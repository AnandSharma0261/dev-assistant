# ============================================================
#  Phase 4: Crew (Orchestrator)
#  Kaam: saare agents ko ek TEAM ki tarah chalana, aur har agent ko
#  pichle agents ka output context ke roop mein dena.
#
#  Dependency graph (what each agent needs decides what can run in parallel):
#
#    Planner ──▶ Architect ──┬─▶ Developer × N ──┬──▶ Reviewer ──▶ Fix ──▶ Re-review
#   (requirement) (+plan)    │  (task + design + │   (code + design + standards)
#                            │   RAG standards)  │   self-correction, one round
#                            │                   └──▶ QA (plan + endpoints + code)
#                            └─▶ Preview (runnable single-file HTML prototype)
#
#  - Architect waits for the plan so the design covers every task (better
#    context, at the cost of not running alongside the Planner).
#  - Developer tasks and Preview are independent and run concurrently; so do
#    the review chain and QA.
#  - Self-correction (reflection): if the Reviewer finds High/Medium issues,
#    the affected files go back to the Developer with those findings, then the
#    Reviewer verifies the fixed code against its earlier findings. One round
#    only, so cost and time stay bounded.
#  - Developer code and Preview HTML stream to the client as they are written.
#  - Every run records a timeline, LLM calls, tokens and cost (metrics.py).
#  Needs Python 3.11+ (asyncio.TaskGroup).
# ============================================================

import asyncio
import copy
import os

import metrics
from metrics import agent_scope
from planner import make_plan
from architect import design_system
from developer import revise_code, write_code
from reviewer import review_code
from qa import generate_tests
from previewer import build_prototype, refine_prototype
from rag import search_standards  # company coding standards (RAG)
from schemas import Design, Plan
from streaming import DeltaEmitter, partial_json_string

# Findings with these severities trigger the self-correction round. Medium is
# included because the cost is one LLM call per affected FILE, however many
# findings it has; fixing more of them in that call costs nothing extra.
FIX_SEVERITIES = tuple(s.strip() for s in os.getenv("FIX_SEVERITIES", "High,Medium").split(",") if s.strip())


def _noop(event_type, data):
    pass


def _combine(dev_outputs):
    """All files as one text, numbered so the Reviewer can say which file an issue is in."""
    return "\n\n".join(
        f"===== File #{i}: {d['filename']} (task: {d['task']}) =====\n{d['code']}"
        for i, d in enumerate(dev_outputs, 1)
    )


def _review_counts(review):
    counts = {sev: 0 for sev in ("High", "Medium", "Low")}
    for f in review.findings:
        counts[f.severity] += 1
    counts["standards_failed"] = sum(1 for c in review.standards_check if c.status == "fail")
    return counts


def _fix_targets(review, file_count):
    """Map file index (0-based) -> findings to fix. File 0 / unknown = applies to every file."""
    targets = {}
    for f in review.findings:
        if f.severity not in FIX_SEVERITIES:
            continue
        indexes = [f.file - 1] if 1 <= f.file <= file_count else range(file_count)
        for i in indexes:
            targets.setdefault(i, []).append(f)
    return targets


def _fix_instructions(findings):
    return "Code review mein ye issues mile — inhe fix karo:\n" + "\n".join(
        f"{n}. [{f.severity}] {f.issue} (at: {f.location}) -> Fix: {f.suggestion}"
        for n, f in enumerate(findings, 1)
    )


class _Crew:
    """One run's shared state and event helpers."""

    def __init__(self, on_event):
        self.emit = on_event or _noop
        self.metrics = metrics.start_run()

    def stage(self, name, status, data=None):
        if status != "delta":
            self.metrics.stage_event(name, status)
        self.emit("stage", {"stage": name, "status": status, "data": data})

    def code_stream(self, stage, index, task):
        """Streaming callback that sends just the `code` field of the JSON being written."""
        return DeltaEmitter(
            lambda d: self.stage(stage, "delta", {"index": index, "task": task, **d}),
            extract=lambda text: partial_json_string(text, "code"),
        )

    def html_stream(self):
        return DeltaEmitter(lambda d: self.stage("preview", "delta", d))


async def run_crew(requirement, max_dev_tasks=2, on_event=None):
    """
    Poori AI team ko chalata hai aur final report (dict) return karta hai.
    max_dev_tasks = Developer kitni top tasks ka code likhe (demo fast rakhne ke liye)
    on_event      = optional callback(event_type, data). Each stage reports
                    started / delta / progress / done through it, so the API can
                    stream real progress (and code being typed) to the browser.
    """
    crew = _Crew(on_event)
    stage = crew.stage

    # ---------- STEP 1: PLANNER ----------
    print("📋 Planner: requirement ko tasks mein tod raha hai...")
    stage("planner", "started")
    with agent_scope("planner"):
        plan = await make_plan(requirement)
    stage("planner", "done", plan.model_dump())

    # ---------- STEP 2: ARCHITECT (gets the plan) ----------
    print("🏛️  Architect: system design bana raha hai...")
    stage("architect", "started")
    with agent_scope("architect"):
        design = await design_system(requirement, plan)
    design_context = design.as_prompt()
    backend_lang = design.tech_stack.backend or "JavaScript"
    stage("architect", "done", design.model_dump())

    # ---------- STEP 3: DEVELOPER × N  ∥  PREVIEW ----------
    dev_tasks = plan.tasks[:max_dev_tasks]

    async def develop(index, t):
        # RAG lookup is local CPU work (embeddings), so keep it off the event loop
        standards = await asyncio.to_thread(search_standards, f"{t.title} {t.description}")
        with agent_scope("developer"):
            out = await write_code(
                f"{t.title}: {t.description}",
                language=backend_lang,
                standards=standards,
                design_context=design_context,
                other_tasks=[o.title for o in dev_tasks if o is not t],
                on_text=crew.code_stream("developer", index, t.title),
            )
        output = {"task": t.title, **out.model_dump()}   # task, language, filename, code, notes
        stage("developer", "progress", {"index": index, **output})
        return output, standards

    async def run_developers():
        print(f"👨‍💻 Developer: {len(dev_tasks)} tasks parallel mein...")
        stage("developer", "started", {"total": len(dev_tasks), "tasks": [t.title for t in dev_tasks]})
        # TaskGroup (not gather): if one task fails, the others are cancelled
        # instead of running on and burning quota for a run that already failed.
        async with asyncio.TaskGroup() as tg:
            jobs = [tg.create_task(develop(i, t)) for i, t in enumerate(dev_tasks)]
        stage("developer", "done")
        return [job.result() for job in jobs]   # keeps the plan's task order

    async def run_preview():
        # A nice-to-have: if it fails, the run still completes without a preview.
        stage("preview", "started")
        try:
            with agent_scope("preview"):
                html = await build_prototype(requirement, plan=plan, design=design, on_text=crew.html_stream())
        except Exception as e:
            print(f"     ⚠️  Preview nahi bana: {e}")
            stage("preview", "failed", {"message": "Preview could not be generated."})
            return None
        stage("preview", "done", {"html": html})
        return {"html": html}

    async with asyncio.TaskGroup() as tg:
        devs_job = tg.create_task(run_developers())
        preview_job = tg.create_task(run_preview())
    results, preview = devs_job.result(), preview_job.result()
    dev_outputs = [out for out, _ in results]
    file_standards = [rules for _, rules in results]
    # Every standard any Developer was given — the Reviewer checks compliance with them
    used_standards = list(dict.fromkeys(rule for rules in file_standards for rule in rules))
    original_code = _combine(dev_outputs)

    # ---------- STEP 4: REVIEW -> FIX -> RE-REVIEW  ∥  STEP 5: QA ----------
    async def run_review_chain():
        stage("reviewer", "started")
        with agent_scope("reviewer"):
            first = await review_code(original_code, design_context=design_context, standards=used_standards)
        stage("reviewer", "done", first.model_dump())

        targets = _fix_targets(first, len(dev_outputs))
        if not targets:
            stage("fix", "done", {"skipped": True, "reason": f"No {'/'.join(FIX_SEVERITIES)} findings to fix."})
            return first, None

        print(f"🔧 Fix: {len(targets)} files mein review findings fix ho rahe hain...")
        stage("fix", "started", {"total": len(targets), "files": sorted(targets)})

        async def fix(index, findings):
            current = dev_outputs[index]
            with agent_scope("fix"):
                out = await revise_code(
                    current, _fix_instructions(findings),
                    design_context=design_context, standards=file_standards[index],
                    on_text=crew.code_stream("fix", index, current["task"]),
                )
            fixed = {
                "task": current["task"], **out.model_dump(),
                "revision": {"original_code": current["code"], "addressed": [f.issue for f in findings]},
            }
            dev_outputs[index] = fixed
            stage("fix", "progress", {"index": index, **fixed})

        async with asyncio.TaskGroup() as tg:
            for index, findings in targets.items():
                tg.create_task(fix(index, findings))

        # Verify the fix: the Reviewer checks its earlier findings against the new code
        with agent_scope("reviewer"):
            final = await review_code(_combine(dev_outputs), design_context=design_context,
                                      standards=used_standards, previous_findings=first.findings)
        correction = {
            "before": _review_counts(first),
            "after": _review_counts(final),
            "files_fixed": sorted(targets),
            "initial_review": first.model_dump(),
        }
        stage("fix", "done", {"review": final.model_dump(), "self_correction": correction})
        return final, correction

    async def run_qa():
        stage("qa", "started")
        with agent_scope("qa"):
            tests = await generate_tests(requirement, plan=plan, design=design, code=original_code)
        stage("qa", "done", tests.model_dump())
        return tests

    print("🔍🧪 Review chain + QA parallel mein...")
    async with asyncio.TaskGroup() as tg:
        review_job = tg.create_task(run_review_chain())
        qa_job = tg.create_task(run_qa())
    (review, correction), tests = review_job.result(), qa_job.result()

    # Plain dict (JSON-serialisable) — DB mein save hota hai aur API se jaata hai
    return {
        "requirement": requirement,
        "plan": plan.model_dump(),
        "design": design.model_dump(),
        "dev_outputs": dev_outputs,
        "preview": preview,
        "review": review.model_dump(),
        "self_correction": correction,
        "tests": tests.model_dump(),
        "metrics": crew.metrics.summary(),
    }


REFINE_TARGETS = ("preview", "code")


async def refine_run(parent, instruction, target, on_event=None):
    """
    Follow-up on a finished run: re-run only the part the user wants changed,
    reusing the parent's plan and design as context.
      target="preview": update the prototype HTML.
      target="code":    revise every file, then review the new code.
    Everything else is carried over from the parent run.
    """
    crew = _Crew(on_event)
    stage = crew.stage
    result = copy.deepcopy(parent)
    result.pop("metrics", None)
    plan, design = Plan.model_validate(parent["plan"]), Design.model_validate(parent["design"])
    requirement = parent["requirement"]

    if target == "preview":
        stage("preview", "started")
        with agent_scope("preview"):
            old_html = (parent.get("preview") or {}).get("html")
            if old_html:
                html = await refine_prototype(old_html, instruction, requirement, on_text=crew.html_stream())
            else:   # parent had no preview: build one that includes the request
                html = await build_prototype(f"{requirement}\n\nExtra: {instruction}", plan=plan,
                                             design=design, on_text=crew.html_stream())
        result["preview"] = {"html": html}
        stage("preview", "done", result["preview"])

    elif target == "code":
        dev_outputs = result["dev_outputs"]
        design_context = design.as_prompt()
        stage("developer", "started", {"total": len(dev_outputs), "tasks": [d["task"] for d in dev_outputs]})

        async def revise(index, current):
            standards = await asyncio.to_thread(search_standards, current["task"])
            with agent_scope("developer"):
                out = await revise_code(current, instruction, design_context=design_context,
                                        standards=standards,
                                        on_text=crew.code_stream("developer", index, current["task"]))
            revised = {"task": current["task"], **out.model_dump(),
                       "revision": {"original_code": current["code"], "addressed": [instruction]}}
            dev_outputs[index] = revised
            stage("developer", "progress", {"index": index, **revised})
            return standards

        async with asyncio.TaskGroup() as tg:
            jobs = [tg.create_task(revise(i, d)) for i, d in enumerate(dev_outputs)]
        stage("developer", "done")

        used = list(dict.fromkeys(r for job in jobs for r in job.result()))
        stage("reviewer", "started")
        with agent_scope("reviewer"):
            review = await review_code(_combine(dev_outputs), design_context=design_context, standards=used)
        result["review"] = review.model_dump()
        result["self_correction"] = None
        stage("reviewer", "done", result["review"])
    else:
        raise ValueError(f"Unknown refine target: {target}")

    result["refinement"] = {"instruction": instruction, "target": target}
    result["metrics"] = crew.metrics.summary()
    return result


if __name__ == "__main__":
    from export import report_markdown

    requirement = (
        "Ek To-Do list web app banao jisme user task add, delete, "
        "aur 'complete' mark kar sake. User login/signup bhi hona chahiye."
    )
    print("🚀 AI CREW START — poori team kaam shuru kar rahi hai\n")
    result = asyncio.run(run_crew(requirement, max_dev_tasks=2))

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w") as f:
        f.write(report_markdown(result))
    print(f"🎉 DONE! Report: {report_path}")
