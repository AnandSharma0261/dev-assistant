# ============================================================
#  Phase 8: Database (SQLAlchemy)
#  Every run is stored with its status (queued / running / done / failed /
#  cancelled), error and final report, so history survives restarts and
#  failed runs are on record too.
#
#  DATABASE_URL sets the database (default: SQLite file next to this module).
#  Postgres: DATABASE_URL=postgresql://user:pass@host/db (hosts like Render give
#  "postgres://..." URLs; both are accepted and use the psycopg driver).
# ============================================================

import os
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine, func, inspect, select, text, update
from sqlalchemy.orm import declarative_base, sessionmaker

BASE = os.path.dirname(os.path.abspath(__file__))


def _normalise_url(url):
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DB_URL = _normalise_url(os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE, 'app.db')}"))

# check_same_thread=False => SQLite connection ko multiple threads use kar sakein
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
    pool_pre_ping=True,   # survive the DB dropping idle connections (common on hosted Postgres)
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
    # Refinements: the run this one refines, and what the user asked for
    parent_id = Column(String(32), index=True)
    instruction = Column(Text)
    # Anonymous browser session that created the run: scopes history, cancel and refine
    session_id = Column(String(64), index=True)


# Columns added after the first release. create_all() only creates missing
# tables, never missing columns, so add them here. (A bigger project would
# use Alembic migrations; this keeps the demo dependency-free.)
_ADDED_COLUMNS = {"parent_id": "VARCHAR(32)", "instruction": "TEXT", "session_id": "VARCHAR(64)"}


def _add_missing_columns():
    existing = {c["name"] for c in inspect(engine).get_columns("runs")}
    with engine.begin() as conn:
        for name, sql_type in _ADDED_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE runs ADD COLUMN {name} {sql_type}"))


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
    _add_missing_columns()
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


def create_run(run_id, requirement, parent_id=None, instruction=None, session_id=None):
    with SessionLocal.begin() as db:
        db.add(Run(id=run_id, requirement=requirement, status="queued",
                   parent_id=parent_id, instruction=instruction, session_id=session_id))


def run_owner(run_id):
    """Session id that created the run, or None (unknown run / legacy run)."""
    with SessionLocal() as db:
        return db.scalar(select(Run.session_id).where(Run.id == run_id))


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
            "parent_id": r.parent_id,
            "instruction": r.instruction,
            "created_at": _iso(r.created_at),
            "finished_at": _iso(r.finished_at),
        }


def list_runs(session_id, limit=20, offset=0):
    """One session's runs, newest first, without the (large) report column."""
    with SessionLocal() as db:
        mine = Run.session_id == session_id
        total = db.scalar(select(func.count()).select_from(Run).where(mine))
        rows = db.execute(
            select(Run.id, Run.requirement, Run.status, Run.created_at, Run.parent_id, Run.instruction)
            .where(mine)
            .order_by(Run.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    return {
        "items": [
            {"id": r.id, "requirement": r.requirement, "status": r.status, "created_at": _iso(r.created_at),
             "parent_id": r.parent_id, "instruction": r.instruction}
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
