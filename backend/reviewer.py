# ============================================================
#  Phase 3: Reviewer Agent
#  Kaam: diye gaye code ko padh kar galtiyan/sudhaar batana
# ============================================================

from gemini_helper import ask_gemini_json


REVIEWER_ROLE = """
Tum ek strict but helpful Code Reviewer ho.
Tumhe code diya jaayega. Usme bugs, security issues, aur improvements dhoondo.

Sirf JSON do, is format mein:
{
  "findings": [
    {"issue": "kya problem hai", "severity": "High/Medium/Low", "suggestion": "kaise theek karein"}
  ],
  "overall_summary": "1-2 line ka overall verdict"
}
Agar code bilkul theek hai to findings khaali list rakho.
"""


def review_code(code):
    """Code (text) le kar review (Python dict) return karta hai."""
    prompt = f"Is code ka review karo:\n\n{code}"
    return ask_gemini_json(prompt, system_instruction=REVIEWER_ROLE)


if __name__ == "__main__":
    # Jaan-bujhkar kuch galtiyon wala code (taaki reviewer pakad ke dikhaye)
    sample_code = """
function login(req, res) {
  const user = db.query("SELECT * FROM users WHERE email = '" + req.body.email + "'");
  if (user.password == req.body.password) {
    res.send("Login success");
  }
}
"""
    print("⏳ Reviewer Agent code check kar raha hai...\n")
    result = review_code(sample_code)

    print("🔍 REVIEW FINDINGS:\n")
    for f in result["findings"]:
        print(f"   [{f['severity']}] {f['issue']}")
        print(f"        💡 {f['suggestion']}\n")
    print("📝 Overall:", result["overall_summary"])
