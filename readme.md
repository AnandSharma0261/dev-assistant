# dev.assistant: a multi-agent dev team

Give it a software requirement in plain language. A team of AI agents plans it,
designs it, writes code, builds a clickable prototype, reviews the code against
your company's coding standards, and writes test cases. You watch each agent
work live.

```
requirement ─▶ Planner ─▶ Architect ─┬─▶ Developer × N ──┬─▶ Reviewer
                                     │   (RAG standards) └─▶ QA
                                     └─▶ Preview (live, sandboxed prototype)
```

**Stack:** FastAPI · Gemini (`google-genai`, async) · ChromaDB (RAG) · SQLAlchemy ·
React + Vite · Server-Sent Events · Docker

## How it works

| Agent | Gets | Produces |
|---|---|---|
| Planner | requirement | prioritised tasks |
| Architect | requirement + plan | tech stack, components, data models, API endpoints |
| Developer × N | task + design + retrieved coding standards | one file per task: `{language, filename, code, notes}` |
| Preview | requirement + plan + design | a single-file HTML/CSS/JS prototype |
| Reviewer | all code + design + the standards used | findings with location, plus a pass/fail check per standard |
| QA | requirement + plan + endpoints + code | test cases with steps and expected results |

Agents whose inputs are ready run concurrently: the Developer tasks and Preview,
then Reviewer and QA. Every structured answer is constrained by a Pydantic schema
passed to Gemini as `response_schema`, then validated again on the server.

## Design decisions

- **Background runs and SSE, not one long request.** `POST /runs` returns `202`
  with a run id right away. Progress streams over Server-Sent Events: updates go
  one way (server to browser), it's plain HTTP, and `EventSource` reconnects on
  its own, resuming from `Last-Event-ID`. Polling would waste requests and lag
  behind. WebSockets would add a two-way channel nobody uses.
- **Asyncio with `TaskGroup`.** All Gemini calls are async. If one parallel task
  fails, its siblings are cancelled so they stop using quota. A semaphore caps
  the number of concurrent LLM calls (`GEMINI_MAX_CONCURRENCY`).
- **Retries by status code.** 5xx, network errors and timeouts retry with
  exponential backoff and jitter. 404 and 429 fail over to the next model.
  Other 4xx errors (bad key, bad request) stop at once. Users see safe messages;
  provider details only go to the logs.
- **RAG that is honest about relevance.** The coding standards are indexed in
  ChromaDB with a local embedding model, so no API quota is spent on
  embeddings. Style rules that apply to every file are always sent. Topical
  rules such as security or error handling are retrieved only within a cosine
  distance threshold. The index is built in the Docker image and checked by
  content hash at startup.
- **Untrusted generated code is isolated.** The preview runs in an
  `<iframe sandbox="allow-scripts">` with no `allow-same-origin`, so it gets an
  opaque origin, plus a CSP that blocks all network access.
- **Runs are persisted.** Status, error and report are stored in the database,
  so history survives restarts. Runs interrupted by a restart are marked failed.

**Known limit:** runs execute inside the API process, which fits a single
instance. Scaling out needs a shared queue and worker (for example Redis with
ARQ or Celery), with events sent over Redis pub/sub.

## API

All responses use one envelope: `{"success": true, "data": ...}` or
`{"success": false, "message": "...", "errors"?: [...]}`, with matching status codes.

| Method | Path | |
|---|---|---|
| GET | `/health` | liveness and RAG index status |
| POST | `/plan` | Planner only (quick) |
| POST | `/runs` | start a full run; returns `202 {run_id}`. Body: `requirement` (10–4000 chars), `max_dev_tasks` (1–5) |
| GET | `/runs` | history, newest first (`limit`, `offset`) |
| GET | `/runs/{id}` | status and full report |
| GET | `/runs/{id}/events` | SSE: `status`, `stage`, then `done`, `failed` or `cancelled` |
| DELETE | `/runs/{id}` | cancel a run in progress, including its in-flight LLM calls |

Interactive docs: http://localhost:8000/docs

## Run it

You need Python 3.11+, Node 20+ and a Gemini API key from https://aistudio.google.com/apikey.

**Docker (simplest)**

```bash
cp backend/.env.example backend/.env   # then put your GEMINI_API_KEY in it
docker compose up --build              # app: http://localhost:3000
```

**Local development**

```bash
# backend
cd backend
python3.12 -m venv venv
venv/bin/pip install -r requirements-dev.txt
cp .env.example .env                   # add GEMINI_API_KEY
venv/bin/uvicorn app:app --reload      # http://localhost:8000

# frontend (new terminal)
cd frontend
npm ci
npm run dev                            # URL is printed (VITE_API_URL defaults to localhost:8000)
```

**Configuration** (`backend/.env`): `GEMINI_API_KEY` (required). Optional:
`GEMINI_MODELS` (fallback order), `GEMINI_MAX_CONCURRENCY`,
`GEMINI_TIMEOUT_SECONDS`, `DATABASE_URL`, `CHROMA_PATH`.

## Tests

```bash
cd backend && venv/bin/python -m pytest
```

The tests swap Gemini for a fake model, so they need no key and make no API
calls. RAG runs for real against a temporary index. They cover retry and
failover rules, RAG retrieval, parallelism and context passing between agents,
cancellation, and the HTTP API (validation, SSE resume, persistence). CI runs
them together with the frontend lint and build and the Docker build.

## Project layout

```
backend/
  app.py            API: routes, validation, error envelope
  runs.py           background runs, SSE streaming, cancellation
  crew.py           orchestrator (dependency graph, parallel stages)
  planner.py architect.py developer.py previewer.py reviewer.py qa.py   agents
  gemini_helper.py  async Gemini client, retries and failover
  schemas.py        Pydantic schemas for every agent's output
  rag.py            ChromaDB ingest and retrieval of coding standards
  database.py       SQLAlchemy models (runs)
  standards/        company coding standards (the RAG source)
  tests/
frontend/src/App.jsx  UI: live pipeline, results, sandboxed preview
```
