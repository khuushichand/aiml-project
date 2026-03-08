# Deep Research Workflow Wait Integration Design

## Summary

This slice adds workflow-side consumption for deep research without changing the existing `deep_research` launch step.

The design introduces a separate `deep_research_wait` workflow step that accepts either a raw `run_id` or the full output of a prior `deep_research` launcher step, polls the existing research service until the run reaches a terminal state, and returns terminal metadata plus the final bundle when requested. The step remains a normal workflow adapter. It does not teach the workflow engine to subscribe to research Jobs or SSE directly.

## Goals

- Let workflows block on a deep-research run when they explicitly need terminal output.
- Keep the existing `deep_research` launch step stable and launch-only.
- Return stable terminal metadata and the final bundle for downstream workflow steps.
- Preserve ownership, artifact semantics, and research-service reuse across workflow integration.

## Non-Goals

- No workflow-engine-native waiting mode for research sessions.
- No SSE-driven or replay-log-driven workflow runtime behavior.
- No checkpoint-aware workflow suspension beyond terminal polling.
- No replacement of the `/research` console as the canonical inspection surface.

## Recommended Approach

Add a second workflow adapter named `deep_research_wait` and keep waiting behavior separate from the existing launcher.

This is preferred over adding an optional wait mode to `deep_research` because launch and wait are materially different runtime behaviors. The existing launcher is intentionally thin and non-blocking. Overloading it with a second execution mode would blur step semantics, complicate workflow definitions, and make step outputs less predictable. A separate wait step preserves the clean chain:

1. `deep_research`
2. downstream workflow logic if needed
3. `deep_research_wait`

## Architecture

### Step Shape

Add one new workflow step type:

- `deep_research_wait`

Default execution behavior:

- resolve a run reference
- poll the research session state through the existing research core
- stop when the session reaches `completed`, `failed`, or `cancelled`
- optionally load and return the final bundle

The step remains a thin workflow-side waiter. The research module still owns the run lifecycle.

### Separate-Step Contract

The wait behavior is intentionally separate from the existing launch step.

That means:

- `deep_research` stays launch-only
- `deep_research_wait` is the only workflow step that blocks for terminal research state in v1
- downstream workflows can opt into waiting explicitly instead of inheriting that behavior accidentally

## Step Contract

### Config

The `deep_research_wait` step config is:

- `run_id`
  - optional templated string
- `run`
  - optional object containing `run_id`
- `include_bundle`
  - optional boolean
  - default `true`
- `fail_on_cancelled`
  - optional boolean
  - default `true`
- `fail_on_failed`
  - optional boolean
  - default `true`
- `poll_interval_seconds`
  - optional number
  - default `2`
- `timeout_seconds`
  - optional number
  - bounded by normal workflow timeout handling
- `save_artifact`
  - optional boolean
  - default `true`

Constraints:

- at least one usable run reference must resolve
- if both `run_id` and `run` are provided, `run_id` wins
- the resolved `run_id` must be non-empty after template resolution
- `poll_interval_seconds` should be clamped to sane minimum and maximum bounds
- config validation should happen in two places:
  - at workflow-definition save time through the workflows endpoint schema map
  - defensively inside the adapter with a Pydantic config model at execution time

### Output

The step output should be small but useful:

- `run_id`
- `status`
- `phase`
- `control_state`
- `completed_at`
- `bundle_url`
- `bundle`
  - only when available and `include_bundle` is true
- terminal metadata such as failure or cancellation context when available from the session model

If `save_artifact` is true, the full output object is persisted as a JSON workflow artifact for operator inspection and downstream reuse.

## Backend Design

### Workflow Adapter

Add a new workflow adapter under:

- `tldw_Server_API/app/core/Workflows/adapters/research/`

The adapter should:

1. validate raw config with a dedicated `DeepResearchWaitConfig`
2. resolve a usable run reference from either `run_id` or `run.run_id`
3. derive the workflow owner from adapter context
4. call `ResearchService.get_session(...)` directly in a polling loop
5. stop on `completed`, `failed`, or `cancelled`
6. optionally load the final bundle through the research core when the run completed
7. optionally write a full JSON wait-result file into the workflow step artifact directory and register it with `add_artifact`
8. return the wait-result object as the step result

The adapter must not call:

- `/api/v1/research/runs`
- the research SSE endpoint
- any internal HTTP endpoint

It should call the research core directly so workflows and the `/research` console keep sharing the same session and bundle semantics.

### Config Model

Add a Pydantic config model alongside the existing research adapter config models in:

- `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`

This config model should mirror the approved wait-step contract and keep validation local to the adapter layer.

As with the launch step, the adapter must call `DeepResearchWaitConfig.model_validate(...)` defensively because the workflow runtime passes raw config dicts to adapters.

### Adapter Registration

Update:

- `tldw_Server_API/app/core/Workflows/adapters/research/__init__.py`
- `tldw_Server_API/app/core/Workflows/adapters/__init__.py`

This keeps decorator registration and public exports aligned with the rest of the workflow adapter package.

### Step Registry And Introspection

Update:

- `tldw_Server_API/app/core/Workflows/registry.py`
- `tldw_Server_API/app/api/v1/endpoints/workflows.py`

`registry.py` should gain a human-facing step type entry for `deep_research_wait`.

`workflows.py` should expose a proper JSON schema for `deep_research_wait` through `/api/v1/workflows/step-types`, including the waiting semantics in the description and the approved config fields.

It should also add a `deep_research_wait` validation schema to the workflow-definition validation map so malformed configs fail at save time instead of only at runtime.

## Frontend Design

### Workflow Editor Presence

Expose the new step as a normal node in:

- `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`

Editor metadata:

- label: `Deep Research Wait`
- category: `research`
- icon and color aligned with research nodes
- description should explicitly say it waits for a launched run to finish and can return the final bundle

### Editor Config Fields

Expose these config fields:

- `run_id`
  - `template-editor`
- `run`
  - object-oriented field, likely `json-editor`
- `include_bundle`
  - `checkbox`
- `fail_on_cancelled`
  - `checkbox`
- `fail_on_failed`
  - `checkbox`
- `poll_interval_seconds`
  - numeric field
- `timeout_seconds`
  - numeric field
- `save_artifact`
  - `checkbox`

The node should feel like an explicit terminal wait step, not like a second launcher.

As with the launcher, the backend schema and the frontend registry must cooperate so `run_id` still renders as a template-oriented field instead of degrading to plain text under server-schema precedence.

## Data Flow

Workflow run:

1. `deep_research` launches a session and returns `run_id`
2. `deep_research_wait` receives either the prior step output or a raw `run_id`
3. the adapter resolves the actual `run_id`
4. the adapter polls `ResearchService.get_session(...)`
5. if the run completes and `include_bundle` is true, the adapter loads the final bundle
6. the adapter returns the terminal result object
7. downstream workflow steps can consume `bundle` directly when present

Optional artifact path:

1. the adapter serializes the wait result
2. the adapter writes a file such as `deep_research_wait.json` in the per-step artifact directory
3. the adapter registers that file as a workflow artifact if `save_artifact` is enabled
4. operators can inspect the wait result from workflow run details later

## Error Handling

### Validation Errors

- invalid wait-step config should fail workflow definition validation or step-types-based client validation before execution
- missing or empty resolved run reference should fail clearly
- invalid `poll_interval_seconds` values should be clamped or rejected consistently

### Timeout Handling

- if the run does not reach terminal state before `timeout_seconds`, the workflow step should fail clearly
- the timeout should bound workflow waiting, not mutate the research session itself

### Terminal Outcomes

- `completed`
  - return success result and optional bundle
- `failed`
  - fail the workflow step when `fail_on_failed` is true
  - otherwise return terminal metadata without raising
- `cancelled`
  - fail the workflow step when `fail_on_cancelled` is true
  - otherwise return terminal metadata without raising

### Ownership

- the workflow owner must remain the research session owner checked by the research service
- the wait step must not permit reading other users' runs by arbitrary `run_id`

## Testing Strategy

### Backend

Add tests for:

- waiting from a raw `run_id`
- waiting from a prior launcher output object
- completed run returns `bundle` when requested
- timeout handling
- `failed` and `cancelled` behavior under both fail and allow configs
- workflow artifact persistence when `save_artifact` is true
- `/api/v1/workflows/step-types` includes `deep_research_wait`
- workflow definition validation accepts valid config and rejects malformed config

### Frontend

Add tests for:

- `deep_research_wait` appears in the workflow editor registry
- `Deep Research Wait` uses the `research` category
- config fields render with the intended controls
- backend/frontend registry parity includes `deep_research_wait`
- descriptive text makes launch-then-wait usage obvious

## Risks And Mitigations

### Worker Occupancy

If waits are too long or poll too aggressively, workflow workers can be tied up unnecessarily.

Mitigation:

- keep polling conservative
- bound `timeout_seconds`
- do not add checkpoint-aware special handling in this slice

### Hidden Runtime Coupling

If the step starts depending on SSE or Jobs internals, workflow integration will become harder to reason about.

Mitigation:

- keep waiting inside a normal polling adapter that only calls the research core

### Semantic Drift

If `deep_research` and `deep_research_wait` begin to overlap in responsibility, workflow authors will get confused.

Mitigation:

- keep `deep_research` launch-only
- keep `deep_research_wait` terminal-only
- make both descriptions explicit in backend schema and frontend editor text

## Exit Condition

This slice is complete when workflows can launch a research run with `deep_research`, block for terminal completion with `deep_research_wait`, and pass the resulting bundle to downstream steps without bypassing the existing research service or duplicating research runtime logic.
