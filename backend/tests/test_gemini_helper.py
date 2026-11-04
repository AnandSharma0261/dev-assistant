"""Retry / failover rules of gemini_helper._generate, with the model call faked."""

import asyncio

import pytest
from google.genai import errors

import gemini_helper
from schemas import Plan

VALID_PLAN = '{"tasks": [{"id": 1, "title": "t", "description": "d", "priority": "High"}]}'


def api_error(code, status="ERROR"):
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": "boom", "status": status}})


class Resp:
    def __init__(self, text):
        self.text = text


@pytest.fixture
def calls(monkeypatch):
    """Script the model call: a list of exceptions/texts consumed in order."""
    script, seen = [], []

    async def fake_call(model, prompt, config):
        seen.append(model)
        item = script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return Resp(item)

    monkeypatch.setattr(gemini_helper, "_call", fake_call)
    monkeypatch.setattr(gemini_helper, "BACKOFF_BASE", 0)   # no real sleeping
    monkeypatch.setattr(gemini_helper, "MODELS", ["m1", "m2"])
    return script, seen


def run(coro):
    return asyncio.run(coro)


def test_transient_5xx_retries_same_model(calls):
    script, seen = calls
    script += [api_error(503), "hello"]
    assert run(gemini_helper.ask_gemini("x")) == "hello"
    assert seen == ["m1", "m1"]


def test_timeout_and_network_errors_are_retried(calls):
    script, seen = calls
    script += [asyncio.TimeoutError(), ConnectionError(), "hello"]
    assert run(gemini_helper.ask_gemini("x")) == "hello"
    assert seen == ["m1", "m1", "m1"]


def test_404_switches_model(calls):
    script, seen = calls
    script += [api_error(404, "NOT_FOUND"), "hello"]
    assert run(gemini_helper.ask_gemini("x")) == "hello"
    assert seen == ["m1", "m2"]


def test_429_on_every_model_reports_quota(calls):
    script, seen = calls
    script += [api_error(429, "RESOURCE_EXHAUSTED"), api_error(429, "RESOURCE_EXHAUSTED")]
    with pytest.raises(gemini_helper.LLMUnavailable, match="quota"):
        run(gemini_helper.ask_gemini("x"))
    assert seen == ["m1", "m2"]


def test_auth_error_stops_immediately(calls):
    script, seen = calls
    script += [api_error(401, "UNAUTHENTICATED")]
    with pytest.raises(gemini_helper.LLMUnavailable, match="API key"):
        run(gemini_helper.ask_gemini("x"))
    assert seen == ["m1"]


def test_persistent_5xx_moves_on_then_gives_up(calls):
    script, seen = calls
    script += [api_error(500)] * (2 * gemini_helper.TRANSIENT_RETRIES)
    with pytest.raises(gemini_helper.LLMUnavailable, match="unavailable"):
        run(gemini_helper.ask_gemini("x"))
    assert seen == ["m1"] * gemini_helper.TRANSIENT_RETRIES + ["m2"] * gemini_helper.TRANSIENT_RETRIES


def test_invalid_structured_output_is_retried(calls):
    script, seen = calls
    script += ['{"tasks": [{"id": 1}]}', VALID_PLAN]
    plan = run(gemini_helper.ask_gemini_structured("x", Plan))
    assert plan.tasks[0].priority == "High"
    assert seen == ["m1", "m1"]


def test_programming_errors_are_not_retried(calls):
    script, seen = calls
    script += [TypeError("bug in our code")]
    with pytest.raises(TypeError):
        run(gemini_helper.ask_gemini("x"))
    assert seen == ["m1"]


def test_backoff_is_capped_and_jittered():
    values = [gemini_helper._backoff(10) for _ in range(200)]
    assert all(0 <= v <= gemini_helper.BACKOFF_CAP for v in values)
    assert len(set(values)) > 1
