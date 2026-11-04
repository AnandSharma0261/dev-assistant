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

from crew import run_crew
from database import save_project

logger = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 15   # comment line so proxies don't close an idle stream
MAX_ACTIVE_RUNS = 3      # each run makes several LLM calls; protect the quota
MAX_STORED_RUNS = 100    # finished runs kept in memory for replay


class TooManyRuns(Exception):
    pass


@dataclass
class Run:
    id: str
    requirement: str
    status: str = "queued"          # queued | running | done | failed
    events: list = field(default_factory=list)
    result: dict | None = None
    project_id: int | None = None
    error: str | None = None
    task: asyncio.Task | None = None
    _changed: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def finished(self):
        return self.status in ("done", "failed")

    def publish(self, event_type, data):
        """Append an event and wake every waiting stream. Must run on the event loop."""
        self.events.append({"type": event_type, "data": data})
        self._changed.set()
        self._changed = asyncio.Event()

    def snapshot(self):
        return {
            "id": self.id,
            "requirement": self.requirement,
            "status": self.status,
            "project_id": self.project_id,
            "error": self.error,
            "result": self.result,
        }


class RunStore:
    def __init__(self):
        self._runs: OrderedDict[str, Run] = OrderedDict()

    def get(self, run_id):
        return self._runs.get(run_id)

    def create(self, requirement, max_dev_tasks):
        """Start a run in the background. Must be called from the event loop."""
        active = sum(1 for r in self._runs.values() if not r.finished)
        if active >= MAX_ACTIVE_RUNS:
            raise TooManyRuns()

        run = Run(id=uuid.uuid4().hex, requirement=requirement)
        self._runs[run.id] = run
        self._evict()
        # Keep a reference to the task, otherwise it can be garbage-collected mid-run
        run.task = asyncio.create_task(self._execute(run, max_dev_tasks))
        return run

    def _evict(self):
        for run_id in list(self._runs):
            if len(self._runs) <= MAX_STORED_RUNS:
                break
            if self._runs[run_id].finished:
                del self._runs[run_id]

    async def _execute(self, run, max_dev_tasks):
        run.status = "running"
        run.publish("status", {"status": "running"})
        try:
            # The crew is async and runs on this event loop, so it can publish directly
            result = await run_crew(run.requirement, max_dev_tasks, on_event=run.publish)
            project_id = await asyncio.to_thread(save_project, run.requirement, result)
        except Exception as e:
            logger.exception("Run %s failed", run.id)
            # Parallel stages run in a TaskGroup, which wraps failures in an ExceptionGroup
            while isinstance(e, ExceptionGroup) and e.exceptions:
                e = e.exceptions[0]
            # RuntimeError is raised by gemini_helper with a user-safe message (quota etc.)
            message = str(e) if isinstance(e, RuntimeError) else "The run failed due to an internal error."
            run.status, run.error = "failed", message
            run.publish("failed", {"message": message})
            return

        run.status, run.result, run.project_id = "done", result, project_id
        run.publish("done", {"project_id": project_id})


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
