# ============================================================
#  Phase 3: Developer Agent
#  Kaam: ek task le kar uska ACTUAL CODE likhna
# ============================================================

# Yahan ask_gemini (normal text) use kar rahe hain, JSON nahi —
# kyunki code ek text hota hai, use seedha padhna aasaan hai.
from gemini_helper import ask_gemini


DEVELOPER_ROLE = """
Tum ek senior software developer ho.
Tumhe ek development task diya jaayega. Uska complete, working code likho.

Rules:
- Saaf, readable code likho with short helpful comments.
- Agar koi assumption le rahe ho to code ke upar 1-2 line mein likh do.
- Sirf code aur zaroori chhoti explanation do, faltu baatein nahi.
"""


def write_code(task, language="JavaScript (Node.js + Express)", standards=None):
    """
    Ek task (text) le kar uska code (text) return karta hai.
    standards = (optional) company coding rules ki list — RAG se aati hai.
                Di gayi to code unhe FOLLOW karega.
    """
    prompt = f"Task: {task}\n\nIska code {language} mein likho."

    # Agar company standards diye gaye hain to unhe prompt mein jod do (yahi RAG ka 'Augmented' hai)
    if standards:
        rules = "\n".join(standards) if isinstance(standards, list) else standards
        prompt += (
            "\n\n--- COMPANY CODING STANDARDS (inhe ZAROOR follow karo) ---\n"
            + rules
        )

    return ask_gemini(prompt, system_instruction=DEVELOPER_ROLE)


if __name__ == "__main__":
    task = "Ek API endpoint banao jo user signup kare: email aur password le, password ko hash kare, aur database mein save kare."
    print("⏳ Developer Agent code likh raha hai...\n")
    code = write_code(task)
    print("👨‍💻 Developer Agent ka code:\n")
    print(code)
