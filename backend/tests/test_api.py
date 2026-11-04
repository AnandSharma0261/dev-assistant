"""HTTP API: validation, response envelope, runs + SSE, history, cancellation."""

import json
import time

import pytest
from fastapi.testclient import TestClient

import app as app_module
from runs import runs

REQ = {"requirement": "Todo app with login and signup", "max_dev_tasks": 2}


@pytest.fixture
def client(fake_llm):
    runs._runs.clear()
    with TestClient(app_module.app) as c:
        yield c


def sse_events(client, run_id, headers=None):
    body = client.get(f"/runs/{run_id}/events", headers=headers or {}).text
    events, current = [], {}
    for line in body.splitlines():
        if line.startswith("event:"):
            current["event"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:])
        elif line.startswith("id:"):
            current["id"] = int(line[3:])
        elif line == "" and "event" in current:
            events.append(current)
            current = {}
    return events


def wait_for(client, run_id, statuses, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/runs/{run_id}").json()["data"]
        if data["status"] in statuses:
            return data
        time.sleep(0.05)
    raise AssertionError(f"run never reached {statuses}")


# ---- validation & envelope ----

def test_health(client):
    body = client.get("/health").json()
    assert body == {"success": True, "data": {"status": "ok", "rag": {"ready": True, "rules": 7, "source": "default"}}}


@pytest.mark.parametrize("payload, field", [
    ({"requirement": "too short"}, "requirement"),
    ({"requirement": "x" * 4001}, "requirement"),
    ({"requirement": "          padded          "}, "requirement"),   # stripped -> too short
    ({"requirement": "A long enough requirement", "max_dev_tasks": 6}, "max_dev_tasks"),
    ({"requirement": "A long enough requirement", "max_dev_tasks": 0}, "max_dev_tasks"),
    ({"requirement": "A long enough requirement", "admin": True}, "admin"),
])
def test_invalid_input_is_rejected_with_422(client, payload, field):
    r = client.post("/runs", json=payload)
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False and body["message"] == "Invalid request."
    assert field in [e["field"] for e in body["errors"]]


def test_plan_success_and_llm_outage(client, fake_llm):
    r = client.post("/plan", json=REQ)
    assert r.status_code == 200 and r.json()["data"]["tasks"][0]["title"] == "T0"

    fake_llm.fail_when = "Yeh raha requirement"
    r = client.post("/plan", json=REQ)
    assert r.status_code == 503
    body = r.json()
    assert body["success"] is False and body["message"].startswith("The AI service is unavailable right now.")


def test_unexpected_error_is_500_without_internals(client, fake_llm):
    fake_llm.fail_when = "Yeh raha requirement"
    fake_llm.fail_with = KeyError("secret internal detail")
    r = client.post("/plan", json=REQ)
    assert r.status_code == 500
    assert r.json() == {"success": False, "message": "Internal server error."}


def test_unknown_routes_and_ids(client):
    assert client.get("/runs/doesnotexist").status_code == 404
    assert client.get("/runs/bad-id!").status_code == 422
    assert client.get("/nope").json()["success"] is False


# ---- runs ----

def test_run_streams_events_and_is_saved(client):
    r = client.post("/runs", json=REQ)
    assert r.status_code == 202
    run_id = r.json()["data"]["run_id"]

    events = sse_events(client, run_id)
    assert events[0]["event"] == "status"
    assert events[-1] == {"event": "done", "data": {"run_id": run_id}, "id": len(events) - 1}

    # Resume after the second-to-last event: only the final one is replayed
    resumed = sse_events(client, run_id, headers={"Last-Event-ID": str(events[-2]["id"])})
    assert [e["event"] for e in resumed] == ["done"]

    run = client.get(f"/runs/{run_id}").json()["data"]
    assert run["status"] == "done" and run["result"]["plan"]["tasks"][0]["title"] == "T0"

    history = client.get("/runs?limit=5").json()["data"]
    assert history["items"][0]["id"] == run_id and "result" not in history["items"][0]


def test_finished_run_is_served_from_db_after_eviction(client):
    run_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    wait_for(client, run_id, {"done"})
    runs._runs.clear()   # as if evicted from memory / server restarted

    data = client.get(f"/runs/{run_id}").json()["data"]
    assert data["status"] == "done" and data["result"]["tests"]["test_cases"][0]["title"] == "signup works"
    assert client.get(f"/runs/{run_id}/events").status_code == 410


def test_failed_run_records_safe_message(client, fake_llm):
    fake_llm.fail_when = "Task: T0:"
    run_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    events = sse_events(client, run_id)
    assert events[-1]["event"] == "failed"
    assert events[-1]["data"]["message"].startswith("The AI service is unavailable right now.")
    data = wait_for(client, run_id, {"failed"})
    assert data["error"].startswith("The AI service is unavailable right now.")


def test_cancel_running_run(client, fake_llm):
    fake_llm.delay = 1.0
    run_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    time.sleep(0.2)

    r = client.delete(f"/runs/{run_id}")
    assert r.status_code == 202 and r.json()["data"]["status"] == "cancelling"

    events = sse_events(client, run_id)
    assert events[-1]["event"] == "cancelled"
    assert wait_for(client, run_id, {"cancelled"})["error"] == "Cancelled by the user."
    assert "Plan" in fake_llm.cancelled          # the in-flight LLM call was cancelled

    runs._runs.clear()                           # DB has it too
    assert client.get(f"/runs/{run_id}").json()["data"]["status"] == "cancelled"


def test_cancel_finished_or_unknown_run(client):
    run_id = client.post("/runs", json=REQ).json()["data"]["run_id"]
    wait_for(client, run_id, {"done"})
    assert client.delete(f"/runs/{run_id}").status_code == 409
    assert client.delete("/runs/unknown").status_code == 404


def test_too_many_concurrent_runs(client, fake_llm):
    fake_llm.delay = 1.0
    ids = [client.post("/runs", json=REQ).json()["data"]["run_id"] for _ in range(3)]
    r = client.post("/runs", json=REQ)
    assert r.status_code == 429 and r.json()["success"] is False
    for run_id in ids:
        client.delete(f"/runs/{run_id}")
