# Deep Research Workflow Select Bundle Fields Design

## Summary

Add a new workflow step, `deep_research_select_bundle_fields`, that safely inlines selected canonical top-level fields from a completed deep research bundle into workflow outputs.

This step is intentionally separate from:

- `deep_research`, which launches a run
- `deep_research_wait`, which waits on lifecycle
- `deep_research_load_bundle`, which returns pointer-style references

The new step exists for the narrow case where a downstream workflow genuinely needs selected bundle data in workflow state.

## Goals

- allow downstream workflow steps to consume selected canonical bundle fields without loading the entire bundle by default
- keep the field-selection contract fixed and explicit
- avoid inventing derived fields or dotted-path semantics
- preserve deterministic behavior for missing optional research outputs by returning `null`

## Non-Goals

- arbitrary dotted-path access into `bundle.json`
- nested field projections
- field aliasing, transforms, or summarization
- reusing `deep_research_load_bundle` for inline projection

## Recommended Approach

Create a separate workflow adapter, `deep_research_select_bundle_fields`.

This is preferable to extending `deep_research_load_bundle` because the two steps solve different problems:

- `deep_research_load_bundle` is pointer-oriented and should stay small and stable
- `deep_research_select_bundle_fields` is an explicit opt-in to place chosen bundle content into workflow state

That separation keeps workflows readable:

1. `deep_research`
2. `deep_research_wait`
3. `deep_research_load_bundle` if references are enough
4. `deep_research_select_bundle_fields` only when inline bundle content is needed

## Canonical Field Allowlist

V1 uses a fixed allowlist of canonical top-level bundle fields only:

- `question`
- `brief`
- `outline`
- `report_markdown`
- `claims`
- `source_inventory`
- `unresolved_questions`
- `verification_summary`
- `unsupported_claims`
- `contradictions`
- `source_trust`

The step must not synthesize new summary fields or expose non-canonical data.

## Step Contract

### Inputs

- `run_id`
  - optional templated string
- `run`
  - optional object containing `run_id`
- `fields`
  - required list of allowlisted field names
- `save_artifact`
  - optional boolean, default `true`

### Validation

- at least one usable run reference must resolve
- if both `run_id` and `run` are provided, `run_id` wins
- `fields` must be non-empty
- requested field names must all be in the fixed allowlist
- duplicate field names are deduped while preserving request order

### Runtime Requirements

- the referenced research session must be `completed`
- the adapter loads the canonical bundle through `ResearchService.get_bundle(...)`
- every requested field appears in output
- if an allowed field is absent in the bundle, the output value is `null`

### Outputs

- `run_id`
- `status`
- `selected_fields`
  - requested keys mapped to canonical values or `null`

## Backend Design

Add a new adapter module:

- `tldw_Server_API/app/core/Workflows/adapters/research/select_bundle_fields.py`

Related backend changes:

- add `DeepResearchSelectBundleFieldsConfig` to `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`
- export/register the new adapter in `tldw_Server_API/app/core/Workflows/adapters/research/__init__.py`
- add the new step type to `tldw_Server_API/app/core/Workflows/registry.py`
- add save-time validation and `/step-types` schema coverage in `tldw_Server_API/app/api/v1/endpoints/workflows.py`

The adapter should:

1. validate config defensively at runtime
2. resolve `run_id`
3. require `completed` session state
4. load the canonical bundle
5. build `selected_fields` from the fixed allowlist
6. optionally persist `deep_research_selected_fields.json` as a workflow artifact

## Frontend Design

Expose `deep_research_select_bundle_fields` as a normal research-category node in:

- `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`

Editor behavior:

- label: `Deep Research Select Bundle Fields`
- category: `research`
- `run_id` remains the primary template-oriented field
- `run` remains an optional advanced JSON field
- `fields` uses a multi-select/checklist over the fixed allowlist
- `save_artifact` uses the existing checkbox pattern

No new editor mechanics are needed if the server schema exposes `fields` as an enum-backed array; the existing workflow editor already supports `multiselect`.

## Artifact Behavior

If `save_artifact=true`, the adapter writes:

- `deep_research_selected_fields.json`

This artifact should contain the returned object:

- `run_id`
- `status`
- `selected_fields`

That keeps operator inspection available without changing the runtime contract.

## Error Handling

The step should fail for:

- missing or unusable run reference
- non-completed research run
- invalid requested field names

The step should not fail for:

- an allowed but absent field in the completed bundle

In that case, the corresponding output value is `null`.

## Testing

Backend tests should cover:

- raw `run_id` input
- prior-step object input
- invalid field names
- deduped fields preserving order
- `null` for absent allowed fields
- rejection of non-completed runs
- artifact persistence
- workflow definition validation and `/step-types` exposure

Frontend tests should cover:

- registry visibility for the new node
- correct metadata and category
- `fields` rendering as a multi-select
- schema/registry parity for the new step

## Expected Outcome

After this slice, workflows will have a safe, explicit way to inline selected canonical deep research bundle fields while keeping the pointer-oriented load step unchanged.
