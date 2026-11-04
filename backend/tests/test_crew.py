"""Orchestrator: parallelism, context passing between agents, failure handling."""

import asyncio
import time

import pytest

import crew


def run_crew(**kw):
    events = []
    result = asyncio.run(crew.run_crew("todo app with login", max_dev_tasks=2,
                                       on_event=lambda t, d: events.append(d), **kw))
    return result, events


def test_independent_agents_run_in_parallel(fake_llm):
    fake_llm.delay = 0.3
    start = time.perf_counter()
    run_crew()
    elapsed = time.perf_counter() - start
    # 7 LLM calls (no fix round); sequential would be ~2.1s. Critical path is 4 steps (~1.2s).
    assert elapsed < 2.0, elapsed


def test_each_agent_gets_upstream_context(fake_llm):
    result, _ = run_crew()
    p = fake_llm.prompts

    assert "[High] T0: signup" in p["Design"][0]                     # Architect <- plan
    dev = p["CodeOutput"][0]
    assert "POST /signup" in dev and "User(email, password_hash)" in dev  # Developer <- design
    assert "Security Rules" in dev                                   # Developer <- RAG
    review = p["Review"][0]
    assert "PROJECT DESIGN" in review and "Security Rules" in review  # Reviewer <- design + standards
    assert "t0.py" in review                                         # Reviewer <- code (by filename)
    qa = p["TestSuite"][0]
    assert "PLANNED TASKS" in qa and "POST /signup" in qa and "GENERATED CODE" in qa
    assert "PLANNED TASKS" in p["Preview"][0]                        # Preview <- plan + design

    assert [d["task"] for d in result["dev_outputs"]] == ["T0", "T1"]  # plan order kept
    assert result["dev_outputs"][0]["language"] == "python"
    assert result["preview"]["html"].startswith("<!DOCTYPE html>")    # fences stripped
    assert result["self_correction"] is None                         # clean review: no fix round


def test_stage_events_cover_every_agent(fake_llm):
    _, events = run_crew()
    done = {e["stage"] for e in events if e["status"] == "done"}
    assert done == {"planner", "architect", "developer", "preview", "reviewer", "fix", "qa"}
    assert sum(1 for e in events if e["stage"] == "developer" and e["status"] == "progress") == 2


def test_failed_task_cancels_its_siblings(fake_llm):
    fake_llm.delay = 0.5
    fake_llm.fail_when = "Task: T1:"
    with pytest.raises(ExceptionGroup):
        run_crew()
    # The other Developer task and the Preview were still running and got cancelled
    assert sorted(fake_llm.cancelled) == ["CodeOutput", "Preview"]


def test_preview_failure_does_not_fail_the_run(fake_llm):
    fake_llm.preview_html = "sorry, no html here"
    result, events = run_crew()
    assert result["preview"] is None
    assert {"stage": "preview", "status": "failed"}.items() <= next(
        e for e in events if e["stage"] == "preview" and e["status"] == "failed").items()
