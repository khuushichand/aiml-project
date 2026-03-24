# Media DB V2 Email Graph Persistence Helper Rebinding Design

## Summary

Rebind the remaining email graph persistence pair onto a package-owned runtime
module so the canonical `MediaDatabase` no longer owns those methods through
legacy globals. Preserve tenant-resolution precedence, message match strategy,
participant/label/attachment refresh behavior, and the SQLite email FTS sync
path while explicitly deferring the broader email coordinator and query
surfaces.

## Scope

In scope:
- `_resolve_email_tenant_id(...)`
- `upsert_email_message_graph(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for tenant-resolution precedence and direct graph
  upsert behavior
- reuse of broader email-native guards for source-message matching, label
  refresh, retention, and detail/search compatibility

Out of scope:
- `_normalize_email_address(...)`
- `_parse_email_internal_date(...)`
- `_collect_email_labels(...)`
- `search_email_messages(...)`
- `get_email_message_detail(...)`
- `apply_email_label_delta(...)`
- `reconcile_email_message_state(...)`
- `run_email_legacy_backfill_batch(...)`
- `run_email_legacy_backfill_worker(...)`
- the remaining tenant/backfill/bootstrap/claims surfaces

## Why This Slice

This is the cleanest remaining bounded email persistence slice because the two
methods form one coherent write seam:
- `_resolve_email_tenant_id(...)` is the shared scope resolver used by the
  already-extracted email runtime modules
- `upsert_email_message_graph(...)` is the remaining graph write owner that
  creates or updates normalized message, participant, label, attachment, and
  SQLite FTS rows

They also already have strong caller-facing coverage:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
  covers update-by-source-message, tenant-scoped retention behavior, label and
  participant refresh, and message detail/search contracts
- [test_media_db_email_message_mutation_ops.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_email_message_mutation_ops.py)
  exercises the mutation layer on top of `upsert_email_message_graph(...)`
- [test_media_db_email_query_ops.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_email_query_ops.py)
  exercises read paths built on top of the normalized graph
- [test_media_db_email_retention_ops.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_email_retention_ops.py)
  reuses graph-created rows for retention behavior

By contrast, `search_by_safe_metadata(...)`, `rollback_to_version(...)`, and
`upsert_email_message_graph(...)` plus tenant resolution mixed with the broader
backfill or query coordinators would be materially wider slices.

## Existing Risks To Preserve

### 1. Tenant resolution precedence must remain unchanged

`_resolve_email_tenant_id(...)` currently resolves:
- explicit `tenant_id`
- effective org scope
- user scope
- `self.client_id` fallback

That precedence is shared across the already-extracted email runtime modules.
The helper move must preserve that exact ordering.

### 2. Match strategy must remain stable

`upsert_email_message_graph(...)` currently matches existing rows in this order:
- `(tenant_id, source_id, source_message_id)`
- `(tenant_id, source_id, message_id)`
- `media_id`

That order prevents duplicate graph rows when providers change one identifier
but not the other. The helper should keep the current resolution order intact.

### 3. Re-upsert must fully replace graph children

The method currently deletes and rebuilds:
- `email_message_participants`
- `email_message_labels`
- `email_attachments`

before recreating children from the latest metadata payload. The helper should
preserve that full-refresh behavior rather than trying to diff or merge child
state.

### 4. SQLite email FTS refresh must remain in place

For SQLite backends, the method currently refreshes `email_fts` with
`INSERT OR REPLACE`. That path is part of the current search contract and must
remain unchanged in this tranche.

### 5. Static normalization helpers should stay deferred

`_normalize_email_address(...)`, `_parse_email_internal_date(...)`, and
`_collect_email_labels(...)` are still class-level helpers, but they are not in
the normalized ownership count. Moving them in this tranche would widen the
change without improving the counter, so they should remain instance-routed
from the new package helper.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_graph_persistence_ops.py`

That module should own only:
- `_resolve_email_tenant_id(...)`
- `upsert_email_message_graph(...)`

Important boundary choices:
- keep `_normalize_email_address(...)`, `_parse_email_internal_date(...)`, and
  `_collect_email_labels(...)` on the DB instance
- keep query/mutation/retention/backfill methods untouched
- keep the helper calling DB-instance seams such as
  `_fetchone_with_connection(...)`, `_execute_with_connection(...)`, and
  `transaction()`

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for:
  - `_resolve_email_tenant_id(...)`
  - `upsert_email_message_graph(...)`
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

### Focused helper-path tests

Add a helper test file covering:
- `_resolve_email_tenant_id(...)` precedence for:
  - explicit tenant
  - effective org scope
  - user scope
  - client-id fallback
- `upsert_email_message_graph(...)` creating the normalized graph via the new
  helper path
- `upsert_email_message_graph(...)` preserving source-message matching and
  refreshing child rows plus SQLite `email_fts`

### Broader caller-facing guards

Retain and reuse:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
- [test_media_db_email_message_mutation_ops.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_email_message_mutation_ops.py)
- [test_media_db_email_query_ops.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_email_query_ops.py)
- [test_media_db_email_retention_ops.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_email_retention_ops.py)

The broader email-native files are the compatibility guard for the real graph
surface. The new helper tests are the primary proof of canonical rebinding.

## Success Criteria

- canonical ownership for the two in-scope methods moves off legacy globals
- both legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader email graph callers stay green
- normalized ownership count drops from `92` to `90`
