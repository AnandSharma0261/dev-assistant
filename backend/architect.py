# ============================================================
#  Phase 3: Architect Agent
#  Kaam: requirement dekh kar SYSTEM DESIGN suggest karna
#  (tech stack, components, data models, API endpoints)
# ============================================================

import asyncio

from gemini_helper import ask_gemini_structured
from planner import make_plan
from schemas import Design


ARCHITECT_ROLE = """
Tum ek experienced Software Architect ho.
Tumhe ek software requirement aur Planner ke banaye development tasks milenge.
Uske liye ek saaf system design banao: tech stack, main components, data models,
aur API endpoints. Design aisa ho ki har planned task usse implement ho sake.
Responsibility aur purpose 1 line mein. Practical aur modern choices suggest karo.
"""


async def design_system(requirement, plan):
    """Requirement + Planner ka plan le kar validated Design return karta hai."""
    prompt = (
        f"Requirement:\n\n{requirement}\n\n"
        f"Planned tasks:\n{plan.as_prompt()}\n\n"
        "Iske liye system design banao."
    )
    return await ask_gemini_structured(prompt, Design, system_instruction=ARCHITECT_ROLE)


if __name__ == "__main__":
    requirement = (
        "Ek To-Do list web app banao jisme user task add, delete, "
        "aur 'complete' mark kar sake. User login/signup bhi hona chahiye."
    )
    print("⏳ Architect Agent design soch raha hai...\n")
    plan = asyncio.run(make_plan(requirement))
    design = asyncio.run(design_system(requirement, plan))

    print("🏛️  TECH STACK:")
    for key, val in design.tech_stack.model_dump().items():
        print(f"   - {key}: {val}")

    print("\n🧩 COMPONENTS:")
    for c in design.components:
        print(f"   - {c.name}: {c.responsibility}")

    print("\n🗄️  DATA MODELS:")
    for m in design.data_models:
        print(f"   - {m.name} ({', '.join(m.fields)})")

    print("\n🔌 API ENDPOINTS:")
    for a in design.api_endpoints:
        print(f"   - {a.method} {a.path} → {a.purpose}")
