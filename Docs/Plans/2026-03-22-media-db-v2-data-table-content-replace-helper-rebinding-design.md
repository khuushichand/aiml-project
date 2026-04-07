# Media DB V2 Data Table Content Replace Helper Rebinding Design

## Summary

After the keyword-access tranche, the normalized legacy ownership count is
`20`. The cleanest remaining non-bootstrap singleton is
`replace_data_table_contents(...)`.

This method currently has no live runtime callers in the worktree, but it is
fully self-contained and only depends on data-table helper seams that have
already been moved. That makes it a good bounded ownership-reduction slice
before the broader bootstrap/search/sync/rollback cluster.

## Current Method Shape

`replace_data_table_contents(...)` currently owns:

- required-owner validation
- required-columns / required-rows validation
- write-client resolution through `_resolve_data_table_write_client_id(...)`
- per-column row shaping with generated `column_id` fallback
- per-row JSON normalization through `_normalize_data_table_row_json(...)`
- generated `row_id` and `row_hash` fallback behavior
- in-transaction owner existence / owner mismatch checks via
  `_get_data_table_owner_client_id(...)`
- soft-delete of existing active columns and rows
- reinsertion of replacement columns and rows through `execute_many(...)`
- `(column_count, row_count)` return semantics

Notably, it does **not** update table metadata and it does **not** touch
`data_table_sources`.

## Why This Slice Is Safe

This method is isolated:

- no live runtime callers in the current worktree
- all child insert / row-normalization / owner helper seams are already
  package-owned
- no bootstrap or backend-specific branching in the method body

That means we can reduce ownership without widening into:

- `initialize_db(...)`
- `search_by_safe_metadata(...)`
- `apply_synced_document_content_update(...)`
- `rollback_to_version(...)`
- bootstrap / postgres schema coordinator helpers

## Risks To Pin

### 1. Owner validation must stay strict

Unlike `persist_data_table_generation(...)`, this method requires an explicit
owner. Rebinding must preserve:

- blank owner rejection via `InputError("owner_user_id is required")`
- `data_table_not_found` when the table owner lookup returns no row
- `data_table_owner_mismatch` when the actual owner differs

### 2. Replacement must only touch columns and rows

The contract is narrower than generation persistence. It should:

- soft-delete existing `data_table_columns`
- soft-delete existing `data_table_rows`
- leave `data_table_sources` untouched
- avoid changing top-level table metadata

The source-preservation behavior is easy to lose if the method is accidentally
collapsed into the generation helper.

### 3. Row/column packing behavior must survive

The helper currently derives replacement rows with several fallback behaviors:

- generated `column_id` and `row_id` when identifiers are absent
- generated `row_hash` when absent
- `position` and `row_index` defaulting from enumeration order
- `_normalize_data_table_row_json(...)` with `validate_keys=True`

These are the most important local invariants to pin directly in helper tests.

### 4. Transaction-bound child reinserts must stay on the current seams

The method currently opens one transaction, soft-deletes through
`_execute_with_connection(...)`, then reinserts through `execute_many(...)` with
`commit=False` and `connection=conn`. That structure should stay intact so the
method does not silently change transaction ownership or durability behavior.

## Recommended Tranche

Move only:

- `replace_data_table_contents(...)`

Defer:

- `initialize_db(...)`
- `search_by_safe_metadata(...)`
- `apply_synced_document_content_update(...)`
- `rollback_to_version(...)`
- bootstrap / postgres schema coordinators

## Design

Add one package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_replace_ops.py`

It should expose:

- `replace_data_table_contents(...)`

Then:

- rebind the canonical `MediaDatabase.replace_data_table_contents` method in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert the legacy method in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into a live-module compat shell

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical `MediaDatabase.replace_data_table_contents(...)` no longer using
  legacy globals
- legacy `Media_DB_v2.replace_data_table_contents(...)` delegating through
  `data_table_replace_ops.py`

### Focused helper coverage

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_data_table_replace_ops.py`

Pin:

- canonical helper rebinding
- blank owner rejection
- missing columns rejection
- `rows is None` rejection
- owner mismatch rejection
- row/column packing with generated ids / hashes
- transaction-bound soft-delete plus reinsertion behavior

### Real DB guard

Add one real SQLite CRUD test in
[test_data_tables_crud.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_data_tables_crud.py)
proving:

- replaced columns and rows become the new active children
- previous columns and rows remain present only as soft-deleted rows
- sources remain intact after replacement

## Success Criteria

- canonical ownership for `replace_data_table_contents(...)` moves off legacy
  globals
- legacy method remains a live-module compat shell
- focused helper tests and the real DB replacement guard pass
- normalized ownership count drops `20 -> 19`
