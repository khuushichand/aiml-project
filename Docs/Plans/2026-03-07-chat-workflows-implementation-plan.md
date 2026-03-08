# Chat Workflows Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a first-class Chat Workflows feature with saved linear templates, runtime-generated drafts, structured Q&A persistence, explicit context attachments, and an optional free-chat handoff after completion.

**Architecture:** Add a dedicated backend `Chat Workflows` domain instead of bending the generic Workflows engine into an interactive interview runtime. Persist template/run/answer state in a dedicated DB adapter, route question phrasing through existing Chat orchestration with safe fallback to stock questions, and expose a focused web UI in the shared `apps/packages/ui` package with a library, builder, generated-draft flow, and run screen.

**Tech Stack:** FastAPI, Pydantic v2, existing AuthNZ claim-first dependencies, SQLite/PostgreSQL DB abstractions, existing Chat orchestration helpers, React, Zustand, TanStack Query, Ant Design, Vitest, pytest, Bandit.

---

### Task 0: Isolated Worktree Preflight (Required)

Use `@superpowers:using-git-worktrees` before changing code. Execute each implementation task with `@superpowers:test-driven-development`, and close the full plan with `@superpowers:verification-before-completion`.

**Files:**
- Verify only: git worktree metadata and branch state

**Step 1: Create an isolated worktree**

Run:

```bash
git worktree add .worktrees/chat-workflows -b codex/chat-workflows
```

Expected: a new worktree exists at `.worktrees/chat-workflows` on branch `codex/chat-workflows`.

**Step 2: Enter the worktree and verify isolation**

Run:

```bash
cd .worktrees/chat-workflows && git branch --show-current && git rev-parse --show-toplevel
```

Expected:
- branch is `codex/chat-workflows`
- repo root is the worktree path, not the primary workspace

**Step 3: Verify the backend/frontend test harness starts clean**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Workflows/test_workflows_db.py -k schema
```

Expected: the existing workflows DB tests still pass in the isolated worktree.

### Task 1: Add the Chat Workflows persistence foundation

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/ChatWorkflows_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/db_path_utils.py`
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Test: `tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_db.py`

**Step 1: Write the failing DB tests**

```python
import json

from tldw_Server_API.app.core.DB_Management.ChatWorkflows_DB import ChatWorkflowsDatabase


def test_chat_workflows_db_persists_template_and_run_snapshot(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")
    template_id = db.create_template(
        tenant_id="default",
        user_id="user-1",
        title="Discovery Interview",
        description="Collect onboarding answers",
        version=1,
    )
    db.replace_template_steps(
        template_id,
        [
            {
                "step_index": 0,
                "label": "Goal",
                "base_question": "What outcome do you want?",
                "question_mode": "stock",
                "context_refs_json": "[]",
            }
        ],
    )
    run_id = db.create_run(
        tenant_id="default",
        user_id="user-1",
        template_id=template_id,
        template_version=1,
        source_mode="saved_template",
        status="active",
        template_snapshot={"title": "Discovery Interview", "steps": [{"base_question": "What outcome do you want?"}]},
        selected_context_refs=[],
        resolved_context_snapshot=[],
    )

    run = db.get_run(run_id)
    assert run["template_version"] == 1
    assert json.loads(run["template_snapshot_json"])["steps"][0]["base_question"] == "What outcome do you want?"


def test_add_answer_is_unique_per_run_step(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")
    run_id = db.create_run(
        tenant_id="default",
        user_id="user-1",
        template_id=None,
        template_version=1,
        source_mode="generated_draft",
        status="active",
        template_snapshot={"steps": [{"id": "step-1", "base_question": "Why?"}]},
        selected_context_refs=[],
        resolved_context_snapshot=[],
    )
    db.add_answer(
        run_id=run_id,
        step_id="step-1",
        step_index=0,
        displayed_question="Why?",
        answer_text="Because.",
        question_generation_meta={},
    )

    answers = db.list_answers(run_id)
    assert len(answers) == 1
    assert answers[0]["answer_text"] == "Because."
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_db.py
```

Expected: FAIL because the DB adapter does not exist yet.

**Step 3: Write the minimal DB implementation**

Create `ChatWorkflows_DB.py` with:

```python
class ChatWorkflowsDatabase:
    def __init__(self, client_id: str, db_path: Path | str | None = None, backend: DatabaseBackend | None = None):
        ...

    def create_template(self, *, tenant_id: str, user_id: str, title: str, description: str | None, version: int) -> int:
        ...

    def replace_template_steps(self, template_id: int, steps: list[dict[str, Any]]) -> None:
        ...

    def create_run(self, *, tenant_id: str, user_id: str, template_id: int | None, template_version: int, source_mode: str, status: str, template_snapshot: dict[str, Any], selected_context_refs: list[dict[str, Any]], resolved_context_snapshot: list[dict[str, Any]]) -> str:
        ...

    def add_answer(self, *, run_id: str, step_id: str, step_index: int, displayed_question: str, answer_text: str, question_generation_meta: dict[str, Any]) -> None:
        ...
```

Back the adapter with dedicated tables:
- `chat_workflow_templates`
- `chat_workflow_template_steps`
- `chat_workflow_runs`
- `chat_workflow_answers`
- `chat_workflow_run_events`

Also update:
- `db_path_utils.py` with `get_chat_workflows_db_path(user_id)`
- `DB_Manager.py` with `create_chat_workflows_database(...)`

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_db.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChatWorkflows_DB.py \
        tldw_Server_API/app/core/DB_Management/db_path_utils.py \
        tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_db.py
git commit -m "feat(chat-workflows): add persistence foundation"
```

### Task 2: Add request/response schemas and dependency injection

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/chat_workflows.py`
- Create: `tldw_Server_API/app/api/v1/API_Deps/chat_workflows_deps.py`
- Test: `tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_schemas.py`
- Test: `tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_deps.py`

**Step 1: Write the failing schema and dependency tests**

```python
import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.chat_workflows import GenerateDraftRequest


def test_generate_draft_request_requires_goal():
    req = GenerateDraftRequest(goal="Plan my migration", desired_step_count=4, context_refs=[])
    assert req.goal == "Plan my migration"
    assert req.desired_step_count == 4


def test_answer_request_rejects_empty_answer():
    from tldw_Server_API.app.api.v1.schemas.chat_workflows import SubmitAnswerRequest

    with pytest.raises(ValidationError):
        SubmitAnswerRequest(step_index=0, answer_text="  ")
```

```python
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import chat_workflows_deps as deps


def test_chat_workflows_user_claims_permissions(monkeypatch):
    async def fake_get_request_user(request, api_key=None, token=None, legacy_token_header=None):
        return type("User", (), {
            "id": 7,
            "username": "workflow-user",
            "roles": ["user"],
            "permissions": ["chat_workflows.run", "chat_workflows.write"],
            "is_admin": False,
        })()

    monkeypatch.setattr(deps, "get_request_user", fake_get_request_user, raising=True)

    app = FastAPI()

    @app.get("/cw/me")
    async def me(ctx=Depends(deps.get_chat_workflows_user)):
        return ctx

    client = TestClient(app)
    response = client.get("/cw/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert "chat_workflows.run" in response.json()["permissions"]
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_schemas.py tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_deps.py
```

Expected: FAIL because the schema and dependency modules do not exist yet.

**Step 3: Write the minimal schema and dependency implementation**

Create Pydantic models for:
- `ChatWorkflowTemplateCreate`
- `ChatWorkflowTemplateUpdate`
- `ChatWorkflowTemplateStep`
- `GenerateDraftRequest`
- `GenerateDraftResponse`
- `StartRunRequest`
- `SubmitAnswerRequest`
- `ContinueChatResponse`

Example minimal shape:

```python
class SubmitAnswerRequest(BaseModel):
    step_index: int = Field(ge=0)
    answer_text: str = Field(min_length=1)
    idempotency_key: str | None = None

    @field_validator("answer_text")
    @classmethod
    def _strip_answer(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("answer_text must not be empty")
        return stripped
```

Model `get_chat_workflows_user(...)` after `prompt_studio_deps.py`:
- resolve the request user with existing auth headers
- expose `user_id`, `client_id`, `is_admin`, and `permissions`
- use test-mode shortcuts only where existing patterns already allow them

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_schemas.py tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_deps.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_workflows.py \
        tldw_Server_API/app/api/v1/API_Deps/chat_workflows_deps.py \
        tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_schemas.py \
        tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_deps.py
git commit -m "feat(chat-workflows): add schemas and auth deps"
```

### Task 3: Add the core Chat Workflows service and question renderer

**Files:**
- Create: `tldw_Server_API/app/core/Chat_Workflows/__init__.py`
- Create: `tldw_Server_API/app/core/Chat_Workflows/question_renderer.py`
- Create: `tldw_Server_API/app/core/Chat_Workflows/service.py`
- Test: `tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_service.py`

**Step 1: Write the failing service tests**

```python
from tldw_Server_API.app.core.Chat_Workflows.service import ChatWorkflowService


def test_start_run_uses_template_snapshot(fake_chat_workflows_db):
    service = ChatWorkflowService(db=fake_chat_workflows_db, question_renderer=None)
    run = service.start_run(
        tenant_id="default",
        user_id="user-1",
        template={
            "id": 10,
            "version": 3,
            "steps": [{"id": "goal", "step_index": 0, "base_question": "What do you want?", "question_mode": "stock"}],
        },
        source_mode="saved_template",
        selected_context_refs=[],
    )
    assert run["template_version"] == 3
    assert run["current_step_index"] == 0


def test_renderer_falls_back_to_base_question_on_error(fake_chat_workflows_db):
    class FailingRenderer:
        async def render_question(self, **kwargs):
            raise RuntimeError("provider offline")

    service = ChatWorkflowService(db=fake_chat_workflows_db, question_renderer=FailingRenderer())
    question = service._render_question_sync(
        step={"base_question": "What is your goal?", "question_mode": "llm_phrased"},
        prior_answers=[],
        context_snapshot=[],
    )
    assert question["displayed_question"] == "What is your goal?"
    assert question["fallback_used"] is True
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_service.py
```

Expected: FAIL because the service and renderer do not exist.

**Step 3: Write the minimal service implementation**

Create:

```python
class ChatWorkflowQuestionRenderer:
    async def render_question(
        self,
        *,
        base_question: str,
        phrasing_instructions: str | None,
        prior_answers: list[dict[str, Any]],
        context_snapshot: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        ...


class ChatWorkflowService:
    def __init__(self, db: ChatWorkflowsDatabase, question_renderer: ChatWorkflowQuestionRenderer | None):
        ...

    def start_run(...):
        ...

    def generate_draft(...):
        ...

    def get_current_step(...):
        ...

    def record_answer(...):
        ...
```

Implementation rules:
- never read live template data after run start; use `template_snapshot_json`
- `llm_phrased` steps call the renderer and fall back to `base_question` if rendering fails
- generated-draft mode normalizes the LLM output into the same step shape used by saved templates
- reject stale/future step submissions in `record_answer(...)`

Use existing chat orchestration primitives rather than calling the HTTP endpoint internally.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_service.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat_Workflows/__init__.py \
        tldw_Server_API/app/core/Chat_Workflows/question_renderer.py \
        tldw_Server_API/app/core/Chat_Workflows/service.py \
        tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_service.py
git commit -m "feat(chat-workflows): add service and renderer"
```

### Task 4: Add the FastAPI endpoints, permission constants, and router wiring

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/chat_workflows.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/permissions.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_api.py`
- Test: `tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_permissions.py`

**Step 1: Write the failing endpoint and permission tests**

```python
def test_chat_workflow_run_can_complete_and_continue_to_chat(client, monkeypatch):
    template_resp = client.post(
        "/api/v1/chat-workflows/templates",
        json={
            "title": "Discovery",
            "description": "Collect context",
            "steps": [
                {"id": "goal", "step_index": 0, "label": "Goal", "base_question": "What is your goal?", "question_mode": "stock", "context_refs": []}
            ],
        },
    )
    template_id = template_resp.json()["id"]

    run_resp = client.post("/api/v1/chat-workflows/runs", json={"template_id": template_id, "selected_context_refs": []})
    run_id = run_resp.json()["run_id"]

    answer_resp = client.post(f"/api/v1/chat-workflows/runs/{run_id}/answer", json={"step_index": 0, "answer_text": "Ship a feature"})
    assert answer_resp.status_code == 200
    assert answer_resp.json()["status"] == "completed"

    continue_resp = client.post(f"/api/v1/chat-workflows/runs/{run_id}/continue-chat")
    assert continue_resp.status_code == 200
    assert continue_resp.json()["conversation_id"]
```

```python
def test_chat_workflows_run_endpoint_forbidden_without_permission(client):
    response = client.post("/api/v1/chat-workflows/runs", json={"template_id": 1, "selected_context_refs": []})
    assert response.status_code == 403
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_api.py tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_permissions.py
```

Expected: FAIL because the router is not registered.

**Step 3: Write the minimal API implementation**

Add permission constants:

```python
CHAT_WORKFLOWS_READ = "chat_workflows.read"
CHAT_WORKFLOWS_WRITE = "chat_workflows.write"
CHAT_WORKFLOWS_RUN = "chat_workflows.run"
```

Create routes for:
- template CRUD
- `POST /generate-draft`
- `POST /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/transcript`
- `POST /runs/{run_id}/answer`
- `POST /runs/{run_id}/cancel`
- `POST /runs/{run_id}/continue-chat`

For free-chat handoff, reuse existing chat persistence primitives instead of making an internal HTTP call:

```python
# Add a small local helper that mirrors chat_helpers default-character bootstrap
# instead of hard-coding an invalid character id.
character_card, character_db_id = await resolve_workflow_handoff_character(
    chat_db,
    asyncio.get_running_loop(),
)
conversation_id, _ = await get_or_create_conversation(
    db=chat_db,
    conversation_id=None,
    character_id=int(character_db_id),
    character_name=character_card["name"],
    client_id=user_context["client_id"],
    loop=asyncio.get_running_loop(),
)
chat_db.add_message(
    {
        "conversation_id": conversation_id,
        "sender": "system",
        "content": handoff_summary,
        "client_id": user_context["client_id"],
    }
)
```

Then register the router in `main.py` in the same area as the existing Workflows routes.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_api.py tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_permissions.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat_workflows.py \
        tldw_Server_API/app/core/AuthNZ/permissions.py \
        tldw_Server_API/app/main.py \
        tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_api.py \
        tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_permissions.py
git commit -m "feat(chat-workflows): add API routes and permissions"
```

### Task 5: Add the shared UI client and query hooks

**Files:**
- Create: `apps/packages/ui/src/services/tldw/chat-workflows.ts`
- Modify: `apps/packages/ui/src/services/tldw/index.ts`
- Create: `apps/packages/ui/src/hooks/useChatWorkflows.ts`
- Test: `apps/packages/ui/src/services/__tests__/chat-workflows.test.ts`
- Test: `apps/packages/ui/src/hooks/__tests__/useChatWorkflows.test.tsx`

**Step 1: Write the failing client/hook tests**

```ts
import { vi, it, expect } from "vitest"
import { createChatWorkflowTemplate } from "@/services/tldw/chat-workflows"
import { apiSend } from "@/services/api-send"

vi.mock("@/services/api-send", () => ({
  apiSend: vi.fn(),
}))

it("posts template payload to the chat-workflows API", async () => {
  vi.mocked(apiSend).mockResolvedValue({
    ok: true,
    status: 200,
    data: { id: 12, title: "Discovery" }
  })

  const result = await createChatWorkflowTemplate({
    title: "Discovery",
    description: "Collect goals",
    steps: [],
  })

  expect(result.id).toBe(12)
  expect(apiSend).toHaveBeenCalledWith(
    expect.objectContaining({ path: "/api/v1/chat-workflows/templates", method: "POST" })
  )
})
```

```tsx
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi } from "vitest"

import { useChatWorkflowTemplateList } from "@/hooks/useChatWorkflows"
import * as chatWorkflowClient from "@/services/tldw/chat-workflows"

vi.mock("@/services/tldw/chat-workflows")

it("loads chat workflow templates through the query hook", async () => {
  vi.mocked(chatWorkflowClient.listChatWorkflowTemplates).mockResolvedValue([
    { id: 1, title: "Discovery", description: "Collect goals", status: "active" }
  ] as any)

  const queryClient = new QueryClient()
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  const { result } = renderHook(() => useChatWorkflowTemplateList(), { wrapper })

  await waitFor(() => expect(result.current.data?.[0]?.title).toBe("Discovery"))
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd .worktrees/chat-workflows && bunx vitest run apps/packages/ui/src/services/__tests__/chat-workflows.test.ts apps/packages/ui/src/hooks/__tests__/useChatWorkflows.test.tsx
```

Expected: FAIL because the service and hook files do not exist.

**Step 3: Write the minimal client and hook implementation**

Create a focused client using the existing service layer instead of adding more methods to `TldwApiClient`:

```ts
export async function createChatWorkflowTemplate(payload: ChatWorkflowTemplateCreatePayload) {
  const response = await apiSend<ChatWorkflowTemplate>({
    path: "/api/v1/chat-workflows/templates",
    method: "POST",
    body: payload,
  })
  if (!response.ok || !response.data) throw new Error(response.error || "Failed to create chat workflow template")
  return response.data
}
```

Add hooks for:
- template list/detail
- create/update/delete template
- generate draft
- start run
- submit answer
- continue chat

Use TanStack Query for cache invalidation around `["chat-workflows", ...]`.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd .worktrees/chat-workflows && bunx vitest run apps/packages/ui/src/services/__tests__/chat-workflows.test.ts apps/packages/ui/src/hooks/__tests__/useChatWorkflows.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/chat-workflows.ts \
        apps/packages/ui/src/services/tldw/index.ts \
        apps/packages/ui/src/hooks/useChatWorkflows.ts \
        apps/packages/ui/src/services/__tests__/chat-workflows.test.ts \
        apps/packages/ui/src/hooks/__tests__/useChatWorkflows.test.tsx
git commit -m "feat(chat-workflows-ui): add client and query hooks"
```

### Task 6: Add the Chat Workflows page shell, library, and builder

**Files:**
- Create: `apps/packages/ui/src/routes/option-chat-workflows.tsx`
- Create: `apps/packages/ui/src/components/ChatWorkflows/ChatWorkflowsPage.tsx`
- Create: `apps/packages/ui/src/components/ChatWorkflows/TemplateLibrary.tsx`
- Create: `apps/packages/ui/src/components/ChatWorkflows/TemplateBuilder.tsx`
- Create: `apps/packages/ui/src/components/ChatWorkflows/GenerateDraftPanel.tsx`
- Create: `apps/tldw-frontend/pages/chat-workflows.tsx`
- Test: `apps/packages/ui/src/components/ChatWorkflows/__tests__/TemplateBuilder.test.tsx`

**Step 1: Write the failing UI tests**

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TemplateBuilder } from "@/components/ChatWorkflows/TemplateBuilder"

it("adds a new linear step with stock question defaults", async () => {
  const user = userEvent.setup()
  render(<TemplateBuilder initialTemplate={null} onSave={vi.fn()} />)

  await user.click(screen.getByRole("button", { name: /add step/i }))
  expect(screen.getByLabelText(/base question/i)).toBeInTheDocument()
  expect(screen.getByDisplayValue("stock")).toBeInTheDocument()
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd .worktrees/chat-workflows && bunx vitest run apps/packages/ui/src/components/ChatWorkflows/__tests__/TemplateBuilder.test.tsx
```

Expected: FAIL because the new components do not exist.

**Step 3: Write the minimal UI shell**

Create:
- a page shell with tabs: `Templates`, `Build`, `Generate`
- a template list that loads saved templates
- a builder that edits ordered linear steps with:
  - label
  - base question
  - `stock` vs `llm_phrased`
  - optional phrasing instructions

The page entrypoint should follow the existing Next alias pattern:

```tsx
import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-chat-workflows"), { ssr: false })
```

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd .worktrees/chat-workflows && bunx vitest run apps/packages/ui/src/components/ChatWorkflows/__tests__/TemplateBuilder.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-chat-workflows.tsx \
        apps/packages/ui/src/components/ChatWorkflows/ChatWorkflowsPage.tsx \
        apps/packages/ui/src/components/ChatWorkflows/TemplateLibrary.tsx \
        apps/packages/ui/src/components/ChatWorkflows/TemplateBuilder.tsx \
        apps/packages/ui/src/components/ChatWorkflows/GenerateDraftPanel.tsx \
        apps/tldw-frontend/pages/chat-workflows.tsx \
        apps/packages/ui/src/components/ChatWorkflows/__tests__/TemplateBuilder.test.tsx
git commit -m "feat(chat-workflows-ui): add library and builder"
```

### Task 7: Add the run screen, completion flow, and chat entry point

**Files:**
- Create: `apps/packages/ui/src/components/ChatWorkflows/RunScreen.tsx`
- Modify: `apps/packages/ui/src/components/ChatWorkflows/ChatWorkflowsPage.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Test: `apps/packages/ui/src/components/ChatWorkflows/__tests__/RunScreen.test.tsx`

**Step 1: Write the failing run-screen tests**

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { RunScreen } from "@/components/ChatWorkflows/RunScreen"

it("advances from the current step to completion and reveals continue-chat CTA", async () => {
  const user = userEvent.setup()
  const onAnswer = vi.fn().mockResolvedValue({
    status: "completed",
    currentStepIndex: 0,
    displayedQuestion: null,
  })

  render(
    <RunScreen
      run={{
        run_id: "run-1",
        status: "active",
        currentStepIndex: 0,
        totalSteps: 1,
        displayedQuestion: "What is your goal?",
        answers: [],
      }}
      onAnswer={onAnswer}
      onContinueChat={vi.fn()}
    />
  )

  await user.type(screen.getByLabelText(/your answer/i), "Ship chat workflows")
  await user.click(screen.getByRole("button", { name: /submit answer/i }))

  expect(onAnswer).toHaveBeenCalled()
})
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd .worktrees/chat-workflows && bunx vitest run apps/packages/ui/src/components/ChatWorkflows/__tests__/RunScreen.test.tsx
```

Expected: FAIL because the run screen does not exist.

**Step 3: Write the minimal run and handoff UI**

Implement a run screen that:
- displays one active question at a time
- shows progress like `Step 2 of 5`
- renders prior answers as read-only history
- submits free-text answers using `useChatWorkflows`
- shows a completion state with explicit `Continue as free chat`

Add a lightweight entry point from the existing chat playground, for example a button or action that navigates to `/chat-workflows` without disturbing the current chat session.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd .worktrees/chat-workflows && bunx vitest run apps/packages/ui/src/components/ChatWorkflows/__tests__/RunScreen.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/ChatWorkflows/RunScreen.tsx \
        apps/packages/ui/src/components/ChatWorkflows/ChatWorkflowsPage.tsx \
        apps/packages/ui/src/components/Option/Playground/Playground.tsx \
        apps/packages/ui/src/components/ChatWorkflows/__tests__/RunScreen.test.tsx
git commit -m "feat(chat-workflows-ui): add run screen and handoff flow"
```

### Task 8: Update docs and run final verification

**Files:**
- Modify: `Docs/Code_Documentation/Chat_Developer_Guide.md`
- Create: `Docs/Published/API-related/Chat_Workflows_API.md`
- Modify: `Docs/Published/Overview/Feature_Status.md`

**Step 1: Write/update the docs**

Document:
- endpoint surface
- template/run model
- generated-draft behavior
- explicit-context-only rule
- stop-by-default completion and free-chat handoff

**Step 2: Run the backend tests**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_db.py \
  tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_schemas.py \
  tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_service.py \
  tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_api.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_deps.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_chat_workflows_permissions.py
```

Expected: PASS.

**Step 3: Run the frontend tests**

Run:

```bash
cd .worktrees/chat-workflows && bunx vitest run \
  apps/packages/ui/src/services/__tests__/chat-workflows.test.ts \
  apps/packages/ui/src/hooks/__tests__/useChatWorkflows.test.tsx \
  apps/packages/ui/src/components/ChatWorkflows/__tests__/TemplateBuilder.test.tsx \
  apps/packages/ui/src/components/ChatWorkflows/__tests__/RunScreen.test.tsx
```

Expected: PASS.

**Step 4: Run Bandit on the touched backend scope**

Run:

```bash
cd .worktrees/chat-workflows && source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/chat_workflows.py \
  tldw_Server_API/app/api/v1/schemas/chat_workflows.py \
  tldw_Server_API/app/api/v1/API_Deps/chat_workflows_deps.py \
  tldw_Server_API/app/core/Chat_Workflows \
  tldw_Server_API/app/core/DB_Management/ChatWorkflows_DB.py \
  -f json -o /tmp/bandit_chat_workflows.json
```

Expected: Bandit completes successfully and any new findings in touched code are fixed before merge.

**Step 5: Commit**

```bash
git add Docs/Code_Documentation/Chat_Developer_Guide.md \
        Docs/Published/API-related/Chat_Workflows_API.md \
        Docs/Published/Overview/Feature_Status.md
git commit -m "docs(chat-workflows): document API and behavior"
```
