# ============================================================
#  Phase 4: Crew (Orchestrator)
#  Kaam: paanchon agents ko ek TEAM ki tarah chalana, aur har agent ko
#  pichle agents ka output context ke roop mein dena.
#
#  Dependency graph (what each agent needs decides what can run in parallel):
#
#    Planner ──▶ Architect ──▶ Developer × N ──┬──▶ Reviewer
#   (requirement) (+plan)    (parallel; task + │   (code + design + standards)
#                             design + RAG)    └──▶ QA
#                                                  (plan + endpoints + code)
#
#  Architect waits for the plan so the design covers every task (a
#  deliberate trade: better context over running it alongside the Planner).
#  The Developer tasks are independent, so they run concurrently, and so do
#  Reviewer and QA, since neither needs the other's output.
#  Needs Python 3.11+ (asyncio.TaskGroup).
# ============================================================

import asyncio
import os

# Apne banaye huye agents ko import karte hain (har file se uska function)
from planner import make_plan
from architect import design_system
from developer import write_code
from reviewer import review_code
from qa import generate_tests
from rag import search_standards  # Phase 5: company coding standards dhoondne ke liye


def _noop(event_type, data):
    pass


async def run_crew(requirement, max_dev_tasks=2, on_event=None):
    """
    Poori AI team ko chalata hai aur final report (dict) return karta hai.
    max_dev_tasks = Developer kitni top tasks ka code likhe (demo fast rakhne ke liye)
    on_event      = optional callback(event_type, data). Each stage reports
                    started / progress / done through it, so callers (the API's
                    SSE stream) can show real progress instead of a spinner.
    """
    emit = on_event or _noop

    def stage(name, status, data=None):
        emit("stage", {"stage": name, "status": status, "data": data})

    # ---------- STEP 1: PLANNER ----------
    print("📋 Planner: requirement ko tasks mein tod raha hai...")
    stage("planner", "started")
    plan = await make_plan(requirement)
    stage("planner", "done", plan.model_dump())
    print(f"     ✅ {len(plan.tasks)} tasks bane")

    # ---------- STEP 2: ARCHITECT (gets the plan) ----------
    print("🏛️  Architect: system design bana raha hai...")
    stage("architect", "started")
    design = await design_system(requirement, plan)
    design_context = design.as_prompt()
    backend_lang = design.tech_stack.backend or "JavaScript"
    stage("architect", "done", design.model_dump())
    print(f"     ✅ Design ready (backend: {backend_lang})")

    # ---------- STEP 3: DEVELOPER × N (parallel) ----------
    dev_tasks = plan.tasks[:max_dev_tasks]
    print(f"👨‍💻 Developer: {len(dev_tasks)} tasks ka code parallel mein likh raha hai...")
    stage("developer", "started", {"total": len(dev_tasks)})

    async def develop(t):
        # RAG lookup is local CPU work (embeddings), so keep it off the event loop
        standards = await asyncio.to_thread(search_standards, f"{t.title} {t.description}")
        code = await write_code(
            f"{t.title}: {t.description}",
            language=backend_lang,
            standards=standards,
            design_context=design_context,
        )
        output = {"task": t.title, "code": code}
        stage("developer", "progress", output)   # reported as each one finishes
        print(f"     ✅ '{t.title}' ka code ban gaya ({len(standards)} standards ke saath)")
        return output, standards

    # TaskGroup (not gather): if one task fails, the others are cancelled
    # instead of running on and burning quota for a run that already failed.
    async with asyncio.TaskGroup() as tg:
        dev_jobs = [tg.create_task(develop(t)) for t in dev_tasks]
    results = [job.result() for job in dev_jobs]
    dev_outputs = [out for out, _ in results]   # gather keeps the plan's task order
    stage("developer", "done")

    # Every standard any Developer was given — the Reviewer checks compliance with them
    used_standards = list(dict.fromkeys(rule for _, rules in results for rule in rules))
    combined_code = "\n\n".join(f"// ===== Task: {d['task']} =====\n{d['code']}" for d in dev_outputs)

    # ---------- STEP 4 + 5: REVIEWER and QA (parallel) ----------
    async def run_review():
        stage("reviewer", "started")
        review = await review_code(combined_code, design_context=design_context, standards=used_standards)
        stage("reviewer", "done", review.model_dump())
        print(f"     ✅ Reviewer: {len(review.findings)} findings")
        return review

    async def run_qa():
        stage("qa", "started")
        tests = await generate_tests(requirement, plan=plan, design=design, code=combined_code)
        stage("qa", "done", tests.model_dump())
        print(f"     ✅ QA: {len(tests.test_cases)} test cases")
        return tests

    print("🔍🧪 Reviewer + QA parallel mein chal rahe hain...")
    async with asyncio.TaskGroup() as tg:
        review_job = tg.create_task(run_review())
        qa_job = tg.create_task(run_qa())
    review, tests = review_job.result(), qa_job.result()

    # Plain dict (JSON-serialisable) — DB mein save hota hai aur API se jaata hai
    return {
        "requirement": requirement,
        "plan": plan.model_dump(),
        "design": design.model_dump(),
        "dev_outputs": dev_outputs,
        "review": review.model_dump(),
        "tests": tests.model_dump(),
    }


def save_report(result, path):
    """Result ko ek padhne-laayak Markdown report file mein save karta hai."""
    r = result
    lines = []
    lines.append(f"# AI Crew Report\n")
    lines.append(f"## Requirement\n{r['requirement']}\n")

    lines.append("## 📋 Plan (Tasks)\n")
    for t in r["plan"]["tasks"]:
        lines.append(f"- **[{t['priority']}] {t['title']}** — {t['description']}")
    lines.append("")

    lines.append("## 🏛️ Architecture\n")
    st = r["design"]["tech_stack"]
    for k, v in st.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## 👨‍💻 Generated Code\n")
    for d in r["dev_outputs"]:
        lines.append(f"### {d['task']}\n")
        lines.append(d["code"])
        lines.append("")

    lines.append("## 🔍 Code Review\n")
    for f in r["review"]["findings"]:
        lines.append(f"- **[{f['severity']}]** {f['issue']} → _{f['suggestion']}_")
    lines.append(f"\n**Overall:** {r['review']['overall_summary']}\n")

    lines.append("## 🧪 Test Cases\n")
    for tc in r["tests"]["test_cases"]:
        lines.append(f"- **{tc['title']}** → Expected: {tc['expected']}")
    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    requirement = (
        "Ek To-Do list web app banao jisme user task add, delete, "
        "aur 'complete' mark kar sake. User login/signup bhi hona chahiye."
    )

    print("=" * 55)
    print("🚀 AI CREW START — poori team kaam shuru kar rahi hai")
    print("=" * 55, "\n")

    result = asyncio.run(run_crew(requirement, max_dev_tasks=2))

    # Report ko file mein save karo
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "report.md")
    save_report(result, report_path)

    print("=" * 55)
    print(f"🎉 DONE! Poori report yahan save ho gayi:\n   {report_path}")
    print("=" * 55)
