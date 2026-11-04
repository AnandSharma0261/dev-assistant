# ============================================================
#  Phase 3: Reviewer Agent
#  Kaam: diye gaye code ko padh kar galtiyan/sudhaar batana
# ============================================================

import asyncio

from gemini_helper import ask_gemini_structured
from schemas import Review


REVIEWER_ROLE = """
Tum ek strict, thorough senior Code Reviewer ho. Tumhe code, project ka system
design, aur company coding standards milenge.

Review kaise karna hai:
1. Code ko line-by-line padho. Bugs, security issues (injection, auth, secrets,
   validation), error handling, edge cases, performance, aur design se mismatch
   (data models, endpoints, tech stack) dhoondo.
2. Har company standard ke liye `standards_check` mein ek entry do: pass ya fail,
   aur `note` mein evidence (kahan follow hua / kahan toota). Har fail standard
   ek finding bhi hai.
3. Har finding specific ho: `file` mein us file ka number (code mein "===== File #N"
   header se), `location` mein function/line, aur ek concrete fix.

AI-generated code mein almost hamesha issues hote hain. Findings khaali sirf tab
rakho jab tumne sach mein har cheez check kar li ho aur kuch na mila ho, aur
`overall_summary` mein batao ki kya-kya check kiya. Bina wajah issues mat banao.
"""


async def review_code(code, design_context=None, standards=None, previous_findings=None):
    """
    Code (+ optional design aur company standards) le kar validated Review return karta hai.
    previous_findings = (optional) findings of the review before a fix. The Reviewer then
                        verifies each one instead of starting from scratch, which keeps
                        the before/after comparison consistent (LLM reviews vary run to run).
    """
    prompt = f"Is code ka review karo:\n\n{code}"
    if previous_findings:
        listed = "\n".join(f"- [{f.severity}] {f.issue} (at: {f.location})" for f in previous_findings)
        prompt += (
            "\n\n--- PICHLE REVIEW KE FINDINGS (code ab inhe fix karne ke baad ka hai) ---\n"
            f"{listed}\n"
            "Har finding ko verify karo: jo ab fix ho gaya hai use dobara report MAT karo; jo abhi "
            "bhi hai use usi severity ke saath dobara report karo. Naya issue sirf tab do jab woh "
            "sach mein fix ki wajah se aaya ho ya pehle clearly miss hua ho."
        )
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
        print(f"   [{f.severity}] {f.issue}  ({f.location})")
        print(f"        💡 {f.suggestion}\n")
    for c in result.standards_check:
        print(f"   {'✅' if c.status == 'pass' else '❌'} {c.standard}: {c.note}")
    print("📝 Overall:", result.overall_summary)
