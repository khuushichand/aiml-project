# Media DB V2 Claims Review Rule Helper Rebinding Design

## Summary

Rebind the legacy claims review-rule CRUD layer onto a package-owned runtime
module so the canonical `MediaDatabase` no longer owns those methods through
legacy globals. Preserve the existing claims-service and review-assignment
contracts for list, create, get, update, and delete while explicitly deferring
review queue, review history, analytics, monitoring, clustering, and broader
claims CRUD/search helpers.

## Scope

In scope:
- `list_claim_review_rules(...)`
- `create_claim_review_rule(...)`
- `get_claim_review_rule(...)`
- `update_claim_review_rule(...)`
- `delete_claim_review_rule(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for create/get/update/delete/list behavior
- reuse of broader review-assignment caller guards

Out of scope:
- `list_review_queue(...)`
- `list_claim_review_history(...)`
- review analytics and metrics helpers
- claims monitoring helpers
- claims cluster helpers
- general claims CRUD/search helpers
- claims-service authorization logic

## Why This Slice

This is the cleanest next claims subdomain because the five methods form one
table-local CRUD layer over `claims_review_rules`:
- list rules for one user with optional `active_only`
- create a rule and return the stored row
- fetch a single rule by id
- update a rule and return the stored row
- delete a rule by id

It is materially narrower than the remaining monitoring and clustering blocks,
and it already has meaningful caller-facing coverage in:
- [test_claim_review_rule_assignment.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claim_review_rule_assignment.py)
  for create-plus-assignment behavior through the rule evaluator
- [claims_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_service.py)
  for list/create/update/delete service-layer authorization and normalization
- [claims.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/api/v1/endpoints/claims.py)
  for the stable review-rules endpoint contract

There are no existing dedicated CRUD helper tests for this table, so this
tranche should add them directly instead of relying only on assignment behavior.

## Existing Risks To Preserve

### 1. Create must preserve read-after-write semantics

`create_claim_review_rule(...)` currently inserts one row and immediately
returns `get_claim_review_rule(...)` for the inserted id. That matters because
callers expect the returned rule to include the actual stored `id`,
timestamps, and backend-normalized fields.

### 2. List must preserve `active_only` filtering and ordering

`list_claim_review_rules(...)` currently:
- always filters by `user_id`
- optionally adds `AND active = 1`
- orders by `priority DESC, id DESC`

That ordering matters because review assignment depends on priority ordering,
and the `active_only` switch is the cleanest caller-facing filter on the raw
rule rows.

### 3. Update must preserve the no-op return path

`update_claim_review_rule(...)` currently returns
`get_claim_review_rule(rule_id)` unchanged when no update fields are supplied.
That no-op behavior should stay intact because the service layer passes partial
patch payloads and expects a rule-shaped response either way.

### 4. Delete should remain a fire-and-forget DB helper

`delete_claim_review_rule(...)` currently returns `None` and relies on the
service layer to fetch/authorize the rule before deletion. This slice should
keep that boundary exactly as-is rather than mixing ownership rebinding with
service semantics.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_review_rule_ops.py`

That module should own only:
- `list_claim_review_rules(...)`
- `create_claim_review_rule(...)`
- `get_claim_review_rule(...)`
- `update_claim_review_rule(...)`
- `delete_claim_review_rule(...)`

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

Important boundary choices:
- do not change `claims_service.py`
- do not change `claims.py`
- do not pull in review queue, analytics, monitoring, clustering, or broader
  claims CRUD/search helpers

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for all five in-scope methods
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

### Focused helper-path tests

Add a new helper test file covering:
- `create_claim_review_rule(...)` returning the stored row with the inserted
  `priority`, `predicate_json`, reviewer target, and timestamps
- `list_claim_review_rules(...)` honoring `active_only=True` and preserving
  `priority DESC, id DESC` ordering
- `get_claim_review_rule(...)` returning `{}` for a missing row id
- `update_claim_review_rule(...)` preserving the no-op return path and applying
  a real update when fields are supplied
- `delete_claim_review_rule(...)` removing the row

These tests should exercise canonical `MediaDatabase` methods, not the legacy
class.

### Broader caller-facing guards

Retain and reuse:
- [test_claim_review_rule_assignment.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claim_review_rule_assignment.py)

The focused helper tests are the primary rebinding proof. The assignment suite
is the broader compatibility guard showing the rules still feed the review
assignment flow correctly.

## Success Criteria

- canonical ownership for the five in-scope methods moves off legacy globals
- all five legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader review-assignment caller-facing guards stay green
- normalized ownership count drops from `79` to `74`
