"""Self-correction, streaming, metrics, refine, ZIP export and custom standards."""

import asyncio
import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

import app as app_module
import crew
import rag
import schemas as s
from conftest import RAW_PREVIEW
from export import _safe_path, build_zip
from runs import runs
from streaming import DeltaEmitter, partial_json_string

REQ = {"requirement": "Todo app with login and signup", "max_dev_tasks": 2}


def run_crew():
    events = []
    result = asyncio.run(crew.run_crew("todo app with login", max_dev_tasks=2,
                                       on_event=lambda t, d: events.append(d)))
    return result, events


def high_finding(file=1):
    return s.Finding(issue="Hardcoded JWT secret", severity="High", file=file,
                     location="login()", suggestion="Read it from an env var")


def rebuild(events, stage, index=None):
    """Reassemble streamed text from delta events, honouring resets."""
    text = ""
    for e in events:
        if e["stage"] != stage or e["status"] != "delta":
            continue
        d = e["data"]
        if index is not None and d.get("index") != index:
            continue
        text = "" if d.get("reset") else text
        text += d.get("append", "")
    return text


# ---- self-correction (reflection) ----

def test_high_findings_trigger_one_fix_round(fake_llm):
    fake_llm.reviews = [
        s.Review(findings=[high_finding(file=1)], standards_check=[], overall_summary="1 issue"),
        s.Review(findings=[], standards_check=[], overall_summary="clean"),
    ]
    result, events = run_crew()

    # Only the file the finding pointed at was revised, with the finding in the prompt
    assert len(fake_llm.prompts["Revise"]) == 1
    assert "Hardcoded JWT secret" in fake_llm.prompts["Revise"][0]
    fixed, untouched = result["dev_outputs"]
    assert fixed["code"].startswith("# fixed") and fixed["revision"]["addressed"] == ["Hardcoded JWT secret"]
    assert fixed["revision"]["original_code"].startswith("# code for T0")
    assert "revision" not in untouched

    # The fixed code was reviewed again against the earlier findings
    assert len(fake_llm.prompts["Review"]) == 2 and "# fixed" in fake_llm.prompts["Review"][1]
    assert "PICHLE REVIEW KE FINDINGS" in fake_llm.prompts["Review"][1]
    assert "Hardcoded JWT secret" in fake_llm.prompts["Review"][1]
    assert "PICHLE REVIEW" not in fake_llm.prompts["Review"][0]
    sc = result["self_correction"]
    assert sc["before"]["High"] == 1 and sc["after"]["High"] == 0 and sc["files_fixed"] == [0]
    assert result["review"]["overall_summary"] == "clean"
    statuses = [e["status"] for e in events if e["stage"] == "fix"]
    assert statuses[0] == "started" and statuses[-2:] == ["progress", "done"] and "delta" in statuses
    assert rebuild(events, "fix", index=0) == fixed["code"]          # the fix streamed too


def test_finding_without_a_file_fixes_every_file(fake_llm):
    fake_llm.reviews = [s.Review(findings=[high_finding(file=0)], standards_check=[], overall_summary="x")]
    result, _ = run_crew()
    assert len(fake_llm.prompts["Revise"]) == 2
    assert result["self_correction"]["files_fixed"] == [0, 1]


def test_low_findings_do_not_trigger_a_fix(fake_llm):
    low = s.Finding(issue="naming", severity="Low", file=1, location="x", suggestion="y")
    fake_llm.reviews = [s.Review(findings=[low], standards_check=[], overall_summary="x")]
    result, events = run_crew()
    assert "Revise" not in fake_llm.prompts and result["self_correction"] is None
    assert next(e for e in events if e["stage"] == "fix")["data"]["skipped"] is True


# ---- streaming ----

def test_code_and_preview_stream_as_deltas(fake_llm):
    result, events = run_crew()
    for i, out in enumerate(result["dev_outputs"]):
        # Only the decoded `code` field is streamed (escapes decoded, no JSON around it)
        assert rebuild(events, "developer", index=i) == out["code"]
    assert rebuild(events, "preview") == RAW_PREVIEW


def test_retry_mid_stream_resets_the_client(fake_llm):
    fake_llm.stream_fail_once = {"Preview"}
    result, events = run_crew()
    deltas = [e["data"] for e in events if e["stage"] == "preview" and e["status"] == "delta"]
    assert {"reset": True} in deltas
    assert rebuild(events, "preview") == RAW_PREVIEW


@pytest.mark.parametrize("text, expected", [
    ('{"language": "py", "code', None),
    ('{"code": "a\\nb', "a\nb"),
    ('{"code": "say \\"hi\\"", "notes": "x"}', 'say "hi"'),
    ('{"code": "cut \\', "cut "),                    # escape not finished yet
    ('{"code": "smile \\ud83d\\ude00!"}', "smile 😀!"),
    ('{"code": "half \\ud83d', "half "),             # surrogate pair not finished yet
])
def test_partial_json_string(text, expected):
    assert partial_json_string(text, "code") == expected


def test_delta_emitter_sends_only_new_text():
    sent = []
    emit = DeltaEmitter(sent.append)
    for t in ["ab", "abcd", "", "x"]:
        emit(t)
    assert sent == [{"append": "ab"}, {"append": "cd"}, {"reset": True}, {"append": "x"}]


# ---- observability ----

def test_metrics_record_calls_tokens_cost_and_timeline(fake_llm):
    fake_llm.delay = 0.2
    result, _ = run_crew()
    m = result["metrics"]

    agents = {c["agent"] for c in m["llm_calls"]}
    assert agents == {"planner", "architect", "developer", "preview", "reviewer", "qa"}
    assert all(c["model"] == "gemini-3.5-flash-lite" and c["attempts"] == 1 for c in m["llm_calls"])

    t = m["totals"]
    assert t["calls"] == 7 and t["input_tokens"] == 700 and t["output_tokens"] == 350
    assert t["cost_usd"] == pytest.approx(7 * (100 * 0.30 + 50 * 2.50) / 1e6)

    stages = {st["stage"]: st for st in m["stages"]}
    assert set(stages) == {"planner", "architect", "developer", "preview", "reviewer", "qa"}
    assert stages["planner"]["end_ms"] <= stages["architect"]["start_ms"]
    # Parallel stages overlap, so the run beat doing them one after another
    assert m["speedup"] > 1.2


def test_metrics_count_retries(fake_llm):
    fake_llm.stream_fail_once = {"Preview"}
    result, _ = run_crew()
    preview_call = next(c for c in result["metrics"]["llm_calls"] if c["agent"] == "preview")
    assert preview_call["attempts"] == 2
    assert result["metrics"]["totals"]["retries"] == 1


# ---- API: refine, download, standards ----

@pytest.fixture
def client(fake_llm):
    runs._runs.clear()
    with TestClient(app_module.app) as c:
        yield c


def finish(client, run_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/runs/{run_id}").json()["data"]
        if data["status"] in ("done", "failed", "cancelled"):
            return data
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_refine_preview_reuses_parent(client, fake_llm):
    parent_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    parent = finish(client, parent_id)

    r = client.post(f"/runs/{parent_id}/refine", json={"instruction": "Make the buttons round", "target": "preview"})
    assert r.status_code == 202
    child = finish(client, r.json()["data"]["run_id"])

    assert child["status"] == "done" and child["parent_id"] == parent_id
    assert child["instruction"] == "Make the buttons round"
    res = child["result"]
    assert "refined" in res["preview"]["html"]
    assert "<body>hi</body>" in fake_llm.prompts["PreviewRefine"][0]      # old HTML was the context
    assert res["dev_outputs"] == parent["result"]["dev_outputs"]          # untouched parts carried over
    assert res["refinement"] == {"instruction": "Make the buttons round", "target": "preview"}
    assert [c["agent"] for c in res["metrics"]["llm_calls"]] == ["preview"]

    history = client.get("/runs").json()["data"]["items"]
    assert history[0]["parent_id"] == parent_id


def test_refine_code_revises_files_and_reviews_again(client, fake_llm):
    parent_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    finish(client, parent_id)
    reviews_before = len(fake_llm.prompts["Review"])

    r = client.post(f"/runs/{parent_id}/refine", json={"instruction": "Add rate limiting", "target": "code"})
    child = finish(client, r.json()["data"]["run_id"])["result"]
    assert all(d["code"].startswith("# fixed") for d in child["dev_outputs"])
    assert all("Add rate limiting" in p for p in fake_llm.prompts["Revise"])
    assert len(fake_llm.prompts["Review"]) == reviews_before + 1


def test_refine_validation(client):
    assert client.post("/runs/nope/refine", json={"instruction": "do it"}).status_code == 404
    assert client.post("/runs/nope/refine", json={"instruction": "do it", "target": "db"}).status_code == 422
    assert client.post("/runs/nope/refine", json={"instruction": "x"}).status_code == 422


def test_refine_requires_a_finished_run(client, fake_llm):
    fake_llm.delay = 1.0
    run_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    assert client.post(f"/runs/{run_id}/refine", json={"instruction": "do it"}).status_code == 409
    client.delete(f"/runs/{run_id}")


def test_download_zip(client):
    run_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    finish(client, run_id)
    r = client.get(f"/runs/{run_id}/download")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(z.namelist()) == {"README.md", "src/t0.py", "src/t1.py", "preview/index.html",
                                 "tests/test-cases.json", "design.json"}
    assert "# AI Crew Report" in z.read("README.md").decode()
    assert json.loads(z.read("tests/test-cases.json"))["test_cases"][0]["title"] == "signup works"


def test_zip_paths_are_sanitised_and_deduplicated():
    out = lambda name, task: {"task": task, "filename": name, "language": "js", "code": "x", "notes": ""}
    result = {
        "requirement": "r", "plan": {"tasks": []}, "design": {"tech_stack": {}},
        "dev_outputs": [out("../../etc/passwd", "a"), out("server.js", "Auth API"),
                        out("server.js", "Todo API"), out("/abs/x.js", "b")],
        "preview": None, "review": {"findings": [], "overall_summary": ""}, "tests": {"test_cases": []},
    }
    names = set(zipfile.ZipFile(io.BytesIO(build_zip({"result": result}))).namelist())
    assert {"src/etc/passwd", "src/server.js", "src/todo-api/server.js", "src/abs/x.js"} <= names
    assert not any(n.startswith("/") or ".." in n for n in names)
    assert _safe_path("..", "fallback") == "fallback"


def test_download_unfinished_run_is_409(client, fake_llm):
    fake_llm.delay = 1.0
    run_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    assert client.get(f"/runs/{run_id}/download").status_code == 409
    client.delete(f"/runs/{run_id}")


CUSTOM = """# Acme standards

## Tabs not spaces [always]
Indent with tabs.

## Database access
Use the repository layer for every database query; never call the driver directly.
"""


def test_custom_standards_replace_the_builtin_ones(client):
    try:
        r = client.put("/standards", json={"content": CUSTOM})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["source"] == "custom"
        assert data["rules"] == [{"title": "Tabs not spaces", "always_on": True},
                                 {"title": "Database access", "always_on": False}]
        assert client.get("/health").json()["data"]["rag"] == {"ready": True, "rules": 2, "source": "custom"}

        found = rag.search_standards("Fetch the user record from the database by id")
        assert [r.splitlines()[0] for r in found] == ["## Tabs not spaces [always]", "## Database access"]
    finally:
        r = client.delete("/standards")
    assert r.json()["data"]["source"] == "default"
    assert rag.status()["rules"] == 7


def test_custom_standards_without_headings_split_into_paragraphs():
    chunks = rag._chunk_text("Use tabs.\n\nNever log secrets.\n\n")
    assert [(t, a) for t, _, a in chunks] == [("Use tabs.", False), ("Never log secrets.", False)]


@pytest.mark.parametrize("content", ["", "   ", "x" * (rag.MAX_DOC_CHARS + 1), "bad\x00binary"])
def test_invalid_standards_are_rejected(client, content):
    r = client.put("/standards", json={"content": content})
    assert r.status_code == 422 and r.json()["success"] is False
    assert client.get("/standards").json()["data"]["source"] == "default"
