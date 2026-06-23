# ============================================================
#  Phase 5: RAG (Retrieval-Augmented Generation)
#  Kaam: company coding standards ko ChromaDB mein daalna (ingest)
#  aur kisi task se related rules dhoondhna (search)
#
#  Khaas: ChromaDB ka DEFAULT embedding model LOCAL chalta hai
#  (internet sirf pehli baar model download ke liye). Matlab
#  embeddings banane mein Gemini ka quota WASTE nahi hota. 🎉
# ============================================================

import os
import chromadb

# ---- Paths set karo ----
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "chroma_db")  # ChromaDB yahan disk par save hoga
STANDARDS_PATH = os.path.join(BASE, "standards", "coding_standards.md")
COLLECTION_NAME = "coding_standards"

# PersistentClient = data disk par save rehta hai (program band hone par bhi)
# (InMemory hota to har baar dobara ingest karna padta)
client = chromadb.PersistentClient(path=DB_PATH)


def _chunk_text(text):
    """
    Document ko chhote 'chunks' mein todo.
    Yahan har section (## heading se shuru) ko ek chunk maante hain.
    Chhote chunks = zyada precise search.
    """
    parts = text.split("## ")          # har section "## " se shuru hota hai
    chunks = []
    for p in parts:
        p = p.strip()
        if p:                          # khaali tukde chhod do
            chunks.append("## " + p)   # "## " wapas jod do (heading ke liye)
    return chunks


def ingest_standards(path=STANDARDS_PATH):
    """Standards file padho -> chunks banao -> ChromaDB mein daalo."""
    with open(path, "r") as f:
        text = f.read()

    chunks = _chunk_text(text)

    # Purana collection delete karo taaki re-run par duplicate na ho
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass  # pehli baar hai to delete karne ko kuch nahi hoga

    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    # add() khud har chunk ko embedding (vector) mein badal kar store karta hai
    collection.add(
        documents=chunks,
        ids=[f"rule-{i}" for i in range(len(chunks))],
    )
    return len(chunks)


def search_standards(query, n=3):
    """
    Ek task/query se related top-n rules ChromaDB se dhoondho.
    Return: rules ki list (text).
    """
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    results = collection.query(query_texts=[query], n_results=n)
    # query() nested list deta hai (multiple queries support karne ke liye),
    # humne ek query bheji to [0] uthate hain
    return results["documents"][0]


# ---- File ko seedha run karne par: ingest + ek test search ----
if __name__ == "__main__":
    print("📥 Standards ko ChromaDB mein daal rahe hain (pehli baar model download ho sakta hai)...")
    count = ingest_standards()
    print(f"✅ {count} rules (chunks) store ho gaye\n")

    # Test: ek task de kar dekho kaun se rules milte hain
    test_query = "user signup API with password"
    print(f"🔍 Test search: '{test_query}'\n")
    rules = search_standards(test_query, n=3)
    for i, r in enumerate(rules, 1):
        print(f"--- Relevant rule #{i} ---")
        print(r)
        print()
