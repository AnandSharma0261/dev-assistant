# ============================================================
#  Phase 5: RAG (Retrieval-Augmented Generation)
#  Kaam: company coding standards ko ChromaDB mein daalna (ingest)
#  aur kisi task se related rules dhoondhna (search)
#
#  - Ingest runs automatically at API startup (ensure_ingested). It is
#    keyed on a hash of the standards file, so it only re-runs when the
#    file changes. The Docker build also runs it, which bakes the
#    embedding model and the index into the image.
#  - Style rules that apply to every file (ALWAYS_ON) are always sent.
#    Semantic search can't find them, because they aren't about any
#    topic. Topical rules (security, errors, ...) are retrieved, and kept
#    only when they are actually relevant (cosine distance threshold).
#  - ChromaDB's default embedding model runs LOCALLY, so embeddings
#    don't use any Gemini quota.
# ============================================================

import hashlib
import logging
import os
import re

import chromadb

logger = logging.getLogger(__name__)

# ---- Paths / settings ----
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("CHROMA_PATH", os.path.join(BASE, "chroma_db"))
STANDARDS_PATH = os.path.join(BASE, "standards", "coding_standards.md")
COLLECTION_NAME = "coding_standards"
INDEX_VERSION = "2"   # bump when chunking/embedding settings change -> forces re-ingest

# Section titles that apply to every file, whatever the task
ALWAYS_ON = ("File Header Rule", "Naming Conventions", "Comments & Documentation")
TOP_K = 3                 # max topical rules per task
MAX_DISTANCE = 0.85       # cosine distance; calibrated on this standards file

_client = None


def _get_client():
    # Created lazily so importing this module never touches the disk
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=DB_PATH)
    return _client


def _read_standards(path=STANDARDS_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _source_hash(text):
    return hashlib.sha256((INDEX_VERSION + text).encode()).hexdigest()


def _chunk_text(text):
    """
    Split into one chunk per "## " section. The document title / preamble
    before the first section is dropped. Returns [(title, chunk_text)].
    """
    sections = re.split(r"(?m)^(?=## )", text)
    chunks = []
    for s in sections:
        s = s.strip()
        if s.startswith("## "):
            title = s.splitlines()[0][3:].strip()
            chunks.append((title, s))
    return chunks


def ingest_standards(path=STANDARDS_PATH):
    """Standards file padho -> chunks banao -> ChromaDB mein (fresh) daalo."""
    text = _read_standards(path)
    chunks = _chunk_text(text)
    client = _get_client()

    # Recreate from scratch so a re-ingest never leaves stale or duplicate rules
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass  # pehli baar hai to delete karne ko kuch nahi hoga

    collection = client.create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"source_hash": _source_hash(text)},
    )
    # add() khud har chunk ko embedding (vector) mein badal kar store karta hai
    collection.add(
        ids=[f"rule-{i}" for i in range(len(chunks))],
        documents=[c for _, c in chunks],
        metadatas=[{"title": t, "always_on": t in ALWAYS_ON} for t, _ in chunks],
    )
    missing = set(ALWAYS_ON) - {t for t, _ in chunks}
    if missing:
        logger.warning("ALWAYS_ON sections not found in standards file: %s", sorted(missing))
    return len(chunks)


def ensure_ingested():
    """Ingest only if the index is missing or the standards file changed. Returns True if it ingested."""
    expected = _source_hash(_read_standards())
    try:
        collection = _get_client().get_collection(name=COLLECTION_NAME)
        if (collection.metadata or {}).get("source_hash") == expected and collection.count() > 0:
            logger.info("RAG index up to date (%d rules)", collection.count())
            return False
    except Exception:
        pass  # collection doesn't exist yet
    count = ingest_standards()
    logger.info("RAG index built (%d rules)", count)
    return True


def status():
    """Small health summary: is the index there, and how many rules does it hold."""
    try:
        count = _get_client().get_collection(name=COLLECTION_NAME).count()
        return {"ready": count > 0, "rules": count}
    except Exception:
        return {"ready": False, "rules": 0}


def search_standards(query, n=TOP_K, max_distance=MAX_DISTANCE):
    """
    Rules for one task: every ALWAYS_ON rule, plus up to `n` topical rules
    that are within `max_distance` of the query. Return: rules ki list (text).
    Raises if the index is missing, so a broken RAG fails loudly instead of
    silently producing code without the standards.
    """
    collection = _get_client().get_collection(name=COLLECTION_NAME)

    always = collection.get(where={"always_on": True})
    rules = list(always["documents"])

    topical_count = collection.count() - len(rules)
    if topical_count > 0:
        results = collection.query(
            query_texts=[query],
            n_results=min(n, topical_count),
            where={"always_on": False},
            include=["documents", "distances"],
        )
        # query() nested list deta hai (multiple queries ke liye); humne ek bheji to [0]
        for doc, dist in zip(results["documents"][0], results["distances"][0]):
            if dist <= max_distance:
                rules.append(doc)
    return rules


# ---- File ko seedha run karne par: (re)ingest + ek test search ----
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("📥 Standards ko ChromaDB mein daal rahe hain (pehli baar model download ho sakta hai)...")
    count = ingest_standards()
    print(f"✅ {count} rules (chunks) store ho gaye\n")

    for test_query in ["user signup API with password", "initialize project structure"]:
        print(f"🔍 Test search: '{test_query}'")
        for r in search_standards(test_query):
            print("   •", r.splitlines()[0])
        print()
