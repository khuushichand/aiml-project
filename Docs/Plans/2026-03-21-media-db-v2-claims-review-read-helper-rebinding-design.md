# Media DB V2 Claims Review Read Helper Rebinding Design

## Summary

Rebind the legacy claims review read layer onto a package-owned runtime module
so the canonical `MediaDatabase` no longer owns those methods through legacy
globals. Preserve the existing claims-service and review API contracts for
`list_claim_review_history(...)` and `list_review_queue(...)` while explicitly
deferring review mutation, review rules, analytics, monitoring, clustering, and
broader claims CRUD/search helpers.

## Scope

In scope:
- `list_claim_review_history(...)`
- `list_review_queue(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for history ordering and queue filtering/visibility
- reuse of broader review API caller-facing guards

Out of scope:
- `update_claim_review(...)`
- `list_claim_review_rules(...)`
- `create_claim_review_rule(...)`
- `get_claim_review_rule(...)`
- `update_claim_review_rule(...)`
- `delete_claim_review_rule(...)`
- review analytics and metrics helpers
- claims monitoring helpers
- claims cluster helpers
- general claims CRUD/search helpers
- claims-service authorization logic

## Why This Slice

This is the cleanest next claims read subdomain because the two methods form the
read-only review access layer:
- `list_claim_review_history(...)` returns ordered review log rows for one claim
- `list_review_queue(...)` lists pending or reviewed claims with filterable
  reviewer, group, extractor, owner, and visibility-aware access constraints

They share the same caller-facing API surface in:
- [claims.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/api/v1/endpoints/claims.py)
- [claims_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_service.py)
- [test_claims_review_api.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_api.py)

This is materially narrower than the remaining monitoring and clustering blocks,
but it still has one meaningful risk center: `list_review_queue(...)` owns the
joined query, filter assembly, limit/offset normalization, scope-based
visibility filtering, and output ordering. That behavior needs direct helper
tests instead of relying only on the API happy path.

## Existing Risks To Preserve

### 1. History must preserve ascending log order

`list_claim_review_history(...)` currently orders by `created_at ASC`. That
ordering matters because the API exposes an audit trail, and callers expect
review transitions to read oldest-to-newest.

### 2. Queue must preserve tolerant paging normalization

`list_review_queue(...)` currently coerces `limit` and `offset` to integers,
falls back to `100/0` on bad input, caps `limit` to `1000`, and floors
`offset` at `0`. The runtime helper must preserve that exact normalization
instead of tightening behavior or surfacing new exceptions.

### 3. Queue must preserve joined filter behavior

`list_review_queue(...)` currently:
- joins `Claims c` to `Media m`
- optionally filters by review status, reviewer, review group, media id,
  owner user, and extractor
- excludes deleted claims unless `include_deleted=True`
- orders by `c.reviewed_at DESC, c.id DESC`

This is the main query-shape risk in the tranche.

### 4. Queue must preserve module-level `get_scope()` visibility semantics

`list_review_queue(...)` currently resolves request scope with `get_scope()`
and, for non-admin scopes, appends one visibility clause across personal, team,
and org visibility. If no visibility branch is available, it appends `(0 = 1)`.

The helper move should preserve that exact behavior and keep the patch seam on
the package helper module, following the existing pattern used by package-owned
runtime helpers like
[data_table_helper_ops.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_helper_ops.py).

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_review_read_ops.py`

That module should own only:
- `list_claim_review_history(...)`
- `list_review_queue(...)`

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

Important boundary choices:
- do not change `claims_service.py`
- do not change `claims.py`
- do not change review mutation, rules, analytics, monitoring, or clustering
  helpers
- import `get_scope` directly in the new helper module so helper-path tests can
  patch the module-level seam

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for both in-scope methods
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

### Focused helper-path tests

Add a new helper test file covering:
- `list_claim_review_history(...)` returning rows in `created_at ASC` order
- `list_review_queue(...)` preserving limit/offset normalization and joined
  filter behavior
- `list_review_queue(...)` respecting `include_deleted`
- `list_review_queue(...)` preserving the non-admin `get_scope()` visibility
  filter for personal/team/org visibility and the `(0 = 1)` fallback when the
  scope has no readable visibility branches

These tests should exercise canonical `MediaDatabase` methods, not the legacy
class.

### Broader caller-facing guards

Retain and reuse:
- [test_claims_review_api.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_api.py)

The focused helper tests are the primary rebinding proof. The review API suite
is the broader compatibility guard showing the queue and history reads still
feed the endpoint flow correctly.

## Success Criteria

- canonical ownership for the two in-scope methods moves off legacy globals
- both legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader review API caller-facing guards stay green
- normalized ownership count drops from `74` to `72`
