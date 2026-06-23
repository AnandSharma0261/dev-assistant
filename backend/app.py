# ============================================================
#  Phase 6: Backend API (FastAPI)
#  Humare agents/crew ko web ke through use karne layak banata hai.
#
#  Chalane ke liye:
#    venv/bin/uvicorn app:app --reload
#  Phir browser mein kholo:  http://localhost:8000/docs
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Apne agents/crew import karo
from planner import make_plan
from crew import run_crew

# Phase 8: database functions
from database import init_db, save_project, list_projects, get_project


# ---- App banao ----
app = FastAPI(title="Multi-Agent Dev Assistant API")

# App start hote hi database tables bana do (agar nahi hain)
init_db()

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
    return {"status": "ok", "message": "API chal rahi hai 🎉"}


@app.post("/plan")
def plan(body: RequirementIn):
    """Sirf Planner chalata hai (halka/sasta) — requirement se tasks deta hai."""
    result = make_plan(body.requirement)
    return {"success": True, "data": result}


@app.post("/generate")
def generate(body: RequirementIn):
    """
    POORI crew chalata hai (Planner -> Architect -> Developer(RAG) -> Reviewer -> QA).
    NOTE: ye bhaari hai — kai AI calls karta hai, time lagta hai.
    """
    result = run_crew(body.requirement, max_dev_tasks=body.max_dev_tasks)

    # Phase 8: result ko database mein permanently save karo
    project_id = save_project(body.requirement, result)

    return {"success": True, "project_id": project_id, "data": result}


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
