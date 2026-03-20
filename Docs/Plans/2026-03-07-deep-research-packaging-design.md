# Deep Research Packaging Slice Design

## Overview

This slice makes the deep research run lifecycle fully worker-driven through completion. The packaging phase will read synthesis artifacts, build the canonical final package, write `bundle.json`, and mark the session `completed`.

## Goals

- Make `packaging` the terminal execution phase for autonomous and checkpointed runs.
- Build the final research package from persisted synthesis artifacts rather than manual service inputs.
- Keep export/read concerns separate from package creation.
- Preserve citation validation and fail the packaging phase on incomplete synthesis outputs.

## Non-Goals

- No new export API surface.
- No additional package formats in the worker.
- No new human-review checkpoints.
- No change to the markdown/JSON export adapter contract.

## Architecture

The packaging slice extends `handle_research_phase_job(...)` in `tldw_Server_API/app/core/Research/jobs.py` with a `packaging` branch that:

1. loads the effective plan and synthesis artifacts
2. derives package inputs from artifacts
3. calls `build_final_package(...)`
4. writes `bundle.json`
5. transitions the session to `completed`

The worker reads:

- `approved_plan.json` or `plan.json`
- `outline_v1.json`
- `claims.json`
- `report_v1.md`
- `source_registry.json`
- `synthesis_summary.json`

`ResearchService.approve_checkpoint(...)` should now enqueue packaging when `outline_review` is approved. `plan_review` already enqueues `collecting`; packaging becomes the second checkpointed phase that automatically resumes via Jobs.

`ResearchService.build_package(...)` remains available as a thin wrapper for manual/test use, but it is no longer the primary lifecycle path.

## Package Contract

`bundle.json` remains the canonical final artifact:

```json
{
  "question": "string",
  "brief": {"query": "string"},
  "outline": {"sections": []},
  "report_markdown": "string",
  "claims": [],
  "source_inventory": [],
  "unresolved_questions": []
}
```

Package inputs are derived as follows:

- `brief.query` from the effective plan query
- `outline` from `outline_v1.json`
- `report_markdown` from `report_v1.md`
- `claims` from `claims.json`
- `source_inventory` from `source_registry.json`
- `unresolved_questions` from `synthesis_summary.json`

## State Transitions

- autonomous: `packaging -> completed`
- checkpointed: `awaiting_outline_review -> packaging -> completed`

On successful packaging:

- `bundle.json` is written
- `active_job_id` is cleared
- `completed_at` is set through the session phase update

On failure:

- the worker raises a phase error
- no completion state is recorded

## Validation Rules

Packaging reuses `build_final_package(...)` validation:

- brief must contain a query
- report markdown must be non-empty
- every claim must have citations

This keeps citation discipline enforced at the final boundary even if upstream artifacts drift.

## Testing

Add or extend:

- worker tests for successful packaging completion
- worker tests for packaging failure on invalid claims
- service test for `outline_review` approval enqueueing packaging
- e2e test for a full run reaching `completed` and exporting from generated `bundle.json`

## Follow-On Work

After packaging is worker-driven, the next likely improvements are:

- expose a read endpoint for `bundle.json`
- auto-export or register package artifacts in file-artifact workflows
- add resumable packaging retries with richer failure visibility
