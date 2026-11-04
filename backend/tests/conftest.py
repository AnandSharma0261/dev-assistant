"""
Test setup. No real Gemini calls are made: `fake_llm` replaces the model call
with canned, schema-valid answers. RAG runs for real (local ChromaDB +
embedding model) against a throwaway index, so its behaviour is covered too.
"""

import asyncio
import os
import tempfile

# Must be set before any app module is imported (they read env at import time)
_TMP = tempfile.mkdtemp(prefix="devassistant-tests-")
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["CHROMA_PATH"] = os.path.join(_TMP, "chroma")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"

import pytest  # noqa: E402

import gemini_helper  # noqa: E402
import rag  # noqa: E402
import schemas  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def rag_index():
    rag.ensure_ingested()


class FakeLLM:
    """Stands in for gemini_helper._generate. Records every prompt by kind."""

    def __init__(self, delay=0.05):
        self.delay = delay
        self.prompts = {}          # kind -> [prompt, ...]
        self.fail_when = None      # substring: a prompt containing it raises
        self.fail_with = gemini_helper.LLMUnavailable("The AI service is unavailable right now.")
        self.cancelled = []
        self.preview_html = "```html\n<!DOCTYPE html><html><head></head><body>hi</body></html>\n```"

    @staticmethod
    def kind(schema):
        return schema.__name__ if schema else "Preview"

    async def __call__(self, prompt, system_instruction=None, schema=None):
        kind = self.kind(schema)
        self.prompts.setdefault(kind, []).append(prompt)
        failing = self.fail_when is not None and self.fail_when in prompt
        try:
            await asyncio.sleep(0.01 if failing else self.delay)
        except asyncio.CancelledError:
            self.cancelled.append(kind)
            raise
        if failing:
            raise self.fail_with
        return self.answer(schema, prompt)

    def answer(self, schema, prompt):
        s = schemas
        if schema is s.Plan:
            return s.Plan(tasks=[
                s.Task(id=i, title=f"T{i}", description="signup with password hashing", priority="High")
                for i in range(3)
            ])
        if schema is s.Design:
            return s.Design(
                tech_stack=s.TechStack(frontend="React", backend="Python", database="PostgreSQL", other=[]),
                components=[s.Component(name="Auth", responsibility="login/signup")],
                data_models=[s.DataModel(name="User", fields=["email", "password_hash"])],
                api_endpoints=[s.Endpoint(method="POST", path="/signup", purpose="create user")],
            )
        if schema is s.CodeOutput:
            task = prompt.split("\n", 1)[0].removeprefix("Task: ").split(":")[0]
            return s.CodeOutput(language="python", filename=f"{task.lower()}.py", code=f"# code for {task}", notes="")
        if schema is s.Review:
            return s.Review(findings=[], standards_check=[], overall_summary="ok")
        if schema is s.TestSuite:
            return s.TestSuite(test_cases=[])
        return self.preview_html


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(gemini_helper, "_generate", fake)
    return fake
