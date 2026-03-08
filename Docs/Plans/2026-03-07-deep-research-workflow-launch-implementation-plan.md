# Deep Research Workflow Launch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a launch-only `deep_research` workflow step that starts a normal deep-research session, returns a stable run reference, and exposes that step in workflow introspection and the workflow editor.

**Architecture:** Keep workflow integration thin. Implement `deep_research` as a normal workflow adapter that calls `ResearchService.create_session(...)` directly, registers a new step type and JSON schema, and exposes a matching node in the workflow editor. Do not teach the workflow engine to wait across research checkpoints in this slice.

**Tech Stack:** FastAPI, existing workflow adapter registry, existing research service, Pydantic, React, workflow editor registry metadata, pytest, Vitest.

---

### Task 1: Add Red Backend Tests For The New Workflow Step

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_step_types.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`

**Step 1: Add adapter-level launch tests**

In `test_research_adapters.py`, add failing tests that cover:

- launching `deep_research` returns `run_id`, `status`, `phase`, `control_state`, `console_url`, `bundle_url`, `query`, `source_policy`, and `autonomy_mode`
- templated `query` resolves from workflow context before launch
- `save_artifact=True` records a workflow artifact for the launch reference
- empty rendered `query` fails clearly

**Step 2: Add step-types API coverage**

In `test_engine_step_types.py` or `test_workflows_api.py`, add failing coverage that asserts:

- `/api/v1/workflows/step-types` includes `deep_research`
- the returned schema includes `query`, `source_policy`, `autonomy_mode`, `limits_json`, `provider_overrides`, and `save_artifact`
- the description makes launch-only behavior explicit
- workflow definition validation rejects clearly invalid `deep_research` config before execution

**Step 3: Run the focused backend tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q
```

Expected: FAIL for missing `deep_research` adapter registration, missing schema exposure, and missing launch output behavior.

### Task 2: Implement The Backend Adapter And Config Model

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`
- Add: `tldw_Server_API/app/core/Workflows/adapters/research/launch.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/__init__.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/__init__.py`

**Step 1: Add the config model**

In `_config.py`, add a `DeepResearchConfig` model with:

- `query: str`
- `source_policy: Literal["balanced", "local_first", "external_first", "local_only", "external_only"] = "balanced"`
- `autonomy_mode: Literal["checkpointed", "autonomous"] = "checkpointed"`
- `limits_json: dict[str, Any] | None = None`
- `provider_overrides: dict[str, Any] | None = None`
- `save_artifact: bool = True`

Use the existing `BaseAdapterConfig` base class.

**Step 2: Add the adapter implementation**

Create `launch.py` with a `@registry.register(...)` adapter for `deep_research`.

The adapter should:

- read the resolved `query`
- derive `owner_user_id` from workflow context using existing context/user helpers
- defensively validate the raw config with `DeepResearchConfig.model_validate(...)`
- instantiate or use `ResearchService`
- call `create_session(...)`
- build:

```python
{
    "run_id": session.id,
    "status": session.status,
    "phase": session.phase,
    "control_state": session.control_state,
    "console_url": f"/research?run={session.id}",
    "bundle_url": f"/api/v1/research/runs/{session.id}/bundle",
    "query": query,
    "source_policy": source_policy,
    "autonomy_mode": autonomy_mode,
}
```

- optionally persist the same payload by:
  - resolving the per-step artifact directory
  - writing `deep_research_launch.json`
  - registering the file through `context["add_artifact"]` with `mime_type="application/json"`

Keep the adapter launch-only. Do not add waiting logic.

**Step 3: Register and export the adapter**

Update `research/__init__.py` and `adapters/__init__.py` so `deep_research` is imported and exported like the other workflow adapters.

**Step 4: Run the focused backend tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py -q
```

Expected: PASS for the new adapter-specific tests.

### Task 3: Register The Step Type And Expose The JSON Schema

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/registry.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Modify: backend tests from Task 1

**Step 1: Add the static step type**

In `registry.py`, add:

- `deep_research`: description should explicitly state that it launches a deep-research session and does not wait for completion

**Step 2: Add the step-types schema**

In `workflows.py`, extend the `schemas` map for `/step-types` with a `deep_research` JSON schema that includes:

- `query`
- `source_policy`
- `autonomy_mode`
- `limits_json`
- `provider_overrides`
- `save_artifact`
- `timeout_seconds` only if the existing step-types surface already expects generic timeout support there

Use an example that shows a templated query.

Also add a matching `deep_research` validation schema to the workflow-definition validation map so malformed configs fail at save/run request time instead of only inside the adapter.

**Step 3: Re-run backend introspection tests**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q
```

Expected: PASS

### Task 4: Add Red Frontend Workflow Editor Tests

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx`

**Step 1: Add registry parity and metadata tests**

In `step-registry.test.ts`, add failing assertions that:

- `deep_research` exists in the frontend registry expectations
- it is categorized as `research`
- its label is `Deep Research Run`
- its description contains launch-only wording
- if server schema is present, the resulting editor field treatment still preserves the intended deep-research controls

**Step 2: Add config-panel tests**

In `NodeConfigPanel.test.tsx`, add failing coverage that checks the deep research node renders:

- required `query` as a template-oriented editor experience
- `source_policy`
- `autonomy_mode`
- `save_artifact`

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

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
- Modify: frontend tests from Task 4

**Step 1: Add the deep research node metadata**

In `step-registry.ts`, add a `deep_research` entry with:

- label `Deep Research Run`
- category `research`
- research-appropriate icon and color
- description: `Launches a deep research session and returns its run reference; does not wait for completion.`

**Step 2: Add the config schema**

Expose config fields for:

- `query` via `template-editor`
- `source_policy` via `select`
- `autonomy_mode` via `select`
- `save_artifact` via `checkbox`

Use only the choices approved in design.

If the server-driven schema path overrides local metadata for this step, add the smallest possible targeted override so the rendered controls still match the approved UX.

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

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`
- Optionally modify: `tldw_Server_API/tests/Workflows/conftest.py`

**Step 1: Add a focused workflow execution test**

Add a failing integration test that:

- creates a workflow with a single `deep_research` step
- runs it with templated `inputs.topic`
- waits for workflow success
- asserts the step result contains a real `run_id`
- asserts the workflow output carries the launch reference payload

Keep this test launch-only. Do not wait for the research session to complete.

**Step 2: Make the runtime test pass**

Adjust backend adapter/service wiring only as needed so the workflow engine can execute the step in tests.

**Step 3: Run the focused workflow integration test**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/test_workflows_api.py -q
```

Expected: PASS

### Task 7: Focused Verification, Security Check, And Commits

**Status:** Complete

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-workflow-launch-implementation-plan.md`

**Step 1: Run the focused backend verification suite**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q
```

Expected: PASS

**Step 2: Run the focused frontend verification suite**

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
  tldw_Server_API/app/core/Workflows/adapters/research \
  tldw_Server_API/app/core/Workflows/registry.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  -f json -o /tmp/bandit_deep_research_workflow_launch.json
```

Expected: `0` new findings in touched code.

**Step 4: Record results in this plan**

Update task statuses and append the actual verification commands/results.

**Actual verification**

- Focused backend adapter verification:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  -q -k deep_research_adapter
```

Result: `2 passed, 58 deselected`

- Focused backend step-types verification:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  -q -k deep_research
```

Result: `1 passed, 4 deselected`

- Focused backend workflow API verification:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Workflows/test_workflows_api.py \
  -q -k "deep_research or step_types_and_runs_listing"
```

Result: `2 passed, 13 deselected`

- Focused backend runtime integration verification:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Workflows/test_workflows_api.py \
  -q -k run_workflow_launches_deep_research_session
```

Result: `1 passed, 15 deselected`

- Focused frontend workflow editor verification:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui
bunx vitest run \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
```

Result: `18/18` tests passed

- Bandit:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Workflows/adapters/research/launch.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Workflows/registry.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/endpoints/workflows.py \
  -f json -o /tmp/bandit_deep_research_workflow_launch.json
```

Result: `0` findings, `0` errors

**Note:** a broader combined run of the full `test_workflows_api.py` file intermittently hit the pre-existing SQLite transaction issue in `test_artifact_download_per_run_non_block`. That test passes in isolation and is unrelated to the `deep_research` workflow-launch slice.

**Step 5: Commit the implementation work**

```bash
git add \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/app/core/Workflows/adapters/research/launch.py \
  tldw_Server_API/app/core/Workflows/adapters/research/__init__.py \
  tldw_Server_API/app/core/Workflows/adapters/__init__.py \
  tldw_Server_API/app/core/Workflows/registry.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  apps/packages/ui/src/components/WorkflowEditor/step-registry.ts \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
git commit -m "feat(workflows): add deep research launch step"
```

**Step 6: Commit the finalized plan**

```bash
git add Docs/Plans/2026-03-07-deep-research-workflow-launch-implementation-plan.md
git commit -m "docs(research): finalize workflow launch plan"
```

## Notes

- This plan intentionally stops at launch-only workflow integration.
- A later slice can add an explicit `research_wait` or `wait_for_completion` mode once workflow/runtime semantics are designed for it.
- The step should stay thin and reuse `ResearchService.create_session(...)` rather than reimplementing research launch behavior in the workflow layer.
