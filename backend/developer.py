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


def _standards_block(standards, heading):
    rules = "\n".join(standards) if isinstance(standards, list) else standards
    return f"\n\n--- {heading} ---\n{rules}"


async def write_code(task, language="JavaScript (Node.js + Express)", standards=None, design_context=None,
                     other_tasks=None, on_text=None):
    """
    Ek task (text) le kar validated CodeOutput (language, filename, code, notes) return karta hai.
    design_context = (optional) Architect ka design (text) — code isse consistent rahe.
    standards = (optional) company coding rules ki list — RAG se aati hai.
                Di gayi to code unhe FOLLOW karega.
    other_tasks = (optional) titles of tasks written in parallel, so filenames don't collide
    on_text = (optional) streaming callback (raw JSON text so far)
    """
    prompt = f"Task: {task}\n\nIska code {language} mein likho."
    if design_context:
        prompt += f"\n\n--- PROJECT DESIGN (isse consistent raho) ---\n{design_context}"
    if other_tasks:
        listed = "\n".join(f"- {t}" for t in other_tasks)
        prompt += (
            "\n\n--- IS PROJECT KI BAAKI FILES (doosre developers parallel mein likh rahe hain) ---\n"
            f"{listed}\nApni file ka path in sabse alag aur specific rakho "
            "(jaise routes/auth.js, models/user.js — generic server.js/index.html nahi, "
            "jab tak yeh task khud app ka entry point na ho)."
        )

    # Agar company standards diye gaye hain to unhe prompt mein jod do (yahi RAG ka 'Augmented' hai)
    if standards:
        prompt += _standards_block(standards, "COMPANY CODING STANDARDS (inhe ZAROOR follow karo)")

    return await ask_gemini_structured(prompt, CodeOutput, system_instruction=DEVELOPER_ROLE, on_text=on_text)


async def revise_code(current, instructions, design_context=None, standards=None, on_text=None):
    """
    Ek existing file (CodeOutput ya uska dict) ko diye gaye instructions ke hisaab
    se badalta hai — review findings fix karne (self-correction) aur user ke
    follow-up (refine) dono ke liye. Poori updated file return karta hai.
    """
    c = current if isinstance(current, dict) else current.model_dump()
    prompt = (
        f"Yeh existing file hai: {c['filename']} ({c['language']})\n\n{c['code']}\n\n"
        f"--- IS FILE MEIN YE CHANGES KARO ---\n{instructions}\n\n"
        "Sirf yahi changes karo; baaki behaviour, naam aur structure same rakho. "
        "Poori updated file do (same filename aur language). `notes` mein 1-2 line mein batao kya badla."
    )
    if design_context:
        prompt += f"\n\n--- PROJECT DESIGN (isse consistent raho) ---\n{design_context}"
    if standards:
        prompt += _standards_block(standards, "COMPANY CODING STANDARDS (inhe ZAROOR follow karo)")
    return await ask_gemini_structured(prompt, CodeOutput, system_instruction=DEVELOPER_ROLE, on_text=on_text)


if __name__ == "__main__":
    task = "Ek API endpoint banao jo user signup kare: email aur password le, password ko hash kare, aur database mein save kare."
    print("⏳ Developer Agent code likh raha hai...\n")
    out = asyncio.run(write_code(task))
    print(f"👨‍💻 {out.filename} ({out.language}) — {out.notes}\n")
    print(out.code)
