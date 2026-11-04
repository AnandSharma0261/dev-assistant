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
#  - Users can upload their own standards document (set_custom_standards).
#    It is stored under DATA_DIR and replaces the built-in one until reset.
#    A heading ending in "[always]" marks a rule that applies to every file.
# ============================================================

import hashlib
import logging
import os
import re
import threading

import chromadb

logger = logging.getLogger(__name__)

# ---- Paths / settings ----
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("CHROMA_PATH", os.path.join(BASE, "chroma_db"))
STANDARDS_PATH = os.path.join(BASE, "standards", "coding_standards.md")
DATA_DIR = os.getenv("DATA_DIR", BASE)
CUSTOM_STANDARDS_PATH = os.path.join(DATA_DIR, "custom_standards.md")
COLLECTION_NAME = "coding_standards"
INDEX_VERSION = "3"   # bump when chunking/embedding settings change -> forces re-ingest

MAX_DOC_CHARS = 100_000
MAX_RULES = 200
ALWAYS_MARKER = re.compile(r"\s*\[always\]\s*$", re.IGNORECASE)

# Re-indexing deletes and recreates the collection; searches must not run
# in the middle of that. All index access goes through this lock.
_lock = threading.RLock()

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


def active_standards():
    """(text, source): the uploaded document if there is one, else the built-in one."""
    if os.path.exists(CUSTOM_STANDARDS_PATH):
        return _read_standards(CUSTOM_STANDARDS_PATH), "custom"
    return _read_standards(STANDARDS_PATH), "default"


def _source_hash(text):
    return hashlib.sha256((INDEX_VERSION + text).encode()).hexdigest()


def _chunk_text(text):
    """
    Split into one chunk per "## " section (the title/preamble before the first
    section is dropped). A document without "## " sections is split into
    paragraphs instead. Returns [(title, chunk_text, always_on)].
    """
    chunks = []
    sections = [s.strip() for s in re.split(r"(?m)^(?=## )", text)]
    sections = [s for s in sections if s.startswith("## ")]
    if sections:
        for s in sections:
            heading = s.splitlines()[0][3:].strip()
            always = bool(ALWAYS_MARKER.search(heading))
            title = ALWAYS_MARKER.sub("", heading).strip() or "Untitled"
            chunks.append((title, s, always or title in ALWAYS_ON))
    else:
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if para:
                title = para.splitlines()[0].lstrip("#-* ").strip()[:60] or "Rule"
                chunks.append((title, para, False))
    return chunks


def ingest_standards(text=None):
    """Standards text (default: the active document) -> chunks -> ChromaDB (fresh)."""
    with _lock:
        return _ingest(text if text is not None else active_standards()[0])


def _ingest(text):
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
        documents=[c for _, c, _ in chunks],
        metadatas=[{"title": t, "always_on": a} for t, _, a in chunks],
    )
    return len(chunks)


def ensure_ingested():
    """Ingest only if the index is missing or the standards file changed. Returns True if it ingested."""
    with _lock:
        text, source = active_standards()
        expected = _source_hash(text)
        try:
            collection = _get_client().get_collection(name=COLLECTION_NAME)
            if (collection.metadata or {}).get("source_hash") == expected and collection.count() > 0:
                logger.info("RAG index up to date (%d rules, %s standards)", collection.count(), source)
                return False
        except Exception:
            pass  # collection doesn't exist yet
        count = _ingest(text)
        logger.info("RAG index built (%d rules, %s standards)", count, source)
        return True


class InvalidStandards(ValueError):
    """The uploaded document can't be used. Message is safe to show users."""


def set_custom_standards(text):
    """Validate, store and index an uploaded standards document. Returns describe()."""
    text = (text or "").strip()
    if not text:
        raise InvalidStandards("The document is empty.")
    if len(text) > MAX_DOC_CHARS:
        raise InvalidStandards(f"The document is too long (max {MAX_DOC_CHARS:,} characters).")
    if "\x00" in text:
        raise InvalidStandards("The document must be plain text or Markdown.")
    chunks = _chunk_text(text)
    if len(chunks) > MAX_RULES:
        raise InvalidStandards(f"Too many rules ({len(chunks)}); the limit is {MAX_RULES}.")
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CUSTOM_STANDARDS_PATH, "w", encoding="utf-8") as f:
            f.write(text)
        ensure_ingested()
    return describe()


def reset_standards():
    """Go back to the built-in standards document."""
    with _lock:
        if os.path.exists(CUSTOM_STANDARDS_PATH):
            os.remove(CUSTOM_STANDARDS_PATH)
        ensure_ingested()
    return describe()


def describe():
    """Which document is active and the rules it was split into."""
    with _lock:
        text, source = active_standards()
        return {
            "source": source,
            "rules": [{"title": t, "always_on": a} for t, _, a in _chunk_text(text)],
            "content": text,
        }


def status():
    """Small health summary: is the index there, and how many rules does it hold."""
    with _lock:
        try:
            count = _get_client().get_collection(name=COLLECTION_NAME).count()
            return {"ready": count > 0, "rules": count, "source": active_standards()[1]}
        except Exception:
            return {"ready": False, "rules": 0, "source": active_standards()[1]}


def search_standards(query, n=TOP_K, max_distance=MAX_DISTANCE):
    """
    Rules for one task: every ALWAYS_ON rule, plus up to `n` topical rules
    that are within `max_distance` of the query. Return: rules ki list (text).
    Raises if the index is missing, so a broken RAG fails loudly instead of
    silently producing code without the standards.
    """
    with _lock:
        return _search(query, n, max_distance)


def _search(query, n, max_distance):
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
