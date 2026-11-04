# ============================================================
#  Background runs + Server-Sent Events.
#
#  POST /runs starts the crew as a background job and returns at once.
#  Every stage the crew reports is appended to the run's event log, and
#  any number of SSE clients can stream that log: they get the events
#  emitted so far and then new ones as they happen. A client that
#  reconnects sends Last-Event-ID and resumes where it stopped.
#
#  Why SSE: updates flow only server -> client, so WebSockets are not
#  needed, and polling would waste requests and lag behind. SSE runs over
#  plain HTTP and EventSource reconnects on its own.
#
#  Limitation: runs live in this process's memory, which suits a single
#  instance. Running several instances would need a shared store and
#  worker (e.g. Redis + ARQ/Celery, events over pub/sub).
# ============================================================

import asyncio
import json
import logging
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from crew import refine_run, run_crew
from database import create_run, get_run, run_owner, update_run
from gemini_helper import LLMUnavailable

logger = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 15   # comment line so proxies don't close an idle stream
MAX_ACTIVE_RUNS = 3      # each run makes several LLM calls; protect the quota
MAX_STORED_RUNS = 100    # finished runs kept in memory for SSE replay (all are in the DB)


class TooManyRuns(Exception):
    pass


class RunFinished(Exception):
    pass


class ParentNotDone(Exception):
    pass


@dataclass
class Run:
    id: str
    requirement: str
    parent_id: str | None = None
    instruction: str | None = None
    session_id: str | None = None   # owner (not exposed in snapshots)
    status: str = "queued"          # queued | running | done | failed | cancelled
    events: list = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    task: asyncio.Task | None = None
    _changed: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def finished(self):
        return self.status in ("done", "failed", "cancelled")

    def publish(self, event_type, data):
        """Append an event and wake every waiting stream. Must run on the event loop."""
        self.events.append({"type": event_type, "data": data})
        self._changed.set()
        self._changed = asyncio.Event()

    def snapshot(self):
        return {
            "id": self.id,
            "requirement": self.requirement,
            "parent_id": self.parent_id,
            "instruction": self.instruction,
            "status": self.status,
            "error": self.error,
            "result": self.result,
        }


def _persist_later(run_id, **fields):
    """Fire-and-forget DB update from synchronous code on the event loop."""
    asyncio.get_running_loop().run_in_executor(None, lambda: update_run(run_id, **fields))


class RunStore:
    def __init__(self):
        self._runs: OrderedDict[str, Run] = OrderedDict()

    def get(self, run_id):
        return self._runs.get(run_id)

    def snapshot(self, run_id):
        """Live state if the run is in memory, otherwise what the database has."""
        run = self._runs.get(run_id)
        return run.snapshot() if run else get_run(run_id)

    def owner(self, run_id):
        run = self._runs.get(run_id)
        return run.session_id if run else run_owner(run_id)

    async def create(self, requirement, max_dev_tasks, session_id=None):
        """Record a full run and start it in the background."""
        return await self._start(
            Run(id=uuid.uuid4().hex, requirement=requirement, session_id=session_id),
            lambda on_event: run_crew(requirement, max_dev_tasks, on_event=on_event),
        )

    async def refine(self, parent_id, instruction, target, session_id=None):
        """Start a refinement of a finished run. Returns None if the parent is unknown."""
        parent = self.snapshot(parent_id)
        if not parent:
            return None
        if parent["status"] != "done" or not parent.get("result"):
            raise ParentNotDone()
        run = Run(id=uuid.uuid4().hex, requirement=parent["requirement"],
                  parent_id=parent_id, instruction=instruction, session_id=session_id)
        return await self._start(
            run, lambda on_event: refine_run(parent["result"], instruction, target, on_event=on_event)
        )

    async def _start(self, run, job):
        active = sum(1 for r in self._runs.values() if not r.finished)
        if active >= MAX_ACTIVE_RUNS:
            raise TooManyRuns()
        await asyncio.to_thread(create_run, run.id, run.requirement, run.parent_id, run.instruction, run.session_id)
        self._runs[run.id] = run
        self._evict()
        # Keep a reference to the task, otherwise it can be garbage-collected mid-run
        run.task = asyncio.create_task(self._execute(run, job))
        run.task.add_done_callback(lambda t: self._on_task_done(run, t))
        return run

    def cancel(self, run_id):
        """Cancel a queued/running run. Returns None if unknown, raises RunFinished if already over."""
        run = self._runs.get(run_id)
        if not run:
            return None
        if run.finished:
            raise RunFinished()
        # Cancelling the task also cancels its TaskGroups, i.e. every in-flight
        # Gemini call. _on_task_done records the outcome.
        run.task.cancel()
        return run

    def _on_task_done(self, run, task):
        # Handles cancellation in one place, including a task cancelled before it
        # ever started (its body, and any except block in it, never runs then).
        if task.cancelled() and not run.finished:
            run.status, run.error = "cancelled", "Cancelled by the user."
            run.publish("cancelled", {"message": run.error})
            _persist_later(run.id, status="cancelled", error=run.error)

    def _evict(self):
        for run_id in list(self._runs):
            if len(self._runs) <= MAX_STORED_RUNS:
                break
            if self._runs[run_id].finished:
                del self._runs[run_id]

    async def _execute(self, run, job):
        run.status = "running"
        run.publish("status", {"status": "running"})
        await asyncio.to_thread(update_run, run.id, status="running")
        try:
            # The crew is async and runs on this event loop, so it can publish directly
            result = await job(run.publish)
        except Exception as e:
            logger.exception("Run %s failed", run.id)
            # Parallel stages run in TaskGroups, which wrap failures in ExceptionGroups
            while isinstance(e, ExceptionGroup) and e.exceptions:
                e = e.exceptions[0]
            # LLMUnavailable carries a user-safe message; anything else stays internal
            message = str(e) if isinstance(e, LLMUnavailable) else "The run failed due to an internal error."
            await asyncio.to_thread(update_run, run.id, status="failed", error=message)
            # Status + terminal event together, with no await in between: a stream
            # that sees the run as finished must also find its final event.
            run.status, run.error = "failed", message
            run.publish("failed", {"message": message})
            return

        await asyncio.to_thread(update_run, run.id, status="done", report=result)
        run.status, run.result = "done", result
        run.publish("done", {"run_id": run.id})


def _format_sse(event_id, event):
    return f"id: {event_id}\nevent: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"


async def stream_events(run, start, is_disconnected):
    """Yield the run's events from index `start` as SSE frames until the run finishes."""
    yield "retry: 3000\n\n"   # EventSource reconnect delay
    idx = start
    while True:
        # Take the waiter before draining, so an event published after the
        # drain still wakes us (nothing can interleave until the next await).
        waiter = run._changed
        while idx < len(run.events):
            yield _format_sse(idx, run.events[idx])
            idx += 1
        if run.finished:
            return
        try:
            await asyncio.wait_for(waiter.wait(), timeout=KEEPALIVE_SECONDS)
        except asyncio.TimeoutError:
            yield ": keep-alive\n\n"
        if await is_disconnected():
            return


runs = RunStore()
