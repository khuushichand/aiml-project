# Media DB V2 Email Retention Helper Rebinding Design

## Summary

Rebind the email retention and tenant hard-delete layer onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals. Preserve the current retention, cleanup, and
tenant-scoped hard-delete behavior while explicitly deferring tenant
resolution and legacy-backfill coordinators.

## Scope

In scope:
- `_cleanup_email_orphans_for_tenant(...)`
- `enforce_email_retention_policy(...)`
- `hard_delete_email_tenant_data(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for orphan cleanup and retention gating
- reuse of broader email-native guards for soft-delete, hard-delete, and
  tenant scoping

Out of scope:
- `_resolve_email_tenant_id(...)`
- `_parse_email_retention_datetime(...)` as a class-owned helper
- `run_email_legacy_backfill_batch(...)`
- `run_email_legacy_backfill_worker(...)`
- `upsert_email_message_graph(...)`
- `search_email_messages(...)`
- `get_email_message_detail(...)`

## Why This Slice

This is the cleanest remaining bounded email coordinator cluster because the
three in-scope methods form one retention/cleanup layer:
- orphan label/participant/source cleanup
- tenant-scoped retention enforcement
- tenant-scoped hard-delete teardown

They also already have strong stage-1 coverage:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
  covers soft-delete retention, hard-delete retention, negative-day rejection,
  and tenant-scoped hard delete

By contrast, the legacy-backfill worker is coupled to ingestion and message
upsert behavior, while `_resolve_email_tenant_id(...)` is shared across the
whole remaining email surface. Mixing either into this tranche would widen a
coherent retention move into a broader email-domain refactor.

## Existing Risks To Preserve

### 1. Retention must keep routing through existing delete seams

`enforce_email_retention_policy(...)` currently:
- calls `soft_delete_media(..., cascade=True)` for soft-delete mode
- calls `permanently_delete_item(...)` for hard-delete mode
- keeps tenant resolution through `_resolve_email_tenant_id(...)`

That routing must stay intact. The package helper should not inline media
deletion semantics.

### 2. Orphan cleanup must stay tenant-scoped

`_cleanup_email_orphans_for_tenant(...)` deletes:
- `email_labels` with no surviving `email_message_labels`
- `email_participants` with no surviving `email_message_participants`
- optionally empty `email_sources`

It must not cross tenant boundaries or delete still-referenced rows.

### 3. Retention gating semantics must remain unchanged

`enforce_email_retention_policy(...)` currently:
- rejects negative `retention_days`
- supports optional `limit`
- skips records with missing dates unless `include_missing_internal_date=True`
- skips already-deleted media in soft-delete mode

Those behaviors need direct helper-path coverage, not only end-state coverage.

### 4. Hard delete must preserve partial-failure behavior

`hard_delete_email_tenant_data(...)` only clears sync/backfill state and source
rows when all candidate media delete successfully. That guard is part of the
current contract and should remain unchanged.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_retention_ops.py`

That module should own the three in-scope `MediaDatabase` methods only.

Important boundary choice:
- keep `_parse_email_retention_datetime(...)` as a module-local helper inside
  `email_retention_ops.py`
- do not rebind it onto `MediaDatabase`

That keeps the runtime boundary coherent and avoids a staticmethod accounting
mismatch in the ownership counter.

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for:
  - `_cleanup_email_orphans_for_tenant(...)`
  - `enforce_email_retention_policy(...)`
  - `hard_delete_email_tenant_data(...)`
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

Keep `_resolve_email_tenant_id(...)` and `_parse_email_retention_datetime(...)`
out of the regression surface.

### Focused helper-path tests

Add a new helper test file covering:
- `_parse_email_retention_datetime(...)` parsing ISO and RFC-2822 values
- `_cleanup_email_orphans_for_tenant(...)` deleting only orphaned tenant rows
  and optional empty sources
- `enforce_email_retention_policy(...)` respecting `limit` and
  `include_missing_internal_date`
- `hard_delete_email_tenant_data(...)` preserving tenant scope and cleanup
  counts through the helper path

### Broader caller-facing guards

Retain and reuse:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)

That suite is the compatibility guard for the public retention/hard-delete
surface; the new helper tests are the primary proof of canonical rebinding.

## Success Criteria

- canonical ownership for the three in-scope methods moves off legacy globals
- all three legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader email-native retention guards stay green
- normalized ownership count drops from `97` to `94`
