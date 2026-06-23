# ============================================================
#  Phase 1: Hamara pehla AI program
#  Maqsad: Gemini se baat karna aur jawab screen par dikhana
# ============================================================

# 1) "os" = computer ke environment (settings) tak pahunchne ke liye
import os

# 2) load_dotenv = ".env" file ki secret key ko program mein le aata hai
from dotenv import load_dotenv

# 3) genai = Google Gemini se baat karne ka official tool
from google import genai


# ---- Step A: secret key load karo ----
# ".env" file padho aur usme jo GEMINI_API_KEY hai usse uthao
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Safety check: agar key nahi mili to saaf message dekar ruk jao
if not api_key:
    raise SystemExit("❌ GEMINI_API_KEY nahi mili. backend/.env file check karo.")


# ---- Step B: Gemini se connection banao ----
# "client" = Gemini tak pahunchne ka hamara darwaza (door)
client = genai.Client(api_key=api_key)


# ---- Step C: AI ko sawaal bhejo ----
# model = kaunsa dimaag use karna hai (flash = fast aur free-tier friendly)
# contents = humara sawaal/prompt
print("⏳ Gemini se jawab maang rahe hain...\n")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Ek line mein Hindi mein samjhao: 'Agentic AI' kya hota hai?",
)


# ---- Step D: jawab screen par dikhao ----
print("🤖 Gemini ka jawab:")
print(response.text)
