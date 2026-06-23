# ============================================================
#  Phase 4 (CrewAI version): Wahi AI team, ab CrewAI framework se
#
#  Yahan hum sirf "team" aur "kaam" describe karte hain.
#  Order/flow/context-passing CrewAI khud sambhalta hai.
# ============================================================

import os
from dotenv import load_dotenv

# CrewAI ke 4 main building blocks:
#   Agent   = ek AI worker (role + goal + backstory)
#   Task    = ek kaam (description + expected output + kaun karega)
#   Crew    = poori team + tasks + process (kaise chalega)
#   Process = sequential (ek ke baad ek) ya hierarchical (manager wala)
from crewai import Agent, Task, Crew, Process, LLM

# Telemetry/extra network noise band karo (saaf output ke liye)
os.environ["OTEL_SDK_DISABLED"] = "true"

# .env se key load karo (LiteLLM khud GEMINI_API_KEY env var padhta hai)
load_dotenv()


# ---- LLM (dimaag) set karo: Gemini via LiteLLM ----
# "gemini/" prefix LiteLLM ko batata hai ki ye Google Gemini hai
llm = LLM(
    model="gemini/gemini-2.5-flash-lite",  # is key par sabse zyada free quota wala model
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7,
)


# ============================================================
#  STEP 1: AGENTS define karo (har ek = role + goal + backstory)
# ============================================================

planner = Agent(
    role="Software Project Planner",
    goal="Requirement ko chhote, clear development tasks mein todna",
    backstory="Tum ek experienced project manager ho jo requirements ko actionable tasks mein todne mein expert ho.",
    llm=llm,
    verbose=False,
)

architect = Agent(
    role="Software Architect",
    goal="Requirement ke liye ek solid system design (tech stack, components, APIs) banana",
    backstory="Tum ek senior architect ho jo scalable systems design karne mein mahir ho.",
    llm=llm,
    verbose=False,
)

developer = Agent(
    role="Senior Developer",
    goal="Diye gaye plan aur design ke hisaab se saaf, working code likhna",
    backstory="Tum ek senior developer ho jo clean, secure code likhta hai.",
    llm=llm,
    verbose=False,
)

reviewer = Agent(
    role="Code Reviewer",
    goal="Code mein bugs, security issues aur improvements dhoondna",
    backstory="Tum ek strict but helpful code reviewer ho jo har galti pakad leta hai.",
    llm=llm,
    verbose=False,
)

qa = Agent(
    role="QA Engineer",
    goal="Feature ke liye accha test cases (normal + edge cases) banana",
    backstory="Tum ek detail-oriented QA engineer ho jo har edge case sochta hai.",
    llm=llm,
    verbose=False,
)


# ============================================================
#  STEP 2: TASKS define karo
#  'context=[...]' = is task ko pichle task(s) ka output milega
#  (yahi automatic context-passing hai!)
# ============================================================

REQUIREMENT = (
    "Ek To-Do list web app banao jisme user task add, delete, "
    "aur 'complete' mark kar sake. User login/signup bhi hona chahiye."
)

plan_task = Task(
    description=f"Is requirement ke liye development tasks banao:\n\n{REQUIREMENT}",
    expected_output="Numbered list of clear development tasks with priority.",
    agent=planner,
)

design_task = Task(
    description="Upar wale plan aur requirement ko dekhte hue system design banao: tech stack, main components, data models, aur API endpoints.",
    expected_output="System design: tech stack, components, data models, API endpoints.",
    agent=architect,
    context=[plan_task],  # <-- planner ka output yahan milega
)

dev_task = Task(
    description="Plan aur design ko dekhte hue, sabse important 1-2 backend tasks ka actual working code likho (jaise user signup/login).",
    expected_output="Working code with short comments.",
    agent=developer,
    context=[plan_task, design_task],  # <-- planner + architect dono ka output
)

review_task = Task(
    description="Developer ke likhe code ka review karo. Bugs, security issues, improvements batao with severity.",
    expected_output="List of findings (issue, severity, suggestion) + overall verdict.",
    agent=reviewer,
    context=[dev_task],  # <-- developer ka code yahan milega
)

qa_task = Task(
    description=f"Is feature ke liye test cases banao (normal + edge cases):\n\n{REQUIREMENT}",
    expected_output="List of test cases with steps and expected result.",
    agent=qa,
    context=[plan_task],
)


# ============================================================
#  STEP 3: CREW banao aur chalao
# ============================================================

crew = Crew(
    agents=[planner, architect, developer, reviewer, qa],
    tasks=[plan_task, design_task, dev_task, review_task, qa_task],
    process=Process.sequential,  # ek ke baad ek (assembly line)
    verbose=False,
)


if __name__ == "__main__":
    print("🚀 CrewAI team kaam shuru kar rahi hai (thoda time lega)...\n")

    # kickoff() poori crew ko chalata hai aur final result deta hai
    result = crew.kickoff()

    # Har task ka output ek saaf report file mein save karo
    labels = ["📋 PLANNER", "🏛️ ARCHITECT", "👨‍💻 DEVELOPER", "🔍 REVIEWER", "🧪 QA"]

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "crewai_report.md")

    with open(report_path, "w") as f:
        f.write("# CrewAI Team Report\n\n")
        for label, task_output in zip(labels, result.tasks_output):
            f.write(f"\n## {label}\n\n")
            f.write(task_output.raw)
            f.write("\n")

    print("\n" + "=" * 55)
    print(f"🎉 DONE! CrewAI report yahan save ho gayi:\n   {report_path}")
    print("=" * 55)
