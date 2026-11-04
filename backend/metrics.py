# ============================================================
#  Observability: per-run timeline, LLM calls, tokens and cost.
#
#  The orchestrator opens a RunMetrics for each run and marks which agent is
#  working (agent_scope). gemini_helper records every LLM call into the
#  current RunMetrics. Both use ContextVars: each asyncio task gets a copy of
#  the context when it is created, so parallel agents never mix up their
#  attribution and nothing has to be passed through every function.
# ============================================================

import json
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar

_metrics: ContextVar["RunMetrics | None"] = ContextVar("run_metrics", default=None)
_agent: ContextVar[str] = ContextVar("agent", default="unknown")

# USD per 1M tokens (input, output). Estimates from public price trackers
# (Nov 2026), not Google's official page — override with GEMINI_PRICING, e.g.
#   GEMINI_PRICING={"gemini-3.5-flash": [1.5, 9.0]}
# Free-tier usage is not billed; the cost shown is what the run would cost
# at paid rates.
DEFAULT_PRICING = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.5-flash": (1.50, 9.00),
}


def _pricing():
    try:
        override = json.loads(os.getenv("GEMINI_PRICING", "{}"))
    except json.JSONDecodeError:
        override = {}
    return {**DEFAULT_PRICING, **{k: tuple(v) for k, v in override.items()}}


def call_cost(model, input_tokens, output_tokens):
    price = _pricing().get(model)
    if not price:
        return None   # unknown model (e.g. a "-latest" alias): don't guess
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


class RunMetrics:
    def __init__(self):
        self._t0 = time.perf_counter()
        self.stages = {}   # stage -> {"start_ms", "end_ms"}
        self.calls = []

    def now_ms(self):
        return round((time.perf_counter() - self._t0) * 1000)

    def stage_event(self, stage, status):
        if status == "started":
            self.stages.setdefault(stage, {"start_ms": self.now_ms(), "end_ms": None})
        elif status in ("done", "failed") and stage in self.stages:
            self.stages[stage]["end_ms"] = self.now_ms()

    def record_call(self, *, start_ms, model, attempts, ok, input_tokens=0, output_tokens=0):
        self.calls.append({
            "agent": _agent.get(),
            "model": model,
            "start_ms": start_ms,
            "duration_ms": self.now_ms() - start_ms,
            "attempts": attempts,
            "ok": ok,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": call_cost(model, input_tokens, output_tokens) if ok else 0.0,
        })

    def summary(self):
        stages = [
            {"stage": s, "start_ms": v["start_ms"], "end_ms": v["end_ms"]}
            for s, v in sorted(self.stages.items(), key=lambda kv: kv[1]["start_ms"])
        ]
        busy_ms = sum((s["end_ms"] or 0) - s["start_ms"] for s in stages if s["end_ms"] is not None)
        costs = [c["cost_usd"] for c in self.calls if c["cost_usd"] is not None]
        total_ms = self.now_ms()
        return {
            "total_ms": total_ms,
            # Sum of stage durations = how long it would take if stages ran one after another
            "sequential_ms": busy_ms,
            "speedup": round(busy_ms / total_ms, 2) if total_ms else None,
            "stages": stages,
            "llm_calls": self.calls,
            "totals": {
                "calls": len(self.calls),
                "retries": sum(c["attempts"] - 1 for c in self.calls),
                "input_tokens": sum(c["input_tokens"] for c in self.calls),
                "output_tokens": sum(c["output_tokens"] for c in self.calls),
                # None if any call used a model without known pricing
                "cost_usd": round(sum(costs), 6) if len(costs) == len(self.calls) else None,
            },
        }


def current():
    return _metrics.get()


def start_run():
    """Begin collecting for the current task (and the tasks it creates)."""
    m = RunMetrics()
    _metrics.set(m)
    return m


@contextmanager
def agent_scope(name):
    """LLM calls made inside this block are attributed to agent `name`."""
    token = _agent.set(name)
    try:
        yield
    finally:
        _agent.reset(token)
