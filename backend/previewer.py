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
- Tailwind, Bootstrap, Google Fonts, icon libraries — inme se kuch bhi <script src>
  ya <link href> se mat lao; woh load nahi honge aur page bina style ke dikhega.
  Plain CSS khud likho (system fonts, inline SVG icons).
- Koi backend nahi hai: data JS memory mein rakho. Login/signup jaisi cheezein
  in-memory fake data se simulate karo. localStorage/sessionStorage/cookies use mat
  karo (sandbox mein blocked hain).
- Plain JavaScript (no frameworks). Design saaf, modern aur responsive ho.
- Core features sach mein kaam karein (jaise calculator ke buttons, todo add/delete).
"""

_HTML_RE = re.compile(r"<!DOCTYPE html.*</html>|<html.*</html>", re.IGNORECASE | re.DOTALL)


# <script src="http…"> / <link href="//…"> / @import / url(http…): anything the
# sandbox CSP would block, leaving the prototype unstyled or broken
_EXTERNAL_RE = re.compile(
    r"""<(?:script|link)\b[^>]*\b(?:src|href)\s*=\s*["']?((?:https?:)?//[^"'\s>]+)"""
    r"""|@import\s+(?:url\()?["']?((?:https?:)?//[^"')\s;]+)"""
    r"""|url\(\s*["']?((?:https?:)?//[^"')\s]+)""",
    re.IGNORECASE,
)


def external_resources(html):
    """External URLs the prototype tries to load (they are blocked in the sandbox)."""
    found = []
    for m in _EXTERNAL_RE.finditer(html or ""):
        url = next(g for g in m.groups() if g)
        if url not in found:
            found.append(url)
    return found


def extract_html(text):
    """Model kabhi-kabhi ```html fences ya extra text jod deta hai — sirf document nikaalo."""
    match = _HTML_RE.search(text or "")
    if not match:
        raise ValueError("Preview agent did not return an HTML document")
    return match.group(0)


async def build_prototype(requirement, plan=None, design=None, on_text=None):
    """Requirement (+ optional plan, design) le kar ek self-contained HTML document (str) return karta hai.
    on_text = (optional) streaming callback (text so far)."""
    prompt = f"Requirement:\n\n{requirement}"
    if plan:
        prompt += f"\n\n--- PLANNED TASKS ---\n{plan.as_prompt()}"
    if design:
        prompt += f"\n\n--- SYSTEM DESIGN (UI isse consistent ho) ---\n{design.as_prompt()}"
    prompt += "\n\nIska working prototype ek single HTML file mein banao."
    return await _generate_self_contained(prompt, on_text)


async def _generate_self_contained(prompt, on_text):
    """
    Generate the HTML; if it loads external files (e.g. the Tailwind CDN), which
    the sandbox blocks, ask once more with the offending URLs named. Returns the
    best HTML we got; the UI warns if external files are still referenced.
    """
    html = extract_html(await ask_gemini(prompt, system_instruction=PREVIEW_ROLE, on_text=on_text))
    external = external_resources(html)
    if not external:
        return html
    if on_text:
        on_text("")   # the retry streams from scratch
    retry = (
        f"{prompt}\n\n--- PICHLA JAWAB GALAT THA ---\n"
        f"Usme ye external files thi: {', '.join(external[:5])}. Preview sandbox mein network band hai, "
        "isliye ye load nahi hongi aur page bina style/JS ke dikhega. Inke bina poora HTML dobara do: "
        "saara CSS <style> mein khud likho, saara JS <script> mein."
    )
    fixed = extract_html(await ask_gemini(retry, system_instruction=PREVIEW_ROLE, on_text=on_text))
    return fixed if len(external_resources(fixed)) < len(external) else html


async def refine_prototype(html, instruction, requirement=None, on_text=None):
    """Existing prototype + user ka follow-up instruction -> updated HTML document."""
    prompt = ""
    if requirement:
        prompt += f"Original requirement:\n{requirement}\n\n"
    prompt += (
        f"Yeh current prototype hai:\n\n{html}\n\n"
        f"--- USER KA CHANGE REQUEST ---\n{instruction}\n\n"
        "Ye change karo aur poora updated HTML document do. Jo kaam kar raha hai use mat todo; "
        "sab rules (single file, inline CSS/JS, no network, no storage) wahi rahenge. "
        "Agar current prototype koi external CSS/JS (jaise Tailwind CDN) load karta hai, to use hata kar "
        "wahi styling plain CSS mein <style> ke andar likho."
    )
    return await _generate_self_contained(prompt, on_text)


if __name__ == "__main__":
    html = asyncio.run(build_prototype("Ek simple calculator banao: + - × ÷, clear, aur decimal support."))
    with open("preview.html", "w") as f:
        f.write(html)
    print(f"✅ preview.html ban gaya ({len(html)} chars) — browser mein kholo")
