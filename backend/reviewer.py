# ============================================================
#  Phase 3: Reviewer Agent
#  Kaam: diye gaye code ko padh kar galtiyan/sudhaar batana
# ============================================================

import asyncio

from gemini_helper import ask_gemini_structured
from schemas import Review


REVIEWER_ROLE = """
Tum ek strict but helpful Code Reviewer ho.
Tumhe code, project ka system design, aur company coding standards milenge.
Usme bugs, security issues, aur improvements dhoondo. Saath hi check karo:
- code design se match karta hai (data models, endpoints, tech stack)
- company coding standards follow hue hain; har violation ek finding hai
  (issue mein standard ka naam likho).
Har finding ke saath severity aur fix ka suggestion do, aur 1-2 line ka overall verdict.
Agar code bilkul theek hai to findings khaali list rakho.
"""


async def review_code(code, design_context=None, standards=None):
    """Code (+ optional design aur company standards) le kar validated Review return karta hai."""
    prompt = f"Is code ka review karo:\n\n{code}"
    if design_context:
        prompt += f"\n\n--- PROJECT DESIGN ---\n{design_context}"
    if standards:
        prompt += "\n\n--- COMPANY CODING STANDARDS (compliance check karo) ---\n" + "\n".join(standards)
    return await ask_gemini_structured(prompt, Review, system_instruction=REVIEWER_ROLE)


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
    result = asyncio.run(review_code(sample_code))

    print("🔍 REVIEW FINDINGS:\n")
    for f in result.findings:
        print(f"   [{f.severity}] {f.issue}")
        print(f"        💡 {f.suggestion}\n")
    print("📝 Overall:", result.overall_summary)
