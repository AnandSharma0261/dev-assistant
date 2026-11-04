# ============================================================
#  Phase 3: Developer Agent
#  Kaam: ek task le kar uska ACTUAL CODE likhna
# ============================================================

# Structured output: language + filename + code + notes, so the UI can
# highlight the right language and show a real file name (no regex on fences).
import asyncio

from gemini_helper import ask_gemini_structured
from schemas import CodeOutput


DEVELOPER_ROLE = """
Tum ek senior software developer ho.
Tumhe ek development task aur project ka system design diya jaayega.
Uska complete, working code likho jo design ke data models, endpoints aur
tech stack se match kare (naam, fields, paths wahi rakho).

Rules:
- Saaf, readable code likho with short helpful comments.
- Ek task = ek main file. `code` mein poori file ho, markdown fences (```) nahi.
- Assumptions ya chalane ka tareeka `notes` mein 1-2 line mein likho.
"""


async def write_code(task, language="JavaScript (Node.js + Express)", standards=None, design_context=None):
    """
    Ek task (text) le kar validated CodeOutput (language, filename, code, notes) return karta hai.
    design_context = (optional) Architect ka design (text) — code isse consistent rahe.
    standards = (optional) company coding rules ki list — RAG se aati hai.
                Di gayi to code unhe FOLLOW karega.
    """
    prompt = f"Task: {task}\n\nIska code {language} mein likho."
    if design_context:
        prompt += f"\n\n--- PROJECT DESIGN (isse consistent raho) ---\n{design_context}"

    # Agar company standards diye gaye hain to unhe prompt mein jod do (yahi RAG ka 'Augmented' hai)
    if standards:
        rules = "\n".join(standards) if isinstance(standards, list) else standards
        prompt += (
            "\n\n--- COMPANY CODING STANDARDS (inhe ZAROOR follow karo) ---\n"
            + rules
        )

    return await ask_gemini_structured(prompt, CodeOutput, system_instruction=DEVELOPER_ROLE)


if __name__ == "__main__":
    task = "Ek API endpoint banao jo user signup kare: email aur password le, password ko hash kare, aur database mein save kare."
    print("⏳ Developer Agent code likh raha hai...\n")
    out = asyncio.run(write_code(task))
    print(f"👨‍💻 {out.filename} ({out.language}) — {out.notes}\n")
    print(out.code)
