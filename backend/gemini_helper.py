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

# Free models ki LIST (fallback order). Pehla try hoga; agar uska daily quota
# khatam (429) ho jaaye to system APNE AAP agle model par switch kar jaayega.
# Isse effective quota badh jaata hai (har model ka alag free limit hota hai).
MODELS = [
    "gemini-2.5-flash-lite",   # sabse halka — pehle ye
    "gemini-2.5-flash",        # iska bhi apna alag quota
    "gemini-2.0-flash",        # extra fallback (kuch keys par available)
    "gemini-2.0-flash-lite",   # aur ek fallback
]


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

    last_err = None

    # ---- Har model ko bari-bari try karo (FAILOVER) ----
    for model in MODELS:
        for attempt in range(1, retries + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                return response.text  # mil gaya — yahीं return
            except Exception as e:
                last_err = e
                msg = str(e)

                # Daily quota khatam (429) ya model unavailable (404):
                # is model par retry bekaar — seedha AGLE model par switch karo
                if any(x in msg for x in ("RESOURCE_EXHAUSTED", "429", "404", "NOT_FOUND")):
                    print(f"⚠️  '{model}' ka quota khatam/unavailable — agle model par switch...")
                    break  # inner loop tod do -> agla model

                # Warna transient error (503 busy) — thoda ruk kar SAME model retry
                if attempt == retries:
                    print(f"⚠️  '{model}' se jawab nahi mila, agla model try karte hain...")
                    break
                wait = attempt * 2
                print(f"⚠️  '{model}' busy (attempt {attempt}/{retries}). {wait}s baad retry...")
                time.sleep(wait)

    # Saare models fail/exhausted ho gaye
    raise RuntimeError(
        "Saare free Gemini models ka aaj ka quota khatam ho gaya (ya unavailable). "
        f"Kal reset hoga, ya nayi API key use karo. Aakhri error: {last_err}"
    )


def ask_gemini(prompt, system_instruction=None):
    """Normal text jawab chahiye to ye use karo."""
    return _generate(prompt, system_instruction, as_json=False)


def ask_gemini_json(prompt, system_instruction=None):
    """JSON (structured data) chahiye to ye use karo — Python object return karta hai."""
    text = _generate(prompt, system_instruction, as_json=True)
    return json.loads(text)  # JSON text ko Python dict/list mein badal do
