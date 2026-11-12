# dev.assistant

A small "dev team" made of AI agents.

You type what you want to build in plain English. The agents plan it, design it,
write the code, make a clickable prototype, review the code against your team's
coding standards, fix what the review found and write test cases. You can watch
each agent work live in the browser, code included. When it's done you can ask
for changes ("make the buttons round") and download everything as a ZIP.

Live demo: https://dev-assistant-two.vercel.app

```
requirement -> Planner -> Architect -+-> Developer (one per task) -+-> Reviewer -> Fix -> Re-review
                                     |                             +-> QA
                                     +-> Preview (clickable prototype)
```

Built with FastAPI, Gemini (`google-genai`), ChromaDB, SQLAlchemy, React + Vite,
Server-Sent Events and Docker.

## How it works

| Agent | Input | Output |
|---|---|---|
| Planner | your requirement | a list of tasks, by priority |
| Architect | requirement + plan | tech stack, components, data models, API endpoints |
| Developer | one task + the design + matching coding standards | one code file per task |
| Preview | requirement + plan + design | a single HTML/CSS/JS file you can click around in |
| Reviewer | all the code + design + standards | issues found (file, where, how to fix) and a pass/fail per standard |
| Fix | files with High or Medium issues | corrected files, which the Reviewer checks again |
| QA | requirement + plan + endpoints + code | test cases with steps and expected results |

Agents that don't depend on each other run at the same time. All Developer tasks
and the Preview run together, and later the Reviewer and QA run together.

Gemini is asked to reply in a fixed JSON shape (a Pydantic schema), and the
server checks the reply again before using it.

## Features

- **Fixes its own mistakes.** If the Reviewer finds High or Medium issues, those
  files go back to the Developer along with the issues. Then the Reviewer checks
  the new code against its own earlier list instead of starting over. This only
  happens once per run so cost and time stay in check.
- **Refine.** After a run finishes you can ask for a change to the prototype or
  the code. It reuses the old plan and design and only redoes that part.
- **Live output.** Code and the prototype show up in the browser while the model
  is still writing them.
- **Run stats.** Every LLM call is logged with its model, retries, time and
  tokens. The UI shows a timeline of the run, how much time running agents in
  parallel saved, and a rough cost.
- **ZIP download.** Code, prototype, tests, design and a Markdown report. File
  names from the model are cleaned up so something like `../` can't write
  outside the folder.
- **Your own coding standards.** Upload a Markdown file and the agents will use
  it. Since this changes things for everyone on the server, it needs an admin
  token.
- **UI.** The agents are drawn as a graph with live timers. Past runs are in a
  sidebar. The run id is in the URL, so refreshing keeps your run and you can
  share the link. Light and dark themes.

## Why I built it this way

- **Runs happen in the background.** Starting a run returns a run id right away,
  and progress comes in over Server-Sent Events. Updates only go from server to
  browser, so SSE was enough. The browser also reconnects on its own if the
  connection drops. Polling would be slower and WebSockets weren't needed.
- **Parallel calls with asyncio.** If one agent fails, the others running with
  it get cancelled so they don't keep using API quota. There's also a limit on
  how many Gemini calls can run at once.
- **Retries depend on the error.** Server errors and timeouts are retried with
  backoff. Rate limits (429) switch to the next Gemini model. A bad key or bad
  request fails right away, since retrying won't help.
- **RAG only sends rules that match.** Coding standards are stored in ChromaDB
  with a local embedding model, so embeddings don't cost API quota. General
  style rules go with every file. Topic rules like security or error handling
  are only sent when they actually match the task.
- **The prototype is sandboxed.** It's generated code, so it runs in a sandboxed
  iframe with no network access.
- **Runs are saved in the database,** so history survives a restart.
- **No login.** Each browser gets a random session id. You can only see, cancel
  or refine your own runs. Anyone with a run's link can view it, which works as
  a share link.

One limit: runs live inside the API process, so run **one** uvicorn worker.
Running more would need a shared queue (Redis with Celery or ARQ, for example).

## API

Responses look like `{"success": true, "data": ...}` or
`{"success": false, "message": "..."}`. Most calls need an `X-Session-Id`
header. Changing the standards needs `X-Admin-Token`.

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | server and RAG status |
| POST | `/plan` | run only the Planner |
| POST | `/runs` | start a run, returns `run_id` |
| GET | `/runs` | your past runs |
| GET | `/runs/{id}` | status and full report |
| GET | `/runs/{id}/events` | live progress (SSE) |
| DELETE | `/runs/{id}` | cancel a run |
| POST | `/runs/{id}/refine` | ask for a change to a finished run |
| GET | `/runs/{id}/download` | ZIP of the results |
| GET / PUT / DELETE | `/standards` | view, upload or reset coding standards |

Full docs at http://localhost:8000/docs once the backend is running.

## Running it

You need Python 3.11+, Node 20+ and a Gemini API key
(https://aistudio.google.com/apikey).

**With Docker**

```bash
cp backend/.env.example backend/.env   # add your GEMINI_API_KEY
docker compose up --build              # open http://localhost:3000
```

**Without Docker**

```bash
# backend
cd backend
python3.12 -m venv venv
venv/bin/pip install -r requirements-dev.txt
cp .env.example .env                   # add your GEMINI_API_KEY
venv/bin/uvicorn app:app --reload      # http://localhost:8000

# frontend, in another terminal
cd frontend
npm ci
npm run dev
```

Only `GEMINI_API_KEY` is required. See `backend/.env.example` for the other
settings (admin token, model order, database URL and so on).

The cost shown in the UI is an estimate. Check Google's pricing page for real
numbers.

## Deploying

I run the backend on Render and the frontend on Vercel.

- **Backend:** deploy `backend/` with its Dockerfile and set `GEMINI_API_KEY`.
  Use Postgres for `DATABASE_URL`, because Render has no persistent disk and a
  SQLite file gets wiped on every deploy. Keep one instance with one worker.
- **Frontend:** build with `VITE_API_URL=https://<your-backend>` and add the
  frontend URL to `CORS_ORIGINS` on the backend.

## Tests

```bash
cd backend && venv/bin/python -m pytest
```

The tests use a fake Gemini, so no API key is needed. Only the lowest-level
model call is faked, so the real retry, streaming, validation and RAG code still
runs. GitHub Actions runs the tests, the frontend lint and build, and the
Docker build on every push.

## Folder structure

```
backend/
  app.py            API routes
  runs.py           background runs, SSE, cancel
  crew.py           runs the agents in order and in parallel
  planner.py, architect.py, developer.py, previewer.py, reviewer.py, qa.py
  gemini_helper.py  Gemini client, retries, model fallback
  rag.py            coding standards in ChromaDB
  schemas.py        output format for each agent
  streaming.py      live code streaming
  metrics.py        tokens, timing, cost
  export.py         report and ZIP
  database.py       saved runs
  standards/        default coding standards
  tests/
frontend/src/
  App.jsx           start, watch, cancel and refine a run
  components/       agent graph, result tabs, live preview, history, timeline
```
