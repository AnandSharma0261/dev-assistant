# ============================================================
#  gemini_helper.py
#  Ek reusable "helper" — hamare SAARE agents isi ke through
#  Gemini se baat karenge. Ek hi jagah connection + retry logic.
#
#  - Async client (client.aio): many agent calls in flight without a thread each.
#  - Errors are classified by HTTP status code (APIError.code), not by
#    searching the message text:
#       404       model gone          -> next model
#       429       quota / rate limit  -> next model (each has its own quota)
#       5xx, network, timeout         -> same model, exponential backoff + jitter
#       other 4xx (bad key/request)   -> stop: retrying cannot help
#       invalid structured output     -> same model, immediate retry
#  - Every call has a timeout, so a hung request can't stall a run forever.
#  - Callers get LLMUnavailable with a user-safe message; the raw provider
#    error is logged, never shown to users.
# ============================================================

import asyncio
import logging
import os
import random

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError
from google import genai
from google.genai import errors, types

try:  # the SDK uses aiohttp for async calls when it's installed
    import aiohttp
    _NETWORK_ERRORS = (httpx.TransportError, aiohttp.ClientError, ConnectionError)
except ImportError:  # pragma: no cover
    _NETWORK_ERRORS = (httpx.TransportError, ConnectionError)

logger = logging.getLogger(__name__)


# ---- Key load karo (sirf ek baar, jab file pehli baar import hoti hai) ----
load_dotenv()
_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    raise SystemExit("❌ GEMINI_API_KEY nahi mili. backend/.env file check karo.")

# Gemini tak pahunchne ka darwaza
client = genai.Client(api_key=_api_key)

# Free models ki LIST (fallback order). Pehla try hoga; agar uska quota khatam
# (429) ho jaaye ya model band (404) ho to APNE AAP agle model par switch.
# Override without a code change: GEMINI_MODELS=model-a,model-b
DEFAULT_MODELS = [
    "gemini-3.5-flash-lite",     # sabse halka/sasta — pehle ye
    "gemini-3.5-flash",          # iska apna alag quota
    "gemini-flash-lite-latest",  # alias: Google keeps it pointed at a current model
    "gemini-flash-latest",
]
MODELS = [m.strip() for m in os.getenv("GEMINI_MODELS", "").split(",") if m.strip()] or DEFAULT_MODELS

# Agents run in parallel. Cap how many Gemini calls are in flight at once
# (across all runs) so a burst doesn't trip the free tier's per-minute limit.
MAX_CONCURRENT_CALLS = int(os.getenv("GEMINI_MAX_CONCURRENCY", "4"))
_limiter = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

CALL_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))
TRANSIENT_RETRIES = 4      # per model, for 5xx / network / timeout
INVALID_OUTPUT_RETRIES = 2 # per model, for output that fails schema validation
BACKOFF_BASE = 1.0         # seconds
BACKOFF_CAP = 20.0


class LLMUnavailable(RuntimeError):
    """Gemini could not produce an answer. `str(e)` is safe to show to users."""


def _backoff(attempt):
    """Exponential backoff with full jitter: random in [0, min(cap, base * 2^attempt)]."""
    return random.uniform(0, min(BACKOFF_CAP, BACKOFF_BASE * 2 ** attempt))


async def _call(model, prompt, config):
    async with _limiter:
        return await asyncio.wait_for(
            client.aio.models.generate_content(model=model, contents=prompt, config=config),
            timeout=CALL_TIMEOUT,
        )


async def _generate(prompt, system_instruction=None, schema=None):
    """
    Andar ka asli kaam karne wala function.
    - prompt              = humara sawaal
    - system_instruction  = agent ka ROLE (jaise "tum planner ho")
    - schema              = Pydantic model. Given => Gemini is constrained to this
                            JSON shape (response_schema) and we return a validated
                            instance of it instead of raw text.
    """
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )

    quota_hit = False
    for model in MODELS:
        transient = invalid = 0
        while True:
            try:
                response = await _call(model, prompt, config)
                if schema is None:
                    if not response.text:
                        raise ValueError("Empty response from model")
                    return response.text
                if not response.text:
                    raise ValueError("Empty response from model")
                return schema.model_validate_json(response.text)

            except (ValidationError, ValueError) as e:
                # Blocked/truncated or schema-mismatched output: retry right away
                invalid += 1
                logger.warning("%s: invalid output (%d/%d): %s", model, invalid, INVALID_OUTPUT_RETRIES, e)
                if invalid >= INVALID_OUTPUT_RETRIES:
                    break  # next model

            except errors.APIError as e:
                if e.code in (404, 429):
                    quota_hit = quota_hit or e.code == 429
                    logger.warning("%s: HTTP %s (%s), switching model", model, e.code, e.status)
                    break  # next model
                if e.code is not None and 400 <= e.code < 500:
                    # Bad key, bad request, permission: no model or retry will fix it
                    logger.error("%s: request rejected, HTTP %s: %s", model, e.code, e.message)
                    raise LLMUnavailable(
                        "The AI service rejected the request. Check the API key and configuration."
                    ) from e
                transient += 1   # 5xx
                logger.warning("%s: HTTP %s (%d/%d)", model, e.code, transient, TRANSIENT_RETRIES)

            except (asyncio.TimeoutError, *_NETWORK_ERRORS) as e:
                transient += 1
                logger.warning("%s: %s (%d/%d)", model, type(e).__name__, transient, TRANSIENT_RETRIES)

            # Only transient failures reach here
            if transient >= TRANSIENT_RETRIES:
                break  # next model
            # Sleep outside the limiter so a waiting retry doesn't hold a slot
            await asyncio.sleep(_backoff(transient))

    if quota_hit:
        raise LLMUnavailable("The AI service quota is used up for now. Please try again later.")
    raise LLMUnavailable("The AI service is unavailable right now. Please try again in a few minutes.")


async def ask_gemini(prompt, system_instruction=None):
    """Normal text jawab chahiye to ye use karo."""
    return await _generate(prompt, system_instruction)


async def ask_gemini_structured(prompt, schema, system_instruction=None):
    """Structured output: returns a validated instance of the `schema` Pydantic model."""
    return await _generate(prompt, system_instruction, schema=schema)
