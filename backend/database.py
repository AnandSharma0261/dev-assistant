# ============================================================
#  Phase 8: Database (SQLAlchemy)
#  Every run is stored with its status (queued / running / done / failed /
#  cancelled), error and final report, so history survives restarts and
#  failed runs are on record too.
#
#  DATABASE_URL sets the database (default: SQLite file next to this module).
#  Postgres works with just a different URL.
# ============================================================

import os
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine, func, inspect, select, update
from sqlalchemy.orm import declarative_base, sessionmaker

BASE = os.path.dirname(os.path.abspath(__file__))
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE, 'app.db')}")

# check_same_thread=False => SQLite connection ko multiple threads use kar sakein
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()

FINISHED = ("done", "failed", "cancelled")


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:          # SQLite drops tzinfo; values are stored in UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(32), primary_key=True)
    requirement = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, index=True)
    error = Column(Text)
    report = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    finished_at = Column(DateTime(timezone=True))


class Project(Base):
    """Legacy table (before runs were tracked). Only read once, to migrate old history."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    requirement = Column(Text, nullable=False)
    report = Column(JSON)
    created_at = Column(DateTime)


def init_db():
    """Create tables, migrate legacy history, and close out runs a restart interrupted."""
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if db.scalar(select(func.count()).select_from(Run)) == 0 and inspect(engine).has_table("projects"):
            for p in db.scalars(select(Project)):
                db.add(Run(id=f"legacy{p.id}", requirement=p.requirement, status="done",
                           report=p.report, created_at=p.created_at, finished_at=p.created_at))
        # Runs execute inside the server process, so any run that was still
        # queued/running when the process stopped can never finish.
        db.execute(
            update(Run)
            .where(Run.status.not_in(FINISHED))
            .values(status="failed", error="Interrupted by a server restart.", finished_at=_utcnow())
        )


def create_run(run_id, requirement):
    with SessionLocal.begin() as db:
        db.add(Run(id=run_id, requirement=requirement, status="queued"))


def update_run(run_id, **fields):
    """Set any of: status, error, report. Finishing statuses also stamp finished_at."""
    if fields.get("status") in FINISHED:
        fields["finished_at"] = _utcnow()
    with SessionLocal.begin() as db:
        db.execute(update(Run).where(Run.id == run_id).values(**fields))


def get_run(run_id):
    """One run with its full report, or None."""
    with SessionLocal() as db:
        r = db.get(Run, run_id)
        if not r:
            return None
        return {
            "id": r.id,
            "requirement": r.requirement,
            "status": r.status,
            "error": r.error,
            "result": r.report,
            "created_at": _iso(r.created_at),
            "finished_at": _iso(r.finished_at),
        }


def list_runs(limit=20, offset=0):
    """Newest first, without the (large) report column."""
    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(Run))
        rows = db.execute(
            select(Run.id, Run.requirement, Run.status, Run.created_at)
            .order_by(Run.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    return {
        "items": [
            {"id": r.id, "requirement": r.requirement, "status": r.status, "created_at": _iso(r.created_at)}
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
