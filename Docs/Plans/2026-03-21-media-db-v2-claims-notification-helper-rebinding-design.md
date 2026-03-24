# Media DB V2 Claims Notification Helper Rebinding Design

## Summary

Rebind the legacy claims notification helper cluster onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals. Preserve the existing claims-service and
claims-notifications contracts for insert, point lookup, latest lookup, list,
batch fetch, and delivery marking while explicitly deferring claims review,
monitoring, cluster, and analytics-export helpers.

## Scope

In scope:
- `insert_claim_notification(...)`
- `get_claim_notification(...)`
- `get_latest_claim_notification(...)`
- `list_claim_notifications(...)`
- `get_claim_notifications_by_ids(...)`
- `mark_claim_notifications_delivered(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for read-after-write, latest-match filtering, list
  delivered filtering, empty-id handling, and delivery marking
- reuse of broader claims notification caller guards

Out of scope:
- claims review rule helpers
- claims monitoring helpers
- claims cluster helpers
- claims analytics export helpers
- claims service authorization/filtering logic
- notification digest orchestration

## Why This Slice

This is the cleanest next claims subdomain because the six methods form one
table-local notification storage layer:
- insert a notification row and return the stored record
- fetch one notification by id
- fetch the latest notification by `(user_id, kind, resource_type, resource_id)`
- list notifications with optional kind/target/resource/delivery filters
- batch fetch notifications by id set
- mark a set of notifications delivered

It already has meaningful caller-facing coverage in:
- [test_claims_review_notifications.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_notifications.py)
  for insert, get, batch fetch, and delivery marking
- [test_claims_watchlist_notifications.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py)
  for list filtering on undelivered watchlist notifications
- [claims_notifications.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_notifications.py)
  for latest-notification dedupe and delivery worker behavior
- [claims_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Claims_Extraction/claims_service.py)
  for list and delivery-marking caller paths

By contrast, review, monitoring, and cluster helpers each widen into different
claims domains and should remain separate slices.

## Existing Risks To Preserve

### 1. Insert must preserve read-after-write semantics

`insert_claim_notification(...)` currently inserts a row and immediately
returns `get_claim_notification(...)` on the inserted id. That matters because
callers treat the returned row as authoritative for `id` and timestamps.

### 2. Latest lookup must preserve dedupe filters

`get_latest_claim_notification(...)` currently filters by required
`(user_id, kind)` plus optional `resource_type` and `resource_id`, ordered by
`created_at DESC LIMIT 1`. That lookup is the dedupe seam used for watchlist
cluster notifications, so the optional resource filters must remain exact.

### 3. List must preserve delivered semantics and tolerant pagination

`list_claim_notifications(...)` currently:
- clamps invalid `limit/offset` to a safe default
- supports optional kind, target user, target review group, resource type, and
  resource id filters
- interprets `delivered=True` as `delivered_at IS NOT NULL`
- interprets `delivered=False` as `delivered_at IS NULL`

That behavior should stay unchanged because the claims service layers
authorization on top of these raw rows.

### 4. Batch fetch and mark-delivered must preserve empty-id handling

`get_claim_notifications_by_ids(...)` returns `[]` for an empty input list, and
`mark_claim_notifications_delivered(...)` returns `0` for an empty input list.
Those zero-work behaviors should remain unchanged.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_notification_ops.py`

That module should own only:
- `insert_claim_notification(...)`
- `get_claim_notification(...)`
- `get_latest_claim_notification(...)`
- `list_claim_notifications(...)`
- `get_claim_notifications_by_ids(...)`
- `mark_claim_notifications_delivered(...)`

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

Important boundary choices:
- do not change `claims_service.py`
- do not change `claims_notifications.py`
- do not pull in review, monitoring, cluster, or analytics-export helpers

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for all six in-scope methods
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

### Focused helper-path tests

Add a new helper test file covering:
- `insert_claim_notification(...)` returning the freshly readable row with the
  inserted target/resource fields
- `get_latest_claim_notification(...)` honoring optional resource filters and
  returning the newest matching row
- `list_claim_notifications(...)` respecting `delivered=True/False` and
  tolerant `limit/offset` normalization
- `get_claim_notifications_by_ids(...)` returning `[]` for `[]`
- `mark_claim_notifications_delivered(...)` returning `0` for `[]` and marking
  the selected rows as delivered

These tests should exercise canonical `MediaDatabase` methods, not the legacy
class.

### Broader caller-facing guards

Retain and reuse:
- [test_claims_review_notifications.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_notifications.py)
- [test_claims_watchlist_notifications.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py)

The focused helper tests are the primary rebinding proof. The claims review and
watchlist suites are the broader compatibility guards.

## Success Criteria

- canonical ownership for the six in-scope methods moves off legacy globals
- all six legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader claims notification caller-facing guards stay green
- normalized ownership count drops from `85` to `79`
