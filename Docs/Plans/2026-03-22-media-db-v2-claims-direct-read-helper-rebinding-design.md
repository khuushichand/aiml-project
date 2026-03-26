# Media DB V2 Claims Direct Read Helper Rebinding Design

## Summary

Rebind the three direct claims read helpers,
`MediaDatabase.get_claims_by_media(...)`,
`MediaDatabase.get_claim_with_media(...)`, and
`MediaDatabase.get_claims_by_uuid(...)`, onto a package-owned runtime helper so
the canonical `MediaDatabase` no longer owns those read paths through legacy
globals. Keep `list_claims(...)` out of scope for a later, wider filter/scope
tranche.

## Why This Slice

- These three methods are cohesive direct-read helpers:
  - media-local claim listing
  - single-claim lookup with media metadata
  - UUID lookup for notification payload assembly
- They already have meaningful caller-facing coverage in:
  - `tldw_Server_API/tests/Claims/test_ingestion_claims_sql.py`
  - `tldw_Server_API/tests/Claims/test_claims_endpoints_api.py`
  - `tldw_Server_API/tests/Claims/test_claims_items_api.py`
  - `tldw_Server_API/tests/Claims/test_claim_review_rule_assignment.py`
- `list_claims(...)` is materially wider:
  - scoped filtering
  - org/team/owner constraints
  - review-state and cluster filters
  - pagination normalization

## In Scope

- `get_claims_by_media(...)`
- `get_claim_with_media(...)`
- `get_claims_by_uuid(...)`

## Out Of Scope

- `list_claims(...)`
- claims CRUD/update methods
- claims search methods
- bootstrap/schema helpers

## Preserved Invariants

- `get_claims_by_media(...)` still:
  - excludes soft-deleted claims
  - orders by `chunk_index ASC, id ASC`
  - returns dict rows
- `get_claim_with_media(...)` still:
  - returns claim row plus media visibility metadata
  - respects `include_deleted`
  - respects `get_scope()` visibility filtering
  - returns `None` when the claim is filtered out or missing
- `get_claims_by_uuid(...)` still:
  - fast-returns `[]` for empty input
  - uses placeholder expansion for the supplied UUID list
  - returns only the current selected columns
  - preserves input-query semantics without adding deleted filtering

## Test Strategy

Add direct regressions for:

- canonical direct-read methods no longer using legacy globals
- legacy `Media_DB_v2` methods delegating through a live package module import

Add focused helper-path tests for:

- `get_claims_by_media(...)` ordering and deleted-row exclusion
- `get_claim_with_media(...)` include-deleted behavior and scope filtering
- `get_claims_by_uuid([])` fast return plus multi-UUID row lookup

Keep broader guards from:

- `test_ingestion_claims_sql.py`
- `test_claims_endpoints_api.py`
- `test_claims_items_api.py`
- `test_claim_review_rule_assignment.py`

## Success Criteria

- normalized ownership count drops `31 -> 28`
- no behavior regressions in claims-service/API read paths
- worktree remains clean after verification
