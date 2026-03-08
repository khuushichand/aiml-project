# Deep Research Workflow Wait Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a separate `deep_research_wait` workflow step that waits for a launched deep-research run to reach terminal state and optionally returns the final bundle for downstream workflow steps.

**Architecture:** Keep the existing `deep_research` step launch-only and implement `deep_research_wait` as a normal polling workflow adapter that calls the research core directly. Register the new step in workflow introspection and the workflow editor, and keep waiting behavior explicit instead of teaching the workflow engine to own research runtime semantics.

**Tech Stack:** FastAPI, existing workflow adapter registry, existing research service, Pydantic, React, workflow editor registry metadata, pytest, Vitest.

---

### Task 1: Add Red Backend Tests For The Wait Step

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_step_types.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`

**Step 1: Add adapter-level wait tests**

In `test_research_adapters.py`, add failing tests that cover:

- waiting from a raw `run_id`
- waiting from a prior `deep_research` output object containing `run_id`
- returning `bundle` when the run completed and `include_bundle=True`
- timing out when the run never reaches terminal state
- `failed` and `cancelled` behavior under both fail and allow configurations
- writing a `deep_research_wait.json` workflow artifact when `save_artifact=True`

**Step 2: Add step-types and validation coverage**

In `test_engine_step_types.py` or `test_workflows_api.py`, add failing coverage that asserts:

- `/api/v1/workflows/step-types` includes `deep_research_wait`
- the returned schema includes `run_id`, `run`, `include_bundle`, `fail_on_cancelled`, `fail_on_failed`, `poll_interval_seconds`, `timeout_seconds`, and `save_artifact`
- the description makes terminal waiting behavior explicit
- workflow definition validation rejects malformed `deep_research_wait` config
- save-time validation still rejects malformed `deep_research_wait` config when `jsonschema` is unavailable

**Step 3: Run the focused backend tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k "deep_research_wait"
```

Expected: FAIL for missing `deep_research_wait` adapter registration, missing schema exposure, and missing wait behavior.

### Task 2: Implement The Backend Config Model And Adapter

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`
- Add: `tldw_Server_API/app/core/Workflows/adapters/research/wait.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/__init__.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/__init__.py`

**Step 1: Add the config model**

In `_config.py`, add a `DeepResearchWaitConfig` model with:

- `run_id: str | None = None`
- `run: dict[str, Any] | None = None`
- `include_bundle: bool = True`
- `fail_on_cancelled: bool = True`
- `fail_on_failed: bool = True`
- `poll_interval_seconds: float = 2.0`
- `save_artifact: bool = True`

Use the existing adapter config base class and keep validation helpers in the model where that reduces adapter branching.

Keep `run_id` as the primary user-facing config path. Support `run` for advanced/API-authored definitions, but do not make full-object input the main UI path.

**Step 2: Add the adapter implementation**

Create `wait.py` with a `@registry.register(...)` adapter for `deep_research_wait`.

The adapter should:

- defensively validate the raw config with `DeepResearchWaitConfig.model_validate(...)`
- resolve a usable `run_id` from either:
  - templated `run_id`, or
  - `run["run_id"]`
- derive `owner_user_id` from workflow context using existing context/user helpers
- instantiate or use `ResearchService`
- poll `get_session(...)` until:
  - `completed`
  - `failed`
  - `cancelled`
  - or timeout
- check `context["is_cancelled"]()` on every poll cycle and stop immediately if the workflow itself was cancelled
- when `include_bundle=True` and the run completed, load the final bundle through the research core
- build:

```python
{
    "run_id": session.id,
    "status": session.status,
    "phase": session.phase,
    "control_state": session.control_state,
    "completed_at": session.completed_at,
    "bundle_url": f"/api/v1/research/runs/{session.id}/bundle",
    "bundle": bundle_or_none,
}
```

- optionally persist the same payload by:
  - resolving the per-step artifact directory
  - writing `deep_research_wait.json`
  - registering the file through `context["add_artifact"]` with `mime_type="application/json"`

Terminal behavior:

- raise on timeout
- return `{"__status__": "cancelled"}` when the workflow cancellation hook trips during waiting
- raise on `failed` when `fail_on_failed=True`
- raise on `cancelled` when `fail_on_cancelled=True`
- otherwise return the terminal result object without raising

**Step 3: Register and export the adapter**

Update `research/__init__.py` and `adapters/__init__.py` so `deep_research_wait` is imported and exported like the other workflow adapters.

**Step 4: Run the focused adapter tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py -q -k deep_research_wait
```

Expected: PASS for the new adapter-specific tests.

### Task 3: Register The Step Type And Expose The JSON Schema

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/registry.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Modify: backend tests from Task 1

**Step 1: Add the static step type**

In `registry.py`, add:

- `deep_research_wait`: description should explicitly state that it waits for a launched deep-research run to finish and can return the final bundle

**Step 2: Add the step-types schema**

In `workflows.py`, extend the `schemas` map for `/step-types` with a `deep_research_wait` JSON schema that includes:

- `run_id`
- `run`
- `include_bundle`
- `fail_on_cancelled`
- `fail_on_failed`
- `poll_interval_seconds`
- `save_artifact`
- `timeout_seconds` if the existing step-types surface already expects generic timeout support there

Use an example that shows chaining from a prior launch step.

Also add:

- a matching `deep_research_wait` validation schema to the workflow-definition validation map
- an explicit `_validate_deep_research_wait_config(...)` helper

The explicit validator should enforce:

- at least one usable run reference is present
- `run_id` wins when both are present
- `run` only counts when it is an object with a non-empty `run_id`
- `poll_interval_seconds` stays within the approved bounds

This keeps save-time validation reliable even when optional `jsonschema` support is not installed.

**Step 3: Re-run backend introspection tests**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k "deep_research_wait or step_types"
```

Expected: PASS

### Task 4: Add Red Frontend Workflow Editor Tests

**Status:** Not Started

**Files:**
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx`

**Step 1: Add registry parity and metadata tests**

In `step-registry.test.ts`, add failing assertions that:

- `deep_research_wait` exists in the frontend registry expectations
- it is categorized as `research`
- its label is `Deep Research Wait`
- its description contains waiting/final-bundle wording

**Step 2: Add config-panel tests**

In `NodeConfigPanel.test.tsx`, add failing coverage that checks the wait node renders:

- `run_id` as a template-oriented editor experience
- `run`
- `include_bundle`
- `fail_on_cancelled`
- `fail_on_failed`
- `poll_interval_seconds`
- `save_artifact`
- helper text or description makes `run_id: "{{ deep_research.run_id }}"` the primary chaining pattern

**Step 3: Run focused frontend tests to verify failure**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
```

Expected: FAIL for missing frontend registry metadata and config fields.

### Task 5: Implement The Workflow Editor Metadata

**Status:** Not Started

**Files:**
- Modify: `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/NodeConfigPanel.tsx`
- Modify: frontend tests from Task 4

**Step 1: Add the wait node metadata**

In `step-registry.ts`, add a `deep_research_wait` entry with:

- label `Deep Research Wait`
- category `research`
- research-appropriate icon and color
- description explaining that it waits for a launched run to finish and can return the final bundle

**Step 2: Add the config schema**

Expose config fields for:

- `run_id` via `template-editor`
- `run` via `json-editor` as a secondary advanced field
- `include_bundle` via `checkbox`
- `fail_on_cancelled` via `checkbox`
- `fail_on_failed` via `checkbox`
- `poll_interval_seconds` via `number`
- `save_artifact` via `checkbox`

If the server-driven schema path overrides local metadata for this step, add the smallest possible targeted override so the rendered controls still match the approved UX.

Make `run_id` the primary authoring path in the node description or field help text, using `{{ deep_research.run_id }}` as the concrete example.

**Step 3: Re-run frontend workflow editor tests**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
```

Expected: PASS

### Task 6: Add A Workflow Runtime Integration Test

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`
- Optionally modify: `tldw_Server_API/tests/Workflows/conftest.py`

**Step 1: Add a focused workflow runtime test**

Add failing integration coverage that:

- creates a workflow with:
  - `deep_research`
  - `deep_research_wait`
- runs the workflow
- verifies the wait step receives the launch output, waits to terminal state, and exposes `bundle` in step results when the run completes
- verifies workflow cancellation during the wait step exits promptly instead of polling until research timeout

Prefer existing research test-mode fixtures so the workflow does not depend on live providers.

**Step 2: Run the focused runtime test to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k deep_research_wait
```

Expected: FAIL for missing chained wait behavior.

**Step 3: Implement the minimal fixes and rerun**

After backend and schema work is in place, rerun the same test until it passes.

### Task 7: Run Verification And Commit

**Status:** Not Started

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-workflow-wait-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k deep_research_wait
```

Expected: PASS

Note: if bundle-size behavior is adjusted during implementation, add one focused assertion that `include_bundle=false` returns only pointers/metadata and not the full package.

**Step 2: Run focused frontend verification**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
```

Expected: PASS

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/core/Workflows/adapters/research/wait.py \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/app/core/Workflows/registry.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  -f json -o /tmp/bandit_deep_research_workflow_wait.json
```

Expected: `0` findings in the touched scope.

**Step 4: Update the plan status and commit**

Mark each task `Complete`, record any residual risks, then commit with a message like:

```bash
git add \
  Docs/Plans/2026-03-07-deep-research-workflow-wait-implementation-plan.md \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/app/core/Workflows/adapters/research/wait.py \
  tldw_Server_API/app/core/Workflows/adapters/research/__init__.py \
  tldw_Server_API/app/core/Workflows/adapters/__init__.py \
  tldw_Server_API/app/core/Workflows/registry.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  apps/packages/ui/src/components/WorkflowEditor/step-registry.ts \
  apps/packages/ui/src/components/WorkflowEditor/NodeConfigPanel.tsx \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
git commit -m "feat(workflows): add deep research wait step"
```
