# Deep Research Workflow Select Bundle Fields Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `deep_research_select_bundle_fields` workflow step that returns only requested canonical top-level bundle fields from a completed deep research run.

**Architecture:** Add a new research workflow adapter plus config model, save-time validation, registry exposure, and workflow-editor metadata. Keep the contract fixed to a canonical allowlist, return `null` for missing allowed fields, and persist a JSON artifact when requested.

**Tech Stack:** FastAPI, Pydantic, workflow adapter registry, React workflow editor metadata, pytest, Bandit.

---

### Task 1: Add Red Tests For Backend Bundle Field Selection

**Files:**
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`

**Step 1: Write the failing adapter tests**

Add failing tests for:

- selecting fields from a raw `run_id`
- selecting fields from a prior step output object
- invalid field names
- rejecting unknown config keys at runtime
- deduping duplicate field names while preserving order
- returning `null` for allowed but absent fields
- rejecting non-completed runs
- rejecting oversized selected inline payloads
- writing `deep_research_selected_fields.json`

Use a fake completed research session and fake canonical bundle like:

```python
{
    "question": "What changed?",
    "claims": [{"text": "Claim A"}],
    "verification_summary": {"supported_claim_count": 1},
}
```

and assert:

```python
{
    "run_id": "research-session-50",
    "status": "completed",
    "selected_fields": {
        "question": "What changed?",
        "claims": [{"text": "Claim A"}],
        "unsupported_claims": None,
    },
}
```

**Step 2: Write the failing workflow API tests**

Add failing coverage that:

- `/api/v1/workflows/step-types` includes `deep_research_select_bundle_fields`
- workflow definition validation rejects unknown requested fields
- workflow definition validation rejects unknown config keys
- workflow definition validation still works when `jsonschema` is unavailable
- a saved workflow chain:
  - `deep_research_wait` with `include_bundle=false`
  - `deep_research_select_bundle_fields`
  - downstream `prompt`
  succeeds and consumes selected fields

**Step 3: Run the focused tests to verify failure**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  -q -k "select_bundle_fields or deep_research_select_bundle_fields"
```

Expected: FAIL for missing adapter, missing config, missing registry/schema wiring.

**Step 4: Commit the red tests**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "test(workflows): cover research bundle field selection"
```

### Task 2: Add Backend Config, Adapter, And Registry Wiring

**Files:**
- Create: `tldw_Server_API/app/core/Workflows/adapters/research/select_bundle_fields.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/__init__.py`
- Modify: `tldw_Server_API/app/core/Workflows/registry.py`

**Step 1: Add the config model**

In `_config.py`, add `DeepResearchSelectBundleFieldsConfig` with:

```python
run_id: str | None
run: dict[str, Any] | None
fields: list[str]
save_artifact: bool | None = True
```

Validation rules:

- at least one usable run reference
- `fields` non-empty
- every field in the fixed allowlist
- dedupe duplicate fields while preserving order
- reject unknown config keys by overriding the base adapter permissive-extra behavior for this model

**Step 2: Implement the adapter**

Create `select_bundle_fields.py` and follow the existing `load_bundle.py` pattern:

- validate config defensively
- resolve `run_id`
- require `session.status == "completed"`
- load the canonical bundle
- build:

```python
selected_fields = {
    field_name: bundle.get(field_name)
    for field_name in validated.fields
}
```

- serialize `selected_fields` and fail if it exceeds the v1 inline payload cap
- write `deep_research_selected_fields.json` when `save_artifact` is true
- return:

```python
{
    "run_id": session.id,
    "status": session.status,
    "selected_fields": selected_fields,
}
```

**Step 3: Export and register the adapter**

Update:

- `research/__init__.py`
- `registry.py`

Add:

- step name: `deep_research_select_bundle_fields`
- description aligned with the approved design

**Step 4: Run focused backend tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py -q -k "select_bundle_fields"
```

Expected: PASS

**Step 5: Commit the backend adapter slice**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/core/Workflows/adapters/research/select_bundle_fields.py \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/app/core/Workflows/adapters/research/__init__.py \
  tldw_Server_API/app/core/Workflows/registry.py \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(workflows): add research bundle field selector"
```

### Task 3: Add Save-Time Validation And Step-Type Schema Exposure

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`

**Step 1: Add schema base**

In `workflows.py`, add a schema helper like:

```python
def _deep_research_select_bundle_fields_step_schema_base() -> dict[str, Any]:
    ...
```

Expose:

- `run_id`
- `run`
- `fields`
  - array of strings
  - enum items from the fixed allowlist
- `save_artifact`

**Step 2: Add save-time validation**

Add:

```python
def _validate_deep_research_select_bundle_fields_config(cfg: dict[str, Any], *, step_id: str) -> None:
    DeepResearchSelectBundleFieldsConfig.model_validate(cfg)
```

Wire it into the explicit validation map so it still works without `jsonschema`.

**Step 3: Add example step-type metadata**

Update the step-types response example block so the new step appears alongside:

- `deep_research`
- `deep_research_wait`
- `deep_research_load_bundle`

Use a realistic example:

```python
"deep_research_select_bundle_fields": {
    ...,
    "example": {
        "run_id": "{{ deep_research_wait.run_id }}",
        "fields": ["question", "verification_summary", "unsupported_claims"],
    },
}
```

**Step 4: Run focused workflow API tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/test_workflows_api.py -q -k "select_bundle_fields"
```

Expected: PASS

**Step 5: Commit the workflow API slice**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(workflows): expose research bundle field selector"
```

### Task 4: Add Workflow Editor Node Metadata And Tests

**Files:**
- Modify: `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx`

**Step 1: Add node metadata**

In `step-registry.ts`, add:

- type: `deep_research_select_bundle_fields`
- label: `Deep Research Select Bundle Fields`
- category: `research`
- icon distinct from `deep_research_load_bundle`
- config fields:
  - `run_id` as `template-editor`
  - `run` as `json-editor`
  - `fields` as `multiselect`
- `save_artifact` as `checkbox`

Use the fixed allowlist for `fields.options`.

Add a short description/warning on `fields` that large selections can hit the inline size limit and that `deep_research_load_bundle` remains the pointer-oriented alternative.

**Step 2: Add registry tests**

Update `step-registry.test.ts` to assert:

- the new step appears in the research category
- the `fields` config field is `multiselect`
- the label and description stay stable

**Step 3: Add config-panel rendering tests**

Update `NodeConfigPanel.test.tsx` to assert:

- the node renders the `Run ID` template field
- the `fields` control renders as a multi-select with the canonical allowlist options
- the description makes the completed-run/canonical-field contract clear enough for editors

**Step 4: Run focused frontend tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
```

Expected: PASS

**Step 5: Commit the workflow editor slice**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/WorkflowEditor/step-registry.ts \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(frontend): add research bundle field selector node"
```

### Task 5: Run Focused Verification And Security Checks

**Files:**
- Modify: `Docs/Plans/2026-03-08-deep-research-workflow-select-bundle-fields-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  -q -k "select_bundle_fields or deep_research_select_bundle_fields"
```

Expected: PASS

**Step 2: Run focused frontend verification**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts \
  apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx
```

Expected: PASS

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/core/Workflows/adapters/research/select_bundle_fields.py \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/app/api/v1/endpoints/workflows.py \
  -f json -o /tmp/bandit_deep_research_select_bundle_fields.json
```

Expected: `0` findings and `0` errors

**Step 4: Mark this plan complete**

Update task statuses and append a short verification note with:

- backend test result
- frontend test result
- Bandit result

**Step 5: Commit the finalized plan**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  Docs/Plans/2026-03-08-deep-research-workflow-select-bundle-fields-implementation-plan.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "docs(research): finalize bundle field selector plan"
```

## Execution Record

Status: Complete

Verification:
- Backend workflow scope: `106 passed` in `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py` and `tldw_Server_API/tests/Workflows/test_workflows_api.py`
- Frontend workflow-editor scope: `21/21` passed in `step-registry.test.ts` and `NodeConfigPanel.test.tsx`
- Bandit: `0` findings, `0` errors in `/tmp/bandit_deep_research_select_bundle_fields.json`
