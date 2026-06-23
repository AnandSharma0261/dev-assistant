# ============================================================
#  Phase 3: QA Agent
#  Kaam: ek feature/requirement ke liye TEST CASES banana
# ============================================================

from gemini_helper import ask_gemini_json


QA_ROLE = """
Tum ek detail-oriented QA (Quality Assurance) Engineer ho.
Tumhe ek feature ya requirement milegi. Uske liye clear test cases banao.
Normal cases ke saath edge cases bhi socho (galat input, khaali field, etc.).

Sirf JSON do, is format mein:
{
  "test_cases": [
    {"id": 1, "title": "...", "steps": ["step1", "step2"], "expected": "kya hona chahiye"}
  ]
}
"""


def generate_tests(feature):
    """Feature (text) le kar test cases (Python dict) return karta hai."""
    prompt = f"Is feature ke liye test cases banao:\n\n{feature}"
    return ask_gemini_json(prompt, system_instruction=QA_ROLE)


if __name__ == "__main__":
    feature = "User login feature: user email aur password daal kar login karta hai."
    print("⏳ QA Agent test cases bana raha hai...\n")
    result = generate_tests(feature)

    print("🧪 TEST CASES:\n")
    for t in result["test_cases"]:
        print(f"   [{t['id']}] {t['title']}")
        for i, step in enumerate(t["steps"], 1):
            print(f"        {i}. {step}")
        print(f"        ✅ Expected: {t['expected']}\n")
