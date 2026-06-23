# ============================================================
#  gemini_helper.py
#  Ek reusable "helper" — hamare SAARE agents isi ke through
#  Gemini se baat karenge. Ek hi jagah connection + retry logic.
# ============================================================

import os
import time
import json

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ---- Key load karo (sirf ek baar, jab file pehli baar import hoti hai) ----
load_dotenv()
_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    raise SystemExit("❌ GEMINI_API_KEY nahi mili. backend/.env file check karo.")

# Gemini tak pahunchne ka darwaza
client = genai.Client(api_key=_api_key)

# Kaunsa model use karna hai.
# gemini-2.5-flash-lite = is key par sabse zyada free quota wala model (probe karke pata kiya).
# NOTE: model badalna ho to bas yahi ek line change karo — poora project switch ho jaayega.
MODEL = "gemini-2.5-flash-lite"


def _generate(prompt, system_instruction=None, as_json=False, retries=6):
    """
    Andar ka asli kaam karne wala function.
    - prompt              = humara sawaal
    - system_instruction  = agent ka ROLE (jaise "tum planner ho")
    - as_json             = True ho to Gemini se saaf JSON maangte hain
    - retries             = busy (503) hone par kitni baar dobara try karein
    """
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        # JSON maangne par Gemini hamesha valid JSON hi dega
        response_mime_type="application/json" if as_json else None,
    )

    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            # Aakhri koshish bhi fail ho gayi to error dikha do
            if attempt == retries:
                raise SystemExit(
                    f"❌ {retries} baar try kiya par Gemini se jawab nahi aaya.\nError: {e}"
                )
            # Warna thoda ruk kar dobara try karo (har baar thoda zyada wait)
            wait = attempt * 2
            print(f"⚠️  Gemini busy (attempt {attempt}/{retries}). {wait}s baad retry...")
            time.sleep(wait)


def ask_gemini(prompt, system_instruction=None):
    """Normal text jawab chahiye to ye use karo."""
    return _generate(prompt, system_instruction, as_json=False)


def ask_gemini_json(prompt, system_instruction=None):
    """JSON (structured data) chahiye to ye use karo — Python object return karta hai."""
    text = _generate(prompt, system_instruction, as_json=True)
    return json.loads(text)  # JSON text ko Python dict/list mein badal do
