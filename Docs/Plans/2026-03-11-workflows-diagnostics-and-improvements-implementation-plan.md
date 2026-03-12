# Workflows Diagnostics and Improvements Implementation Plan

**Goal:** Add a first-class workflows diagnostics model with explicit replay safety, per-attempt execution history, investigation APIs, a shared run inspector, and server-authoritative preflight validation.

**Architecture:** Keep the current workflows runtime and raw execution ledger in place, but add a structured diagnostics layer beside it. Preserve `workflow_step_runs` as the logical step record, add child `workflow_step_attempts`, derive a `run investigation` view from runs/events/artifacts, and expose that view consistently to the API and shared UI. Build replay safety from explicit step capability metadata rather than inferring it from failures after the fact.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL via `Workflows_DB`, asyncio workflow engine, pytest, React, Zustand, shared UI services, Vitest

---

### Task 1: Establish replay capability metadata for step types

**Files:**
- Create: `tldw_Server_API/app/core/Workflows/capabilities.py`
- Modify: `tldw_Server_API/app/core/Workflows/registry.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Test: `tldw_Server_API/tests/Workflows/test_workflow_step_capabilities.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/Workflows/test_workflow_step_capabilities.py` with expectations for safe and unsafe step types.

Example:

```python
from tldw_Server_API.app.core.Workflows.capabilities import get_step_capability


def test_webhook_steps_default_to_unsafe_replay():
    capability = get_step_capability("webhook")
    assert capability.replay_safe is False
    assert capability.requires_human_review_for_rerun is True


def test_prompt_steps_expose_safe_replay_defaults():
    capability = get_step_capability("prompt")
    assert capability.replay_safe is True
    assert capability.idempotency_strategy == "run_scoped"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_step_capabilities.py -v`

Expected: FAIL because the capability module and helpers do not exist yet.

**Step 3: Write minimal implementation**

Create a small capability model and registry helper.

Implementation target:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class StepCapability:
    replay_safe: bool = False
    idempotency_strategy: str = "none"
    compensation_supported: bool = False
    requires_human_review_for_rerun: bool = False
    evidence_level: str = "standard"
```

Register per-step defaults in `registry.py`, and extend `/api/v1/workflows/step-types` output so clients can inspect replay semantics without hard-coding them.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_step_capabilities.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/capabilities.py \
  tldw_Server_API/app/core/Workflows/registry.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  tldw_Server_API/tests/Workflows/test_workflow_step_capabilities.py
git commit -m "feat(workflows): add step replay capabilities"
```

### Task 2: Add `workflow_step_attempts` schema and DB adapter support

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Workflows_DB.py`
- Test: `tldw_Server_API/tests/Workflows/test_workflows_db.py`
- Test: `tldw_Server_API/tests/Workflows/test_workflows_postgres_migrations.py`
- Test: `tldw_Server_API/tests/Workflows/test_dual_backend_workflows.py`

**Step 1: Write the failing tests**

Add DB-level tests that assert:
- the new `workflow_step_attempts` table exists in SQLite and PostgreSQL
- attempt rows can be inserted and listed
- `workflow_step_runs` remains the logical parent row

Example:

```python
def test_create_step_attempt_persists_attempt_history(workflows_db):
    workflows_db.create_step_run(...)
    attempt_id = workflows_db.create_step_attempt(...)
    rows = workflows_db.list_step_attempts(run_id="run-1", step_id="step-a")
    assert rows[0]["attempt_id"] == attempt_id
    assert rows[0]["attempt_number"] == 1
```

**Step 2: Run tests to verify they fail**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflows_db.py -k step_attempt -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflows_postgres_migrations.py -k step_attempt -v`

Expected: FAIL because the schema and adapter methods do not exist yet.

**Step 3: Write minimal implementation**

Add a new table and adapter methods such as:

```sql
CREATE TABLE IF NOT EXISTS workflow_step_attempts (
    attempt_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    step_run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    reason_code_core TEXT,
    reason_code_detail TEXT,
    retryable BOOLEAN,
    error_summary TEXT,
    metadata_json TEXT
)
```

Add adapter helpers like:
- `create_step_attempt(...)`
- `complete_step_attempt(...)`
- `list_step_attempts(run_id, step_id=None, step_run_id=None)`

Do not remove or repurpose `workflow_step_runs`.

**Step 4: Run tests to verify they pass**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflows_db.py -k step_attempt -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflows_postgres_migrations.py -k step_attempt -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_dual_backend_workflows.py -k step_attempt -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Workflows_DB.py \
  tldw_Server_API/tests/Workflows/test_workflows_db.py \
  tldw_Server_API/tests/Workflows/test_workflows_postgres_migrations.py \
  tldw_Server_API/tests/Workflows/test_dual_backend_workflows.py
git commit -m "feat(workflows): add step attempt persistence"
```

### Task 3: Emit layered failure semantics and attempt-level engine records

**Files:**
- Create: `tldw_Server_API/app/core/Workflows/failures.py`
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/_base.py`
- Test: `tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py`
- Test: `tldw_Server_API/tests/Workflows/test_workflows_api.py`
- Create: `tldw_Server_API/tests/Workflows/test_workflow_attempt_failures.py`

**Step 1: Write the failing tests**

Add tests that prove:
- each failed attempt gets a `reason_code_core` and `retryable` decision
- retry loops create multiple attempt rows instead of mutating only a counter
- unsafe step types do not report safe replay recommendations

Example:

```python
def test_retrying_step_records_multiple_attempt_rows(workflows_db, engine):
    run_id = create_retrying_run(...)
    asyncio.run(engine.start_run(run_id))
    attempts = workflows_db.list_step_attempts(run_id=run_id, step_id="prompt_1")
    assert len(attempts) == 2
    assert attempts[0]["reason_code_core"] == "runtime_error"
```

**Step 2: Run tests to verify they fail**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_attempt_failures.py -v`

Expected: FAIL because the engine does not yet emit attempt rows or layered failure envelopes.

**Step 3: Write minimal implementation**

Create a helper model such as:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class FailureEnvelope:
    reason_code_core: str
    reason_code_detail: str | None
    category: str
    blame_scope: str
    retryable: bool
    retry_recommendation: str
    error_summary: str
```

Update the engine so each loop iteration:
- creates an attempt row before adapter execution
- completes that attempt with success, waiting, cancel, or failure state
- persists failure envelope fields
- keeps `workflow_step_runs` as the stable parent row for approvals and routing

**Step 4: Run tests to verify they pass**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_attempt_failures.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflows_api.py -k retry -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/failures.py \
  tldw_Server_API/app/core/Workflows/engine.py \
  tldw_Server_API/app/core/Workflows/adapters/_base.py \
  tldw_Server_API/tests/Workflows/test_engine_retry_classifier.py \
  tldw_Server_API/tests/Workflows/test_workflow_attempt_failures.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py
git commit -m "feat(workflows): emit attempt-level failure diagnostics"
```

### Task 4: Add the run investigation service and API endpoints

**Files:**
- Create: `tldw_Server_API/app/core/Workflows/investigation.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/workflows.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Create: `tldw_Server_API/tests/Workflows/test_workflow_investigation_api.py`

**Step 1: Write the failing tests**

Add API tests for:
- `GET /api/v1/workflows/runs/{run_id}/investigation`
- `GET /api/v1/workflows/runs/{run_id}/steps`
- `GET /api/v1/workflows/runs/{run_id}/steps/{step_id}/attempts`
- auth gating between safe summary fields and operator-only detail

Example:

```python
def test_investigation_endpoint_returns_primary_failure(client, failed_run):
    resp = client.get(f"/api/v1/workflows/runs/{failed_run}/investigation", headers=auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["primary_failure"]["reason_code_core"] == "runtime_error"
    assert "recommended_actions" in data
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_investigation_api.py -v`

Expected: FAIL because the service, schemas, and endpoints do not exist yet.

**Step 3: Write minimal implementation**

Create a service that assembles investigation data from:
- `workflow_runs`
- `workflow_step_runs`
- `workflow_step_attempts`
- `workflow_events`
- artifacts and webhook delivery evidence

Response shape target:

```python
{
    "run_id": run_id,
    "primary_failure": {...},
    "failed_step": {...},
    "attempts": [...],
    "evidence": {...},
    "recommended_actions": [...]
}
```

If you materialize this view, include `schema_version` and `derived_from_event_seq`.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_investigation_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Workflows/investigation.py \
  tldw_Server_API/app/api/v1/schemas/workflows.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  tldw_Server_API/tests/Workflows/test_workflow_investigation_api.py
git commit -m "feat(workflows): add investigation APIs"
```

### Task 5: Add server-authoritative preflight validation

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/workflows.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Create: `tldw_Server_API/tests/Workflows/test_workflow_preflight_api.py`

**Step 1: Write the failing tests**

Add tests that assert preflight returns:
- blocking validation errors
- non-blocking warnings
- replay safety warnings for unsafe step types

Example:

```python
def test_preflight_flags_unsafe_replay_steps(client, workflow_definition):
    resp = client.post("/api/v1/workflows/preflight", json={"definition": workflow_definition}, headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json()["warnings"][0]["code"] == "unsafe_replay_step"
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_preflight_api.py -v`

Expected: FAIL because the endpoint and schema do not exist yet.

**Step 3: Write minimal implementation**

Reuse existing validation helpers instead of creating a second rules engine.

Response shape target:

```python
{
    "valid": False,
    "errors": [{"code": "missing_required_input", "message": "..."}],
    "warnings": [{"code": "unsafe_replay_step", "message": "..."}]
}
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_preflight_api.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/workflows.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  tldw_Server_API/tests/Workflows/test_workflow_preflight_api.py
git commit -m "feat(workflows): add preflight validation endpoint"
```

### Task 6: Extend shared UI workflow services and types for diagnostics

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/workflows.ts`
- Modify: `apps/packages/ui/src/types/workflow-editor.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/workflows.test.ts`

**Step 1: Write the failing tests**

Add service tests for:
- fetching investigation data
- fetching step attempts
- posting preflight requests

Example:

```ts
it("fetches workflow investigation data", async () => {
  mockBgRequest.mockResolvedValueOnce({ run_id: "run-1", primary_failure: { reason_code_core: "runtime_error" } })
  const result = await getWorkflowInvestigation("run-1")
  expect(result.primary_failure.reason_code_core).toBe("runtime_error")
})
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/workflows.test.ts`

Expected: FAIL because the functions and types do not exist yet.

**Step 3: Write minimal implementation**

Add typed service helpers such as:

```ts
export const getWorkflowInvestigation = (runId: string) =>
  bgRequest<WorkflowRunInvestigation>({
    path: `/api/v1/workflows/runs/${runId}/investigation`,
    method: "GET"
  })
```

Also add typed models for:
- `WorkflowRunInvestigation`
- `WorkflowStepAttempt`
- `WorkflowPreflightResult`

**Step 4: Run tests to verify they pass**

Run: `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/workflows.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/workflows.ts \
  apps/packages/ui/src/types/workflow-editor.ts \
  apps/packages/ui/src/services/tldw/__tests__/workflows.test.ts
git commit -m "feat(ui): add workflow diagnostics services"
```

### Task 7: Build a shared run inspector and embed it in the workflow editor

**Files:**
- Create: `apps/packages/ui/src/components/Common/Workflow/WorkflowRunInspector.tsx`
- Modify: `apps/packages/ui/src/components/Common/Workflow/index.ts`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/ExecutionPanel.tsx`
- Modify: `apps/packages/ui/src/store/workflow-editor.ts`
- Create: `apps/packages/ui/src/components/Common/Workflow/__tests__/WorkflowRunInspector.test.tsx`

**Step 1: Write the failing test**

Add component tests that assert the inspector renders:
- failure summary
- attempt timeline
- evidence tabs
- recommended actions

Example:

```tsx
it("renders failure summary and attempts", () => {
  render(<WorkflowRunInspector investigation={investigationFixture} />)
  expect(screen.getByText("runtime_error")).toBeInTheDocument()
  expect(screen.getByText("Attempt 2")).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: /evidence/i })).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Common/Workflow/__tests__/WorkflowRunInspector.test.tsx`

Expected: FAIL because the component does not exist yet.

**Step 3: Write minimal implementation**

Build a shared inspector component that accepts typed investigation data and exposes:
- summary card
- attempts list
- evidence tabs
- next-action panel

Then update `ExecutionPanel.tsx` to open or render that shared component for real run ids instead of only displaying local mock state.

**Step 4: Run test to verify it passes**

Run:
- `cd apps/packages/ui && bunx vitest run src/components/Common/Workflow/__tests__/WorkflowRunInspector.test.tsx`
- `cd apps/packages/ui && bunx vitest run src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/Workflow/WorkflowRunInspector.tsx \
  apps/packages/ui/src/components/Common/Workflow/index.ts \
  apps/packages/ui/src/components/WorkflowEditor/ExecutionPanel.tsx \
  apps/packages/ui/src/store/workflow-editor.ts \
  apps/packages/ui/src/components/Common/Workflow/__tests__/WorkflowRunInspector.test.tsx
git commit -m "feat(ui): add shared workflow run inspector"
```

### Task 8: Update docs, alerts, and final verification

**Files:**
- Modify: `Docs/Design/Workflows.md`
- Modify: `Docs/Operations/Workflows_Debugging.md`
- Modify: `Docs/Operations/Workflows_Runbook.md`
- Modify: `Docs/Operations/monitoring/alerts/workflows_alerts.yml`
- Reference: `Docs/Plans/2026-03-11-workflows-diagnostics-and-improvements-design.md`

**Step 1: Write the doc and alert updates**

Document:
- the new attempt model
- investigation endpoints
- preflight endpoint
- replay safety rules
- operator workflows for investigation-first triage

Extend alerts or dashboards to key on structured reason codes where possible.

**Step 2: Run targeted verification**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_step_capabilities.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_attempt_failures.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_investigation_api.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Workflows/test_workflow_preflight_api.py -v`
- `cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/workflows.test.ts`
- `cd apps/packages/ui && bunx vitest run src/components/Common/Workflow/__tests__/WorkflowRunInspector.test.tsx`

Expected: PASS

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/Workflows \
  tldw_Server_API/app/core/DB_Management/Workflows_DB.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  tldw_Server_API/app/api/v1/schemas/workflows.py \
  -f json -o /tmp/bandit_workflows_diagnostics.json
```

Expected: no new findings in changed workflows code.

**Step 4: Review the final diff**

Run: `git diff --stat`

Expected: only workflows diagnostics, UI inspector, docs, and tests are changed.

**Step 5: Commit**

```bash
git add Docs/Design/Workflows.md \
  Docs/Operations/Workflows_Debugging.md \
  Docs/Operations/Workflows_Runbook.md \
  Docs/Operations/monitoring/alerts/workflows_alerts.yml
git commit -m "docs(workflows): document diagnostics investigation flow"
```
