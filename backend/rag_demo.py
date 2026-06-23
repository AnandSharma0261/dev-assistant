# ============================================================
#  Phase 5 demo: RAG ka asar dikhana
#  Same task, do baar: (1) bina standards (2) RAG standards ke saath
# ============================================================

from rag import search_standards
from developer import write_code

# Ek aisa task jisme company rules ka asar dikh sake
task = "Ek function banao jo database se user ka data fetch kare (user id se)."

print("=" * 60)
print("❌ WITHOUT RAG — Developer apni general knowledge se")
print("=" * 60)
code_plain = write_code(task)
print(code_plain[:1200])  # pehle 1200 chars (chhota rakhne ke liye)

print("\n\n")

print("=" * 60)
print("✅ WITH RAG — pehle company standards dhoondo, phir code")
print("=" * 60)

# STEP 1: task se related company rules ChromaDB se dhoondho
rules = search_standards(task, n=4)
print("🔍 ChromaDB se ye rules mile (ye prompt mein jaayenge):")
for r in rules:
    first_line = r.split("\n")[0]
    print(f"   • {first_line}")
print()

# STEP 2: wahi task, par ab rules ke saath
code_rag = write_code(task, standards=rules)
print("👨‍💻 RAG-powered code:\n")
print(code_rag[:1500])
