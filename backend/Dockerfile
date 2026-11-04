# ============================================================
#  Backend container ki recipe (Python FastAPI app)
# ============================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # SQLite lives on a mounted volume (see docker-compose), so history survives redeploys
    DATABASE_URL=sqlite:////data/app.db

# Non-root user: if the app is ever compromised, it can't modify the image or system
# (/app must be writable by it too: the RAG index is created in /app/chroma_db)
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app /data && chown app:app /app /data

WORKDIR /app

# Dependencies first (separate layer: code changes don't reinstall libraries)
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app . .
USER app

# Build the RAG index at build time: downloads the embedding model and ingests
# the standards into the image (owned by `app`). At startup ensure_ingested()
# sees a matching hash and skips, so the first request isn't slow.
RUN python -c "import rag; rag.ensure_ingested()"

EXPOSE 8000

# No curl in slim images; use Python to hit /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/health', timeout=4)"

# `exec` replaces the shell, so uvicorn is PID 1 and receives SIGTERM directly
# (graceful shutdown). PORT is set by cloud hosts like Render; default 8000.
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
