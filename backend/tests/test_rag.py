"""RAG: ingest is idempotent, style rules always apply, topical rules only when relevant."""

import pytest

import rag


def titles(rules):
    return [r.splitlines()[0].removeprefix("## ") for r in rules]


def test_ingest_is_skipped_when_standards_unchanged():
    assert rag.ensure_ingested() is False
    assert rag.status() == {"ready": True, "rules": 7, "source": "default"}


def test_chunking_drops_document_title():
    chunks = rag._chunk_text(rag._read_standards())
    assert all(text.startswith("## ") for _, text, _ in chunks)
    assert "Security Rules" in [t for t, _, _ in chunks]


def test_relevant_topical_rule_is_retrieved():
    found = titles(rag.search_standards("User signup API: hash password and store user in database"))
    assert "Security Rules" in found
    assert set(rag.ALWAYS_ON) <= set(found)


def test_unrelated_task_gets_only_always_on_rules():
    found = titles(rag.search_standards("Setup project structure: initialize Node.js express app"))
    assert set(found) == set(rag.ALWAYS_ON)


def test_missing_index_fails_loudly(monkeypatch, tmp_path):
    import chromadb
    monkeypatch.setattr(rag, "_client", chromadb.PersistentClient(path=str(tmp_path)))
    assert rag.status()["ready"] is False
    with pytest.raises(Exception):
        rag.search_standards("anything")
