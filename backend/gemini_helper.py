# ============================================================
#  gemini_helper.py
#  Ek reusable "helper" — hamare SAARE agents isi ke through
#  Gemini se baat karenge. Ek hi jagah connection + retry logic.
#
#  Async: uses the SDK's async client (client.aio), so many agent calls
#  can be in flight at once without tying up a thread each, and retry
#  waits use asyncio.sleep instead of blocking with time.sleep.
# ============================================================

import asyncio
import os

from dotenv import load_dotenv
from pydantic import ValidationError
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

# Agents now run in parallel. Cap how many Gemini calls are in flight at once
# (across all runs) so a burst doesn't trip the free tier's per-minute limit.
MAX_CONCURRENT_CALLS = int(os.getenv("GEMINI_MAX_CONCURRENCY", "4"))
_limiter = asyncio.Semaphore(MAX_CONCURRENT_CALLS)


async def _generate(prompt, system_instruction=None, schema=None, retries=6):
    """
    Andar ka asli kaam karne wala function.
    - prompt              = humara sawaal
    - system_instruction  = agent ka ROLE (jaise "tum planner ho")
    - schema              = Pydantic model. Given => Gemini is constrained to this
                            JSON shape (response_schema) and we return a validated
                            instance of it instead of raw text.
    - retries             = busy (503) hone par kitni baar dobara try karein
    """
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )

    last_err = None

    # ---- Har model ko bari-bari try karo (FAILOVER) ----
    for model in MODELS:
        for attempt in range(1, retries + 1):
            try:
                async with _limiter:
                    response = await client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                    )
                if schema is None:
                    return response.text
                if not response.text:
                    # Blocked or truncated response: nothing to parse
                    raise ValueError("Empty response from model")
                return schema.model_validate_json(response.text)
            except (ValidationError, ValueError) as e:
                # Output didn't match the schema (rare with response_schema, but
                # possible on truncation). Retry immediately, no backoff needed.
                last_err = e
                print(f"⚠️  '{model}' returned invalid output (attempt {attempt}/{retries}): {e}")
                if attempt == retries:
                    break
                continue
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
                # Sleep outside the limiter so a waiting retry doesn't hold a slot
                await asyncio.sleep(wait)

    # Saare models fail/exhausted ho gaye
    raise RuntimeError(
        "Saare free Gemini models ka aaj ka quota khatam ho gaya (ya unavailable). "
        f"Kal reset hoga, ya nayi API key use karo. Aakhri error: {last_err}"
    )


async def ask_gemini(prompt, system_instruction=None):
    """Normal text jawab chahiye to ye use karo."""
    return await _generate(prompt, system_instruction)


async def ask_gemini_structured(prompt, schema, system_instruction=None):
    """Structured output: returns a validated instance of the `schema` Pydantic model."""
    return await _generate(prompt, system_instruction, schema=schema)
