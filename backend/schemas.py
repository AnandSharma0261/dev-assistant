# ============================================================
#  Agent output schemas.
#  These Pydantic models are passed to Gemini as `response_schema`, so the
#  model is constrained to this exact shape, and every response is validated
#  again on our side before any agent's output is used.
# ============================================================

from typing import Literal

from pydantic import BaseModel

Level = Literal["High", "Medium", "Low"]


# ---- Planner ----
class Task(BaseModel):
    id: int
    title: str
    description: str
    priority: Level


class Plan(BaseModel):
    tasks: list[Task]

    def as_prompt(self):
        """Compact text form, used as context for the agents that come after."""
        return "\n".join(f"{t.id}. [{t.priority}] {t.title}: {t.description}" for t in self.tasks)


# ---- Architect ----
class TechStack(BaseModel):
    frontend: str
    backend: str
    database: str
    other: list[str]


class Component(BaseModel):
    name: str
    responsibility: str


class DataModel(BaseModel):
    name: str
    fields: list[str]


class Endpoint(BaseModel):
    method: str
    path: str
    purpose: str


class Design(BaseModel):
    tech_stack: TechStack
    components: list[Component]
    data_models: list[DataModel]
    api_endpoints: list[Endpoint]

    def as_prompt(self):
        """Compact text form, used as context for the agents that come after."""
        st = self.tech_stack
        lines = [
            f"Tech stack: frontend={st.frontend}, backend={st.backend}, database={st.database}"
            + (f", other={', '.join(st.other)}" if st.other else ""),
            "Components:",
            *(f"- {c.name}: {c.responsibility}" for c in self.components),
            "Data models:",
            *(f"- {m.name}({', '.join(m.fields)})" for m in self.data_models),
            "API endpoints:",
            *(f"- {e.method} {e.path}: {e.purpose}" for e in self.api_endpoints),
        ]
        return "\n".join(lines)


# ---- Reviewer ----
class Finding(BaseModel):
    issue: str
    severity: Level
    suggestion: str


class Review(BaseModel):
    findings: list[Finding]
    overall_summary: str


# ---- QA ----
class TestCase(BaseModel):
    id: int
    title: str
    steps: list[str]
    expected: str


class TestSuite(BaseModel):
    test_cases: list[TestCase]
