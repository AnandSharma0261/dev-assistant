# ============================================================
#  Preview Agent
#  Kaam: requirement ka ek CHALTA-PHIRTA prototype banana — ek single,
#  self-contained HTML file (inline CSS + JS) jo browser mein seedha chale.
#  Frontend ise sandboxed iframe mein dikhata hai (Live Preview).
#
#  Developer agent production-style backend code likhta hai (Node/Python),
#  jo browser mein run nahi ho sakta. Preview is the clickable counterpart:
#  same plan + design, but built to run on its own with no server.
# ============================================================

import asyncio
import re

from gemini_helper import ask_gemini

PREVIEW_ROLE = """
Tum ek senior frontend developer ho jo jaldi se working prototypes banata hai.
Tumhe requirement, plan aur system design milega. Uska ek WORKING, clickable
prototype banao — ek single HTML file mein.

Strict rules:
- Sirf ek complete HTML document do, <!DOCTYPE html> se shuru. Koi explanation nahi.
- Saara CSS <style> mein aur saara JS <script> mein — inline. Koi external file,
  CDN, font, image URL ya fetch/XHR NAHI (network blocked hai, kuch load nahi hoga).
- Koi backend nahi hai: data JS memory mein rakho. Login/signup jaisi cheezein
  in-memory fake data se simulate karo. localStorage/sessionStorage/cookies use mat
  karo (sandbox mein blocked hain).
- Plain JavaScript (no frameworks). Design saaf, modern aur responsive ho.
- Core features sach mein kaam karein (jaise calculator ke buttons, todo add/delete).
"""

_HTML_RE = re.compile(r"<!DOCTYPE html.*</html>|<html.*</html>", re.IGNORECASE | re.DOTALL)


def extract_html(text):
    """Model kabhi-kabhi ```html fences ya extra text jod deta hai — sirf document nikaalo."""
    match = _HTML_RE.search(text or "")
    if not match:
        raise ValueError("Preview agent did not return an HTML document")
    return match.group(0)


async def build_prototype(requirement, plan=None, design=None):
    """Requirement (+ optional plan, design) le kar ek self-contained HTML document (str) return karta hai."""
    prompt = f"Requirement:\n\n{requirement}"
    if plan:
        prompt += f"\n\n--- PLANNED TASKS ---\n{plan.as_prompt()}"
    if design:
        prompt += f"\n\n--- SYSTEM DESIGN (UI isse consistent ho) ---\n{design.as_prompt()}"
    prompt += "\n\nIska working prototype ek single HTML file mein banao."
    return extract_html(await ask_gemini(prompt, system_instruction=PREVIEW_ROLE))


if __name__ == "__main__":
    html = asyncio.run(build_prototype("Ek simple calculator banao: + - × ÷, clear, aur decimal support."))
    with open("preview.html", "w") as f:
        f.write(html)
    print(f"✅ preview.html ban gaya ({len(html)} chars) — browser mein kholo")
