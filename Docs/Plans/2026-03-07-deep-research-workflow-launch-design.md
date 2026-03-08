# Deep Research Workflow Launch Integration Design

## Summary

This slice exposes deep research as a first-class workflow step without teaching the workflow engine to own the research runtime.

The design adds a new `deep_research` workflow step that launches a normal deep-research session through the existing `ResearchService`, returns a small launch reference object, and optionally stores that reference as a workflow artifact. The step is explicitly launch-only in v1. It does not block the workflow while the research session plans, pauses for checkpoints, or packages results.

## Goals

- Let workflows launch deep research through the same backend service used by the `/research` console.
- Return a stable run reference object that downstream workflow steps can store, log, or hand off.
- Expose the new step cleanly in the workflow editor and step-types introspection API.
- Keep ownership, launch parameters, and artifact semantics consistent with the existing research module.

## Non-Goals

- No workflow step that waits across deep-research checkpoints in v1.
- No workflow-native editing of research checkpoints in this slice.
- No second research engine embedded inside workflow execution.
- No backend self-calls to the HTTP research endpoints.

## Recommended Approach

Add a normal workflow adapter named `deep_research` and treat deep research as an external long-running capability launched from workflows, not as a special engine mode.

This is preferred over adding workflow-engine-native waiting semantics because the research module already has its own Jobs-backed lifecycle, checkpoint approvals, pause/resume/cancel controls, and replayable events. Keeping the workflow step launch-only avoids coupling the workflow runtime to that separate lifecycle before there is a real need for cross-runtime waiting behavior.

## Architecture

### Step Shape

Add one new workflow step type:

- `deep_research`

Default execution behavior:

- launch a deep-research session
- enqueue its normal planning phase through the existing research service
- return immediately

The workflow step becomes a thin launcher and reference producer. The canonical detailed inspection surface remains `/research`.

### Launch-Only Contract

The step is hardcoded to launch-only in v1.

That means:

- no `wait_mode` config yet
- no workflow step suspension until the research session finishes
- no workflow retries that try to resume a partially completed research session in place

If a future slice adds waiting behavior, it should be explicit and opt-in rather than silently changing this step's meaning.

## Step Contract

### Config

The `deep_research` step config is:

- `query`
  - required string or templated string
- `source_policy`
  - optional
  - default `balanced`
- `autonomy_mode`
  - optional
  - default `checkpointed`
- `limits_json`
  - optional object
- `provider_overrides`
  - optional object
- `save_artifact`
  - optional boolean
  - default `true`

Constraints:

- the workflow adapter resolves templated config values through the normal workflow engine template-resolution path
- this slice does not expose raw research-internal fields beyond the public run creation contract
- validation should happen in two places:
  - at workflow-definition save time through the workflows endpoint schema map
  - defensively inside the adapter with the Pydantic config model at execution time

### Output

The step output is intentionally small and stable:

- `run_id`
- `status`
- `phase`
- `control_state`
- `console_url`
- `bundle_url`
- `query`
- `source_policy`
- `autonomy_mode`

If `save_artifact` is true, the same object is persisted as a workflow artifact for operator inspection and downstream step reuse.

## Backend Design

### Workflow Adapter

Add a new workflow adapter under:

- `tldw_Server_API/app/core/Workflows/adapters/research/`

The adapter should:

1. accept validated workflow config
2. resolve the workflow owner from adapter context
3. call `ResearchService.create_session(...)` directly
4. build the launch reference object
5. optionally write a full JSON launch payload file into the workflow step artifact directory and register it with `add_artifact`
6. return the launch reference object as the step result

The adapter must not call:

- `/api/v1/research/runs`
- any other internal HTTP endpoint

It should call the existing research core directly so workflows and the `/research` page keep sharing the same launch path and session semantics.

### Config Model

Add a Pydantic config model alongside the existing research adapter config models in:

- `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`

This config model should mirror the supported research-run creation contract and keep validation local to the adapter layer.

It is not enough to rely on decorator metadata alone because the workflow runtime currently passes raw config dicts to adapters. The adapter should therefore call `DeepResearchConfig.model_validate(...)` defensively before launching the research session.

### Adapter Registration

Update the existing workflow adapter registration surfaces:

- `tldw_Server_API/app/core/Workflows/adapters/research/__init__.py`
- `tldw_Server_API/app/core/Workflows/adapters/__init__.py`

This keeps:

- decorator registration active at import time
- backward-compatible adapter exports working

### Step Registry And Introspection

Update:

- `tldw_Server_API/app/core/Workflows/registry.py`
- `tldw_Server_API/app/api/v1/endpoints/workflows.py`

`registry.py` should gain the human-facing step type entry.

`workflows.py` should expose a proper JSON schema for `deep_research` through `/api/v1/workflows/step-types`, including the launch-only description so the editor and any API consumers understand the intended behavior.

It should also add a `deep_research` validation schema to the workflow-definition validation map so invalid config can be rejected before execution instead of relying on runtime failure alone.

## Frontend Design

### Workflow Editor Presence

Expose the new step as a normal node in:

- `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`

Editor metadata:

- label: `Deep Research Run`
- category: `research`
- icon/color aligned with research nodes
- description should explicitly say it launches a session and does not wait for completion

### Editor Config Fields

Expose these config fields:

- `query`
  - `template-editor`
  - required
- `source_policy`
  - `select`
- `autonomy_mode`
  - `select`
- `save_artifact`
  - `checkbox`
- `timeout_seconds`
  - only if it is already part of the generic schema flow, and described as bounding launch only

The node should feel like a launcher/reference step, not like an inline research execution environment.

Because `NodeConfigPanel` prefers server schema fields when `/step-types` returns a schema, this slice must ensure the backend schema and the frontend registry agree on field intent. In practice that means either:

- the server schema descriptions and shapes are sufficient for the existing schema-to-field mapper to infer the intended controls, or
- the frontend adds a small deep-research override so `query` still renders as a `template-editor` and the select fields remain explicit.

The design goal is not “add metadata in one place,” but “the editor actually renders the intended controls.”

## Data Flow

Workflow run:

1. engine resolves step config templates
2. `deep_research` adapter receives the resolved config
3. adapter derives `owner_user_id` from workflow context
4. adapter creates a research session through `ResearchService.create_session(...)`
5. research service enqueues the planning phase as normal
6. adapter returns the launch reference object
7. workflow continues immediately to downstream steps

Optional artifact path:

1. adapter serializes the launch reference object
2. adapter writes it to a JSON file such as `deep_research_launch.json` in the per-step artifact directory
3. adapter registers that file as a workflow artifact if `save_artifact` is enabled
3. operators can inspect that artifact from workflow run details later

## Error Handling

### Validation Errors

- invalid step config should fail workflow definition validation or step-types-based client validation before launch
- templated `query` resolving to empty should fail the step clearly rather than creating a malformed research session

### Launch Errors

- if `ResearchService.create_session(...)` raises, the workflow step fails normally
- there is no retry-special casing in this slice beyond existing workflow retry semantics

### Ownership

- the workflow owner must become the research session owner
- console URLs and bundle URLs should therefore point at resources the same user can read

## Testing Strategy

### Backend

Add tests for:

- adapter launch through the workflow runtime
- templated `query` resolution
- launch output shape
- artifact persistence when `save_artifact` is true
- `/api/v1/workflows/step-types` includes `deep_research`
- workflow definition validation accepts the new config

### Frontend

Add tests for:

- `deep_research` appears in the workflow editor registry
- `Deep Research Run` uses the `research` category
- config fields and descriptions are exposed correctly
- backend/frontend registry parity includes `deep_research`

## Risks And Mitigations

### Registry Drift

Risk:

- backend step registry, `/step-types` schema, and frontend step registry drift apart

Mitigation:

- update all three in the same slice
- add parity-focused tests

### False Expectation Of Synchronous Completion

Risk:

- users may assume the workflow step waits for research completion

Mitigation:

- make launch-only behavior explicit in backend schema descriptions and frontend node copy

### Hidden HTTP Coupling

Risk:

- an internal HTTP call path would duplicate auth and request-shaping logic

Mitigation:

- keep the adapter on the core `ResearchService` path only

## Rollout Notes

This slice is intentionally the thinnest useful workflow integration:

- workflows can launch deep research
- workflows get a stable run reference back
- the dedicated `/research` console remains the canonical place to inspect and control the run

Any future `wait_for_completion` behavior should be treated as a separate design slice, because it changes workflow runtime semantics rather than merely adding another launch surface.
