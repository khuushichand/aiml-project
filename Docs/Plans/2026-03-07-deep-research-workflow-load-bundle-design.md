# Deep Research Workflow Load Bundle Design

**Date:** 2026-03-07

## Goal

Add a workflow-safe consumption step for completed deep research runs that returns lightweight references and summary data instead of copying the full bundle into workflow state.

## Why This Slice Is Next

The workflow integration now has:

- `deep_research` to launch a durable research session
- `deep_research_wait` to block until terminal completion

The missing piece is safe downstream consumption. Today, the only way for workflows to get research output is to make `deep_research_wait` inline the full bundle, which grows workflow state and mixes lifecycle waiting with result-shaping concerns.

## Recommended Approach

Add a separate workflow step: `deep_research_load_bundle`.

This step should:

- accept `run_id` or a prior step output object with `run_id`
- require the referenced research session to be `completed`
- load `bundle.json` and the current artifact manifest through `ResearchService`
- return a compact reference object by default
- persist a full JSON reference artifact for operator/debug inspection

This keeps workflow graphs explicit:

- `deep_research` launches
- `deep_research_wait` waits
- `deep_research_load_bundle` consumes

## Alternatives Considered

### 1. Extend `deep_research_wait`

Add a pointer-only mode to `deep_research_wait` and make full bundle inclusion optional.

Why not:

- overloads one step with both waiting and result shaping
- makes workflow graphs harder to read
- keeps the current state-bloat problem close to the wait step contract

### 2. Add `deep_research_load_bundle` (recommended)

Separate post-completion consumption into its own workflow step.

Why this is best:

- preserves the launch-only and wait-only step boundaries already established
- gives downstream steps a stable reference-oriented output
- avoids repeating the bundle-in-workflow-state problem by default

### 3. Add a generic `deep_research_load`

Support bundle plus arbitrary artifact reads in one generalized adapter.

Why not yet:

- too broad for the current need
- drifts toward intermediate artifact browsing instead of completed-run consumption
- would require more UI/config surface than warranted for v1

## Architecture

Add a new adapter under `tldw_Server_API/app/core/Workflows/adapters/research/` named `deep_research_load_bundle`.

Execution path:

1. validate config defensively inside the adapter
2. resolve `run_id` from either:
   - `run_id`
   - `run.run_id`
3. load the research session via `ResearchService.get_session(...)`
4. fail unless the session is `completed`
5. load the final bundle via `ResearchService.get_bundle(...)`
6. load the artifact manifest via existing research service methods
7. derive a compact summary object from the bundle
8. optionally write `deep_research_bundle_ref.json` into the workflow step artifact directory and register it
9. return a lightweight result object

This step should call the research core directly and never call the HTTP research endpoints.

## Step Contract

### Config

- `run_id`
  - optional templated string
- `run`
  - optional object containing `run_id`
- `save_artifact`
  - optional bool, default `true`

### Validation Rules

- exactly one usable run reference must resolve
- if both `run_id` and `run` are provided, `run_id` wins
- resolved `run_id` must be non-empty
- the research session must exist and be owned by the workflow user
- the research session must be `completed`

### Output

- `run_id`
- `status`
- `phase`
- `control_state`
- `completed_at`
- `bundle_url`
- `bundle_summary`
  - `concise_answer`
  - `outline_titles`
  - `claim_count`
  - `source_count`
  - `unresolved_question_count`
- `artifacts`
  - compact manifest entries containing only:
    - `name`
    - `version`
    - `content_type`
    - `phase`

The full `bundle` object should not be returned in normal workflow outputs.

## Artifact Behavior

When `save_artifact=true`, the adapter should write a file such as `deep_research_bundle_ref.json` into the per-step artifact directory and register it through `context["add_artifact"]`.

That JSON should contain the same lightweight reference payload returned by the step.

This gives operators and downstream tooling a persistent record without forcing the full research package into workflow state.

## Frontend Workflow Editor

Expose a new workflow node:

- label: `Deep Research Load Bundle`
- category: `research`
- description: loads references from a completed deep research run without inlining the full bundle

Config fields:

- `run_id`
  - `template-editor`
- `run`
  - `json-editor`, optional advanced path
- `save_artifact`
  - `checkbox`

Help text should make the primary chain explicit:

- recommended usage after `Deep Research Wait`
- primary pattern: `{{ deep_research_wait.run_id }}`

## Error Handling

The adapter should fail clearly when:

- `run_id` cannot be resolved
- the run does not exist
- the run is not owned by the workflow user
- the run is not `completed`
- `bundle.json` cannot be loaded for a supposedly completed run

The non-completed failure message should say this step is for completed runs only.

## Testing Strategy

### Backend

Add tests for:

- loading from raw `run_id`
- loading from a prior wait/launch output object
- rejecting non-completed runs
- returning compact `bundle_summary` and artifact refs
- writing `deep_research_bundle_ref.json`
- `/step-types` includes `deep_research_load_bundle`
- save-time workflow validation accepts valid config and rejects invalid config

### Frontend

Add tests for:

- `Deep Research Load Bundle` appearing in the workflow registry
- correct `research` category assignment
- correct description text
- config-panel rendering of `run_id`, `run`, and `save_artifact`
- `run_id` rendered with template-oriented helper text

## Risks

### Summary Drift

If the bundle evolves, a brittle summary extractor could break.

Mitigation:

- keep summary derivation defensive and minimal
- prefer optional access with sane defaults

### Hidden Bundle Growth

It is easy to accidentally reintroduce full-bundle outputs.

Mitigation:

- make the normal return contract reference-oriented
- test explicitly that only summary fields are returned

### Misuse On In-Progress Runs

Users may point this step at a run that has not finished.

Mitigation:

- fail with a clear completed-run-only error message
- keep `deep_research_wait` as the intended predecessor step

## Exit Condition

This slice is complete when workflows can consume completed deep research output through a dedicated reference-oriented step, without copying the full bundle into workflow state by default.
