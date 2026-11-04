"""
Test setup. No real Gemini calls are made: `fake_llm` replaces the lowest-level
model call (gemini_helper._call) with canned answers, so the real retry,
validation, streaming and metrics code all still runs. RAG runs for real
(local ChromaDB + embedding model) against a throwaway index.
"""

import asyncio
import os
import tempfile
from types import SimpleNamespace

# Must be set before any app module is imported (they read env at import time)
_TMP = tempfile.mkdtemp(prefix="devassistant-tests-")
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["CHROMA_PATH"] = os.path.join(_TMP, "chroma")
os.environ["DATA_DIR"] = os.path.join(_TMP, "data")
# TEST_DATABASE_URL runs the suite against another database (e.g. Postgres)
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ.pop("GEMINI_MODELS", None)

import pytest  # noqa: E402
from google.genai import errors  # noqa: E402

import gemini_helper  # noqa: E402
import rag  # noqa: E402
import schemas as s  # noqa: E402

USAGE = SimpleNamespace(prompt_token_count=100, candidates_token_count=50, thoughts_token_count=None)
SESSION = "test-session-aaaaaaaaaaaa"
OTHER_SESSION = "test-session-bbbbbbbbbbbb"
RAW_PREVIEW = "```html\n<!DOCTYPE html><html><head></head><body>hi</body></html>\n```"


@pytest.fixture(scope="session", autouse=True)
def rag_index():
    rag.ensure_ingested()


def server_error():
    return errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})


class FakeLLM:
    """Stands in for gemini_helper._call. Records every prompt by kind."""

    def __init__(self):
        self.delay = 0.05
        self.prompts = {}            # kind -> [prompt, ...]
        self.fail_when = None        # substring: a prompt containing it raises fail_with
        self.fail_with = server_error()
        self.cancelled = []
        self.preview_html = RAW_PREVIEW
        self.preview_queue = []      # Preview answers returned in order (then preview_html)
        self.reviews = []            # Review objects returned in order (then a clean review)
        self.stream_fail_once = set()  # kinds whose first streamed attempt dies mid-way

    @staticmethod
    def kind(schema, prompt):
        if schema is None:
            return "PreviewRefine" if "USER KA CHANGE REQUEST" in prompt else "Preview"
        if schema is s.CodeOutput and prompt.startswith("Yeh existing file hai"):
            return "Revise"
        return schema.__name__

    async def __call__(self, model, prompt, config, on_text=None):
        kind = self.kind(config.response_schema, prompt)
        self.prompts.setdefault(kind, []).append(prompt)
        failing = self.fail_when is not None and self.fail_when in prompt
        try:
            await asyncio.sleep(0.01 if failing else self.delay)
        except asyncio.CancelledError:
            self.cancelled.append(kind)
            raise
        if failing:
            raise self.fail_with
        text = self.answer(config.response_schema, prompt, kind)
        if on_text:   # stream in three chunks, like the real SDK
            n = len(text)
            for end in (n // 3, 2 * n // 3):
                on_text(text[:end])
            if kind in self.stream_fail_once:
                self.stream_fail_once.discard(kind)
                raise server_error()
            on_text(text)
        return gemini_helper._Result(text, USAGE)

    def answer(self, schema, prompt, kind):
        if kind == "Preview":
            return self.preview_queue.pop(0) if self.preview_queue else self.preview_html
        if kind == "PreviewRefine":
            return "<!DOCTYPE html><html><body>refined</body></html>"
        if schema is s.Plan:
            obj = s.Plan(tasks=[
                s.Task(id=i, title=f"T{i}", description="signup with password hashing", priority="High")
                for i in range(3)
            ])
        elif schema is s.Design:
            obj = s.Design(
                tech_stack=s.TechStack(frontend="React", backend="Python", database="PostgreSQL", other=[]),
                components=[s.Component(name="Auth", responsibility="login/signup")],
                data_models=[s.DataModel(name="User", fields=["email", "password_hash"])],
                api_endpoints=[s.Endpoint(method="POST", path="/signup", purpose="create user")],
            )
        elif kind == "Revise":
            filename = prompt.split("Yeh existing file hai: ", 1)[1].split(" ", 1)[0]
            obj = s.CodeOutput(language="python", filename=filename, code=f'# fixed "{filename}"\n', notes="fixed")
        elif schema is s.CodeOutput:
            task = prompt.split("\n", 1)[0].removeprefix("Task: ").split(":")[0]
            obj = s.CodeOutput(language="python", filename=f"{task.lower()}.py",
                               code=f'# code for {task}\nprint("tab\\there")\n', notes="")
        elif schema is s.Review:
            obj = self.reviews.pop(0) if self.reviews else s.Review(findings=[], standards_check=[], overall_summary="ok")
        elif schema is s.TestSuite:
            obj = s.TestSuite(test_cases=[s.TestCase(id=1, title="signup works", steps=["open", "submit"], expected="ok")])
        else:
            raise AssertionError(f"unexpected schema {schema}")
        return obj.model_dump_json()


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(gemini_helper, "_call", fake)
    monkeypatch.setattr(gemini_helper, "BACKOFF_BASE", 0)
    return fake
