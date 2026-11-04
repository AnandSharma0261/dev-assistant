# ============================================================
#  Phase 6: Backend API (FastAPI)
#  Humare agents/crew ko web ke through use karne layak banata hai.
#
#  Chalane ke liye:
#    venv/bin/uvicorn app:app --reload
#  Phir browser mein kholo:  http://localhost:8000/docs
# ============================================================

import asyncio
import hmac
import logging
import os
import re
from contextlib import asynccontextmanager

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.exceptions import HTTPException as StarletteHTTPException

# Apne agents/crew import karo
from planner import make_plan
from runs import ParentNotDone, RunFinished, TooManyRuns, runs, stream_events
from export import build_zip
from crew import REFINE_TARGETS
from gemini_helper import LLMUnavailable
import rag

# Phase 8: database functions
from database import init_db, list_runs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Startup work, run once before the server accepts requests."""
    init_db()   # DB tables bana do (agar nahi hain)
    # Make sure the coding standards are in ChromaDB. Re-ingests only when the
    # standards file changed (content hash), so restarts are cheap. If it fails,
    # the API still starts, but /health reports RAG as down instead of hiding it.
    try:
        await asyncio.to_thread(rag.ensure_ingested)
    except Exception:
        logger.exception("RAG ingest failed; Developer will run without company standards")
    yield


# ---- App banao ----
app = FastAPI(title="Multi-Agent Dev Assistant API", lifespan=lifespan)


# ============================================================
#  RESPONSES & ERRORS
#  Every response uses one envelope, as the company API standard asks:
#    success: {"success": true,  "data": ...}             2xx
#    error:   {"success": false, "message": "...", ...}   4xx / 5xx
#  Error messages are safe to show users; internal details only go to the log.
# ============================================================

def ok(data):
    return {"success": True, "data": data}


def error_response(status_code, message, headers=None, **extra):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, **extra},
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return error_response(exc.status_code, str(exc.detail), headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    errors = [
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
        for e in exc.errors()
    ]
    return error_response(422, "Invalid request.", errors=errors)


@app.exception_handler(LLMUnavailable)
async def llm_unavailable(request, exc):
    return error_response(503, str(exc))


# Registered BEFORE the CORS middleware so CORS stays the outer layer: even
# an unexpected 500 then carries CORS headers and the browser can read it.
@app.middleware("http")
async def catch_unhandled(request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(500, "Internal server error.")


# ---- CORS ----
# In Docker the frontend's nginx proxies /api to this server (same origin, no
# CORS needed). For local development any localhost port is allowed; a
# deployed frontend on another domain is listed in CORS_ORIGINS
# (comma-separated, e.g. https://my-app.vercel.app).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Who is asking ----
# There are no user accounts. Each browser makes a random id once and sends
# it as X-Session-Id (or ?session= where headers can't be set). It scopes
# history, cancel and refine to that browser. Reading one run by its id
# (report, events, ZIP) needs no session: run ids are random UUIDs, so a run
# link works like an unlisted share link.
_SESSION_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")


def session_id(
    x_session_id: Annotated[str | None, Header()] = None,
    session: Annotated[str | None, Query(include_in_schema=False)] = None,
):
    sid = x_session_id or session
    if not sid or not _SESSION_RE.match(sid):
        raise HTTPException(status_code=400, detail="Missing or invalid X-Session-Id header.")
    return sid


Session = Annotated[str, Depends(session_id)]


def _require_owner(run_id, sid):
    # A run you don't own looks the same as one that doesn't exist
    if runs.owner(run_id) != sid:
        raise HTTPException(status_code=404, detail="Run not found.")


def require_admin(x_admin_token: Annotated[str | None, Header()] = None):
    """Changing the coding standards affects every user, so it needs ADMIN_TOKEN."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=403, detail="Uploading standards is disabled on this server (no ADMIN_TOKEN set).")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


# ---- Request ka shape (body kaisa aayega) ----
# Limits protect the Gemini quota: max_dev_tasks drives how many LLM calls a
# run makes, and the requirement text goes into every agent's prompt.
Requirement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)]
RunId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,40}$")]


class RequirementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: Requirement
    max_dev_tasks: int = Field(default=2, ge=1, le=5)   # Developer kitni tasks ka code likhe


class RefineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
    target: Literal[REFINE_TARGETS] = "preview"   # what to regenerate: the prototype or the code


class StandardsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: Annotated[str, StringConstraints(max_length=rag.MAX_DOC_CHARS)]


# ============================================================
#  ENDPOINTS
# ============================================================

@app.get("/health")
def health():
    """Server zinda hai ya nahi — sabse simple check (koi AI call nahi)."""
    return ok({"status": "ok", "rag": rag.status()})


@app.post("/plan")
async def plan(body: RequirementIn):
    """Sirf Planner chalata hai (halka/sasta) — requirement se tasks deta hai."""
    result = await make_plan(body.requirement)   # LLMUnavailable -> 503 via handler
    return ok(result.model_dump())


# ---- Runs: full crew as a background job + live progress over SSE ----

@app.post("/runs", status_code=202)
async def create_run(body: RequirementIn, sid: Session):
    """
    Starts the full crew (Planner -> Architect -> Developer(RAG) ∥ Preview -> Reviewer ∥ QA)
    in the background and returns immediately with a run id.
    Progress: GET /runs/{id}/events (SSE). Final state: GET /runs/{id}.
    """
    try:
        run = await runs.create(body.requirement, body.max_dev_tasks, session_id=sid)
    except TooManyRuns:
        raise HTTPException(status_code=429, detail="Too many runs in progress. Try again shortly.")
    return ok({"run_id": run.id, "status": run.status})


@app.get("/runs")
def list_all_runs(sid: Session, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """This browser's history: runs newest first (without reports), paginated."""
    return ok(list_runs(sid, limit=limit, offset=offset))


@app.get("/runs/{run_id}")
def get_run(run_id: RunId):
    """Current state of a run; `result` holds the report once it is done."""
    snapshot = runs.snapshot(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Run not found.")
    return ok(snapshot)


@app.delete("/runs/{run_id}", status_code=202)
def cancel_run(run_id: RunId, sid: Session):
    """Cancel a queued/running run. Its in-flight Gemini calls are cancelled too."""
    _require_owner(run_id, sid)
    try:
        run = runs.cancel(run_id)
    except RunFinished:
        raise HTTPException(status_code=409, detail="Run has already finished.")
    if not run:
        snapshot = runs.snapshot(run_id)
        if snapshot:   # only in the DB, so it finished (or was interrupted) earlier
            raise HTTPException(status_code=409, detail="Run has already finished.")
        raise HTTPException(status_code=404, detail="Run not found.")
    return ok({"run_id": run.id, "status": "cancelling"})


@app.get("/runs/{run_id}/events")
async def run_events(run_id: RunId, request: Request, last_event_id: str | None = Header(default=None)):
    """
    Server-Sent Events stream of a run's progress.
    Events: status, stage {stage, status: started|progress|done|failed, data},
    and one terminal event: done | failed | cancelled.
    On reconnect, EventSource sends Last-Event-ID and the stream resumes after it.
    """
    run = runs.get(run_id)
    if not run:
        if runs.snapshot(run_id):
            raise HTTPException(status_code=410, detail="Live events are no longer available; use GET /runs/{id}.")
        raise HTTPException(status_code=404, detail="Run not found.")
    start = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0
    return StreamingResponse(
        stream_events(run, start, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/runs/{run_id}/refine", status_code=202)
async def refine(run_id: RunId, body: RefineIn, sid: Session):
    """
    Follow-up on a finished run ("make the buttons round"). Starts a new run that
    reuses the parent's plan and design and regenerates only `target`
    (preview: the prototype; code: every file, then a fresh review).
    Stream it like any run: GET /runs/{new_id}/events.
    """
    try:
        _require_owner(run_id, sid)
        run = await runs.refine(run_id, body.instruction, body.target, session_id=sid)
    except ParentNotDone:
        raise HTTPException(status_code=409, detail="Only a finished, successful run can be refined.")
    except TooManyRuns:
        raise HTTPException(status_code=429, detail="Too many runs in progress. Try again shortly.")
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return ok({"run_id": run.id, "parent_id": run_id, "status": run.status})


@app.get("/runs/{run_id}/download")
def download(run_id: RunId):
    """Everything a finished run produced, as a ZIP: src/, preview/, tests/, design.json, README.md."""
    snapshot = runs.snapshot(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Run not found.")
    if snapshot["status"] != "done" or not snapshot.get("result"):
        raise HTTPException(status_code=409, detail="The run has not finished successfully.")
    return Response(
        content=build_zip(snapshot),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="dev-assistant-{run_id[:8]}.zip"'},
    )


# ---- Company coding standards (the RAG source) ----

@app.get("/standards")
def get_standards():
    """The active standards document (built-in or uploaded) and the rules it was split into.
    `editable` says whether this server accepts uploads (ADMIN_TOKEN is set)."""
    return ok({**rag.describe(), "editable": bool(os.getenv("ADMIN_TOKEN"))})


@app.put("/standards", dependencies=[Depends(require_admin)])
async def upload_standards(body: StandardsIn):
    """
    Replace the coding standards with your own Markdown/text document and re-index it.
    Use "## Heading" per rule; end a heading with "[always]" for rules that apply to every file.
    """
    try:
        info = await asyncio.to_thread(rag.set_custom_standards, body.content)
        return ok({**info, "editable": True})
    except rag.InvalidStandards as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.delete("/standards", dependencies=[Depends(require_admin)])
async def reset_standards():
    """Go back to the built-in standards."""
    return ok({**await asyncio.to_thread(rag.reset_standards), "editable": True})
