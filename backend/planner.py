# ============================================================
#  Phase 2: Planner Agent
#  Kaam: requirement ko chhote development tasks mein todna
#  (Jaise ek Project Manager karta hai)
# ============================================================

from gemini_helper import ask_gemini_json


# ---- Agent ka ROLE / personality (system instruction) ----
# Ye AI ko batata hai ki usse kis tarah se sochna hai.
PLANNER_ROLE = """
Tum ek experienced Software Project Planner ho.
Tumhe ek software requirement di jaayegi.
Tumhara kaam: us requirement ko chhote, clear, aur practical
development tasks mein todna.

Rules:
- Har task choti aur "actionable" honi chahiye (ek banda usse seedha kar sake).
- Tasks logical order mein hon: pehle setup, phir core features, phir testing.
- Sirf aur sirf JSON do, bilkul is format mein:
{
  "tasks": [
    {"id": 1, "title": "chhota title", "description": "1-2 line mein kya karna hai", "priority": "High"}
  ]
}
priority sirf "High", "Medium", ya "Low" ho.
"""


def make_plan(requirement):
    """Requirement (text) le kar tasks ki list (Python dict) return karta hai."""
    prompt = f"Yeh raha requirement:\n\n{requirement}\n\nIske liye development tasks banao."
    return ask_gemini_json(prompt, system_instruction=PLANNER_ROLE)


# ---- Ye hissa tabhi chalta hai jab file ko SEEDHA run karein ----
if __name__ == "__main__":
    # Test ke liye ek nakli (sample) requirement
    requirement = (
        "Ek To-Do list web app banao jisme user task add, delete, "
        "aur 'complete' mark kar sake. User login/signup bhi hona chahiye."
    )

    print("📥 Requirement:", requirement, "\n")
    print("⏳ Planner Agent soch raha hai...\n")

    plan = make_plan(requirement)

    print("📋 Planner Agent ne ye tasks banaye:\n")
    for t in plan["tasks"]:
        print(f"  [{t['id']}] ({t['priority']}) {t['title']}")
        print(f"       → {t['description']}\n")
