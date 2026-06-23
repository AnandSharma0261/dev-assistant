# ============================================================
#  Phase 4: Crew (Orchestrator)
#  Kaam: paanchon agents ko ek TEAM ki tarah sahi order mein
#  chalana, aur ek agent ka output agle ko context dena.
#
#  Flow: Planner -> Architect -> Developer -> Reviewer -> QA
# ============================================================

import os

# Apne banaye huye agents ko import karte hain (har file se uska function)
from planner import make_plan
from architect import design_system
from developer import write_code
from reviewer import review_code
from qa import generate_tests
from rag import search_standards  # Phase 5: company coding standards dhoondne ke liye


def run_crew(requirement, max_dev_tasks=2):
    """
    Poori AI team ko chalata hai aur ek final report (text) banata hai.
    max_dev_tasks = Developer kitni top tasks ka code likhe (demo fast rakhne ke liye)
    """

    # ---------- STEP 1: PLANNER ----------
    print("📋 [1/5] Planner: requirement ko tasks mein tod raha hai...")
    plan = make_plan(requirement)
    tasks = plan["tasks"]
    print(f"     ✅ {len(tasks)} tasks bane\n")

    # ---------- STEP 2: ARCHITECT ----------
    print("🏛️  [2/5] Architect: system design bana raha hai...")
    design = design_system(requirement)
    stack = design["tech_stack"]
    # Design ka chhota summary — ye DEVELOPER ko context ke roop mein denge
    design_context = (
        f"Frontend: {stack.get('frontend')}, "
        f"Backend: {stack.get('backend')}, "
        f"Database: {stack.get('database')}."
    )
    backend_lang = stack.get("backend", "JavaScript")
    print(f"     ✅ Design ready ({design_context})\n")

    # ---------- STEP 3: DEVELOPER ----------
    # Har top task ke liye code likhwate hain — aur design ka context bhi dete hain
    print(f"👨‍💻 [3/5] Developer: top {max_dev_tasks} tasks ka code likh raha hai...")
    dev_outputs = []
    for t in tasks[:max_dev_tasks]:
        # YAHAN context pass ho raha hai: task + architect ka design
        task_with_context = (
            f"{t['title']}: {t['description']}\n\n"
            f"Project design context: {design_context}"
        )
        # Phase 5 (RAG): is task se related company standards ChromaDB se dhoondo
        standards = search_standards(f"{t['title']} {t['description']}", n=4)
        # ...aur Developer ko de do taaki code company rules follow kare
        code = write_code(task_with_context, language=backend_lang, standards=standards)
        dev_outputs.append({"task": t["title"], "code": code})
        print(f"     ✅ '{t['title']}' ka code ban gaya (RAG standards ke saath)")
    print()

    # Saare code ko ek jagah jod do — ye REVIEWER ko denge
    combined_code = "\n\n".join(d["code"] for d in dev_outputs)

    # ---------- STEP 4: REVIEWER ----------
    print("🔍 [4/5] Reviewer: Developer ke code ko check kar raha hai...")
    review = review_code(combined_code)
    print(f"     ✅ {len(review['findings'])} findings mile\n")

    # ---------- STEP 5: QA ----------
    print("🧪 [5/5] QA: test cases bana raha hai...")
    tests = generate_tests(requirement)
    print(f"     ✅ {len(tests['test_cases'])} test cases bane\n")

    # Sab kuch ek dictionary mein wapas bhej do
    return {
        "requirement": requirement,
        "plan": plan,
        "design": design,
        "dev_outputs": dev_outputs,
        "review": review,
        "tests": tests,
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

    result = run_crew(requirement, max_dev_tasks=2)

    # Report ko file mein save karo
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "report.md")
    save_report(result, report_path)

    print("=" * 55)
    print(f"🎉 DONE! Poori report yahan save ho gayi:\n   {report_path}")
    print("=" * 55)
