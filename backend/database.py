# ============================================================
#  Phase 8: Database (SQLAlchemy + SQLite)
#  Har processed requirement + uski report ko permanently save karta hai.
# ============================================================

import os
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, Text, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker


BASE = os.path.dirname(os.path.abspath(__file__))

# DB ka "pata". sqlite:///...app.db  => ek file 'app.db' mein sab save hoga.
# (Baad mein Postgres chahiye to sirf ye URL badlega, baaki code same.)
DB_URL = f"sqlite:///{os.path.join(BASE, 'app.db')}"

# engine = database se asli connection
# check_same_thread=False => FastAPI ke multiple requests ke liye zaroori (SQLite ke saath)
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

# SessionLocal = har baar DB se baat karne ke liye ek "session" (baat-cheet) banata hai
SessionLocal = sessionmaker(bind=engine, autoflush=False)

# Base = saari table-models ka parent
Base = declarative_base()


# ---- TABLE MODEL ----
# Ye Python class = database mein 'projects' naam ki table.
# Har attribute = table ka ek column.
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)   # har row ka unique number
    requirement = Column(Text, nullable=False)           # user ne kya maanga
    report = Column(JSON)                                # poori AI report (JSON)
    created_at = Column(DateTime, default=datetime.utcnow)  # kab bani


def init_db():
    """Tables banao (agar pehle se nahi hain). Ek baar app start par chalta hai."""
    Base.metadata.create_all(engine)


def save_project(requirement, report):
    """Ek naya project (requirement + report) DB mein save karo. id wapas do."""
    db = SessionLocal()
    try:
        project = Project(requirement=requirement, report=report)
        db.add(project)       # session mein add karo
        db.commit()           # disk par pakka save (commit)
        db.refresh(project)   # naya id le aao
        return project.id
    finally:
        db.close()            # session band — resource leak na ho


def list_projects():
    """Saare projects ki choti list (naye pehle). Report ke bina (list halki rahe)."""
    db = SessionLocal()
    try:
        rows = db.query(Project).order_by(Project.created_at.desc()).all()
        return [
            {"id": r.id, "requirement": r.requirement, "created_at": str(r.created_at)}
            for r in rows
        ]
    finally:
        db.close()


def get_project(project_id):
    """Ek project ki poori detail (report ke saath) id se nikaalo."""
    db = SessionLocal()
    try:
        r = db.get(Project, project_id)
        if not r:
            return None
        return {
            "id": r.id,
            "requirement": r.requirement,
            "report": r.report,
            "created_at": str(r.created_at),
        }
    finally:
        db.close()
