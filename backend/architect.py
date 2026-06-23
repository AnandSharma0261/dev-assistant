# ============================================================
#  Phase 3: Architect Agent
#  Kaam: requirement dekh kar SYSTEM DESIGN suggest karna
#  (tech stack, components, data models, API endpoints)
# ============================================================

from gemini_helper import ask_gemini_json


ARCHITECT_ROLE = """
Tum ek experienced Software Architect ho.
Tumhe ek software requirement milegi. Uske liye ek saaf system design banao.

Sirf JSON do, bilkul is format mein:
{
  "tech_stack": {
    "frontend": "...",
    "backend": "...",
    "database": "...",
    "other": ["...", "..."]
  },
  "components": [
    {"name": "...", "responsibility": "1 line"}
  ],
  "data_models": [
    {"name": "...", "fields": ["field1", "field2"]}
  ],
  "api_endpoints": [
    {"method": "GET/POST/...", "path": "/...", "purpose": "1 line"}
  ]
}
Practical aur modern choices suggest karo.
"""


def design_system(requirement):
    """Requirement le kar system design (Python dict) return karta hai."""
    prompt = f"Requirement:\n\n{requirement}\n\nIske liye system design banao."
    return ask_gemini_json(prompt, system_instruction=ARCHITECT_ROLE)


if __name__ == "__main__":
    requirement = (
        "Ek To-Do list web app banao jisme user task add, delete, "
        "aur 'complete' mark kar sake. User login/signup bhi hona chahiye."
    )
    print("⏳ Architect Agent design soch raha hai...\n")
    design = design_system(requirement)

    print("🏛️  TECH STACK:")
    for key, val in design["tech_stack"].items():
        print(f"   - {key}: {val}")

    print("\n🧩 COMPONENTS:")
    for c in design["components"]:
        print(f"   - {c['name']}: {c['responsibility']}")

    print("\n🗄️  DATA MODELS:")
    for m in design["data_models"]:
        print(f"   - {m['name']} ({', '.join(m['fields'])})")

    print("\n🔌 API ENDPOINTS:")
    for a in design["api_endpoints"]:
        print(f"   - {a['method']} {a['path']} → {a['purpose']}")
