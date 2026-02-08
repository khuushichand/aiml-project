# WebSearch Diagnostics Contract (4chan + Aggregated Pipeline)

Date: 2026-02-08  
Scope: `POST /api/v1/research/websearch` pipeline (`generate_and_search`) and provider-level diagnostics from `search_web_4chan`.

## Problem

`search_web_4chan` emits board-level `warnings` and an `error` for all-board failure, but the aggregated pipeline response can drop these fields before returning API output.

This contract defines canonical merge behavior so diagnostics are observable while preserving backward compatibility.

## Output Contract

The aggregated `web_search_results_dict` MAY include the following additive diagnostic fields:

- `warnings`: `list[Any]` (provider-shaped warning entries, preserved as-is).
- `error`: `str | None` (aggregate-level failure summary).
- `processing_error`: existing field, reserved for pipeline-level processing failures.

No existing required fields are removed or renamed.

## Merge Rules in `generate_and_search`

Per query, provider output (`raw_results`) can include `results`, `warnings`, `error`, and `processing_error`.

1. `processing_error`
- If `raw_results.processing_error` is present, that query remains skipped as today.
- `processing_error` semantics do not change in this remediation track.

2. `warnings`
- If `raw_results.warnings` is a non-empty list, append entries to aggregate `web_search_results_dict.warnings`.
- Preserve provider entry shape (no destructive normalization).
- Preserve deterministic order: query order first, provider order second.

3. `error`
- Track non-empty provider errors from `raw_results.error`.
- If aggregate result set is empty at end of all queries and at least one provider error exists:
  - set `web_search_results_dict.error` to the first observed provider error.
- If aggregate result set is non-empty:
  - leave `web_search_results_dict.error` unset/`None`.
  - retain observability by surfacing provider errors as warning entries.

## Expected Behavior

Single-query (`subquery_generation=false`):
- 4chan partial board failure: results may exist, `warnings` present, `error` absent.
- 4chan all-board failure: no results, `warnings` present, `error` present.

Multi-query (`subquery_generation=true`):
- Any query-level warnings are accumulated.
- If at least one query yields results, aggregate `error` remains unset.
- If no queries yield results and at least one provider error exists, aggregate `error` is set.

## Backward Compatibility

- This is additive: clients ignoring unknown fields continue to work.
- Existing payloads and validation rules are unchanged.
- No response schema breaking change is introduced.
