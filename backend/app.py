# ============================================================
#  Phase 6: Backend API (FastAPI)
#  Humare agents/crew ko web ke through use karne layak banata hai.
#
#  Chalane ke liye:
#    venv/bin/uvicorn app:app --reload
#  Phir browser mein kholo:  http://localhost:8000/docs
# ============================================================

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Apne agents/crew import karo
from planner import make_plan
from runs import TooManyRuns, runs, stream_events
import rag

# Phase 8: database functions
from database import init_db, list_projects, get_project

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

# ---- CORS ----
# Browser security ke kaaran, frontend (alag port par) ko backend call karne ki
# permission chahiye. CORS middleware wahi permission deta hai.
# (Abhi development ke liye sabko allow kar rahe hain; production mein limit karenge.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Request ka shape (body kaisa aayega) ----
# Pydantic model = FastAPI ko batata hai input mein kya-kya hona chahiye.
# Galat input aaya to FastAPI khud saaf error de deta hai.
class RequirementIn(BaseModel):
    requirement: str
    max_dev_tasks: int = 2   # default 2 (Developer kitni tasks ka code likhe)


# ============================================================
#  ENDPOINTS
# ============================================================

@app.get("/health")
def health():
    """Server zinda hai ya nahi — sabse simple check (koi AI call nahi)."""
    return {"status": "ok", "message": "API chal rahi hai 🎉", "rag": rag.status()}


@app.post("/plan")
async def plan(body: RequirementIn):
    """Sirf Planner chalata hai (halka/sasta) — requirement se tasks deta hai."""
    try:
        result = await make_plan(body.requirement)
        return {"success": True, "data": result.model_dump()}
    except Exception as e:
        # Error ko crash banane ki jagah saaf message do (CORS header ke saath jaayega)
        return {"success": False, "message": str(e)}


# ---- Runs: full crew as a background job + live progress over SSE ----

@app.post("/runs", status_code=202)
async def create_run(body: RequirementIn):
    """
    Starts the full crew (Planner -> Architect -> Developer(RAG) -> Reviewer -> QA)
    in the background and returns immediately with a run id.
    Progress: GET /runs/{id}/events (SSE). Final state: GET /runs/{id}.
    """
    try:
        run = runs.create(body.requirement, body.max_dev_tasks)
    except TooManyRuns:
        raise HTTPException(status_code=429, detail="Too many runs in progress. Try again shortly.")
    return {"run_id": run.id, "status": run.status}


def _get_run_or_404(run_id):
    run = runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    """Current state of a run (the result is included once it is done)."""
    return _get_run_or_404(run_id).snapshot()


@app.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, last_event_id: str | None = Header(default=None)):
    """
    Server-Sent Events stream of a run's progress.
    Events: status, stage {stage, status: started|progress|done, data}, done, failed.
    On reconnect, EventSource sends Last-Event-ID and the stream resumes after it.
    """
    run = _get_run_or_404(run_id)
    start = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0
    return StreamingResponse(
        stream_events(run, start, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- History endpoints (Phase 8) ----

@app.get("/history")
def history():
    """Saare purane projects ki list (naye pehle)."""
    return {"success": True, "data": list_projects()}


@app.get("/history/{project_id}")
def history_detail(project_id: int):
    """Ek purane project ki poori report id se."""
    project = get_project(project_id)
    if not project:
        return {"success": False, "message": "Project nahi mila"}
    return {"success": True, "data": project}
