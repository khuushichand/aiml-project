# Deep Research Workflow Load Bundle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `deep_research_load_bundle` workflow step that loads lightweight references from a completed deep research run without inlining the full bundle into workflow state.

**Architecture:** Keep launch, waiting, and consumption as separate workflow steps. Implement `deep_research_load_bundle` as a normal research adapter that validates a run reference, requires a completed session, derives a compact bundle summary, writes a pointer-style artifact, and returns a small reference object for downstream workflow steps.

**Tech Stack:** FastAPI, existing workflow adapter registry, `ResearchService`, Pydantic, React workflow editor, pytest, Vitest.

---

### Task 1: Add Red Backend Tests For The Bundle-Load Step

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_step_types.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`

**Step 1: Add adapter-level tests**

In `test_research_adapters.py`, add failing tests that cover:

- loading from a raw `run_id`
- loading from a prior launch/wait output object containing `run_id`
- returning only compact `bundle_summary` plus artifact refs
- writing `deep_research_bundle_ref.json` when `save_artifact=True`
- rejecting non-completed runs with a clear completed-run-only error

**Step 2: Add step-types and validation coverage**

Add failing coverage that asserts:

- `/api/v1/workflows/step-types` includes `deep_research_load_bundle`
- the schema includes `run_id`, `run`, and `save_artifact`
- the description makes completed-run bundle loading explicit
- workflow definition validation rejects malformed config

**Step 3: Add a workflow runtime integration test**

In `test_workflows_api.py`, add failing coverage for a workflow chain:

- `deep_research`
- `deep_research_wait`
- `deep_research_load_bundle`

Verify the final step returns the compact bundle reference object instead of the full bundle.

**Step 4: Run focused backend tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k "deep_research_load_bundle"
```

Expected: FAIL for missing adapter registration, missing schema exposure, and missing runtime support.

### Task 2: Implement Backend Config And Adapter

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`
- Add: `tldw_Server_API/app/core/Workflows/adapters/research/load_bundle.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/__init__.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/__init__.py`

**Step 1: Add the config model**

In `_config.py`, add a `DeepResearchLoadBundleConfig` model with:

- `run_id: str | None = None`
- `run: dict[str, Any] | None = None`
- `save_artifact: bool = True`

Validation rules:

- require either `run_id` or `run.run_id`
- `run_id` wins when both exist
- reject empty resolved references

**Step 2: Add the adapter implementation**

Create `load_bundle.py` with a `@registry.register(...)` adapter for `deep_research_load_bundle`.

The adapter should:

- validate config defensively with `DeepResearchLoadBundleConfig.model_validate(...)`
- resolve `owner_user_id` from workflow context
- resolve `run_id`
- load the session with `ResearchService.get_session(...)`
- fail unless `session.status == "completed"`
- load the final bundle with `ResearchService.get_bundle(...)`
- load the artifact manifest through research service methods
- derive:

```python
{
    "run_id": session.id,
    "status": session.status,
    "phase": session.phase,
    "control_state": session.control_state,
    "completed_at": session.completed_at,
    "bundle_url": f"/api/v1/research/runs/{session.id}/bundle",
    "bundle_summary": {
        "concise_answer": ...,
        "outline_titles": [...],
        "claim_count": ...,
        "source_count": ...,
        "unresolved_question_count": ...,
    },
    "artifacts": [...],
}
```

The `artifacts` entries should be compact and include only:

- `name`
- `version`
- `content_type`
- `phase`

**Step 3: Persist the reference artifact**

When `save_artifact=True`, write `deep_research_bundle_ref.json` into the workflow step artifact directory and register it through `context["add_artifact"]`.

**Step 4: Re-run the focused adapter tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py -q -k "deep_research_load_bundle"
```

Expected: PASS

### Task 3: Register The Step Type And Expose The Schema

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/registry.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Modify: backend tests from Task 1

**Step 1: Add the static step type**

In `registry.py`, add:

- `deep_research_load_bundle`
- description should explicitly say it loads references from a completed deep research run without returning the full bundle

**Step 2: Add `/step-types` schema and save-time validation**

In `workflows.py`, add:

- `_deep_research_load_bundle_step_schema_base()`
- `_validate_deep_research_load_bundle_config(...)`
- `deep_research_load_bundle` to the workflow-definition validation schema map
- `deep_research_load_bundle` to the `/api/v1/workflows/step-types` schemas map

The explicit validator should enforce:

- one usable run reference exists
- `run_id` wins when both are present
- `run` only counts when it is an object with a non-empty `run_id`

**Step 3: Re-run backend schema tests**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k "deep_research_load_bundle or step_types"
```

Expected: PASS

### Task 4: Add Red Frontend Workflow Editor Tests

**Status:** Not Started

**Files:**
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx`

**Step 1: Add registry tests**

Add failing assertions that:

- `deep_research_load_bundle` exists in the frontend registry
- it is categorized as `research`
- its label is `Deep Research Load Bundle`
- its description explains completed-run bundle reference loading

**Step 2: Add config-panel tests**

Add failing coverage that checks the node renders:

- `run_id` as a template-editor experience
- `run`
- `save_artifact`
- helper text showing the preferred chain `{{ deep_research_wait.run_id }}`

**Step 3: Run focused frontend tests to verify failure**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
```

Expected: FAIL for missing metadata and fields.

### Task 5: Implement Workflow Editor Metadata

**Status:** Not Started

**Files:**
- Modify: `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
- Modify: frontend tests from Task 4

**Step 1: Add the load-bundle node metadata**

In `step-registry.ts`, add `deep_research_load_bundle` with:

- label `Deep Research Load Bundle`
- category `research`
- a research-appropriate icon and color
- a description that makes it clear this loads references from a completed run and does not inline the full bundle

**Step 2: Add config schema**

Expose:

- `run_id` via `template-editor`
- `run` via `json-editor`
- `save_artifact` via `checkbox`

The `run_id` description/help text should use:

- `{{ deep_research_wait.run_id }}`

as the preferred chaining example.

**Step 3: Re-run frontend tests**

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

**Step 1: Add a focused launch-wait-load workflow test**

Add or extend integration coverage so a workflow can:

- launch a deep research session
- wait for completion
- load the resulting bundle references

The final step output should prove:

- it contains `bundle_summary`
- it contains compact `artifacts`
- it does not contain the full `bundle`

**Step 2: Run the focused runtime test**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k "deep_research_load_bundle"
```

Expected: PASS

### Task 7: Run Verification And Commit

**Status:** Not Started

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-workflow-load-bundle-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_step_types.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k "deep_research_load_bundle"
```

Expected: PASS

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
  tldw_Server_API/app/core/Workflows/adapters/research/load_bundle.py \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/app/core/Workflows/registry.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  -f json -o /tmp/bandit_deep_research_workflow_load_bundle.json
```

Expected: `0` findings in the touched scope.

**Step 4: Update the plan status and commit**

Mark each task `Complete`, record residual notes, then commit with a message like:

```bash
git add \
  Docs/Plans/2026-03-07-deep-research-workflow-load-bundle-implementation-plan.md \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/app/core/Workflows/adapters/research/load_bundle.py \
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
git commit -m "feat(workflows): add deep research bundle loader"
```
