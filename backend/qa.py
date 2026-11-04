# ============================================================
#  Phase 3: QA Agent
#  Kaam: ek feature/requirement ke liye TEST CASES banana
# ============================================================

import asyncio

from gemini_helper import ask_gemini_structured
from schemas import TestSuite


QA_ROLE = """
Tum ek detail-oriented QA (Quality Assurance) Engineer ho.
Tumhe ek requirement milegi, aur ho sakta hai saath mein planned tasks, API endpoints
aur generated code bhi. Uske liye clear test cases banao. Endpoints/code diye hain to
tests unhi ke actual paths, fields aur behaviour par based hon.
Normal cases ke saath edge cases bhi socho (galat input, khaali field, etc.).
Har test case mein clear steps aur expected result ho.
"""


async def generate_tests(feature, plan=None, design=None, code=None):
    """Feature (+ optional plan, design, code) le kar validated TestSuite return karta hai."""
    prompt = f"Is feature ke liye test cases banao:\n\n{feature}"
    if plan:
        prompt += f"\n\n--- PLANNED TASKS ---\n{plan.as_prompt()}"
    if design:
        endpoints = "\n".join(f"- {e.method} {e.path}: {e.purpose}" for e in design.api_endpoints)
        prompt += f"\n\n--- API ENDPOINTS ---\n{endpoints}"
    if code:
        prompt += f"\n\n--- GENERATED CODE ---\n{code}"
    return await ask_gemini_structured(prompt, TestSuite, system_instruction=QA_ROLE)


if __name__ == "__main__":
    feature = "User login feature: user email aur password daal kar login karta hai."
    print("⏳ QA Agent test cases bana raha hai...\n")
    result = asyncio.run(generate_tests(feature))

    print("🧪 TEST CASES:\n")
    for t in result.test_cases:
        print(f"   [{t.id}] {t.title}")
        for i, step in enumerate(t.steps, 1):
            print(f"        {i}. {step}")
        print(f"        ✅ Expected: {t.expected}\n")
