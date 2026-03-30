# Media DB V2 Data Table Generation Persist Coordinator Rebinding Design

## Summary

Rebind the live data-table generation persist coordinator onto a package-owned
runtime helper so the canonical `MediaDatabase` no longer owns
`persist_data_table_generation(...)` through legacy globals. Preserve the
`Media_DB_v2` live-module compat shell and explicitly defer
`replace_data_table_contents(...)`, which currently has no runtime callers in
this worktree.

## Scope

In scope:
- `persist_data_table_generation(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for:
  - owner validation and owner mismatch behavior
  - `sources is None` preserving existing sources
  - `sources == []` clearing existing sources
  - `generation_model is None` preserving the current model value
  - row/column packing and metadata update behavior
- reuse of broader CRUD/API/worker caller tests

Out of scope:
- `replace_data_table_contents(...)`
- `get_data_table_counts(...)`
- public metadata CRUD methods already rebound
- claims, email, bootstrap/schema, search, and media ingestion helpers

## Why This Slice

`persist_data_table_generation(...)` is the actual coordinator used by both the
content-update API path and the data-table generation worker:
- [data_tables.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/api/v1/endpoints/data_tables.py#L895)
- [jobs_worker.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/Data_Tables/jobs_worker.py#L1083)

By contrast, `replace_data_table_contents(...)` has no live callers in the
current worktree and would add test burden without protecting an active runtime
path. The correct next step is therefore a one-method coordinator tranche, not
a paired coordinator tranche.

## Existing Risks To Preserve

### 1. Owner validation and no-owner admin path

`persist_data_table_generation(...)` allows `owner_user_id=None`, but when an
owner is provided it must:
- reject blank-string owner values
- raise `InputError("data_table_not_found")` when the table is missing
- raise `InputError("data_table_owner_mismatch")` when the explicit owner does
  not match the real owner

The runtime helper must preserve this split because the worker path omits
`owner_user_id`, while the API update-content path passes it.

### 2. `sources is None` versus `sources == []`

The method currently treats source updates in two distinct ways:
- `sources is None`: do not soft-delete existing sources
- `sources == []`: soft-delete existing sources and reinsert none

That distinction is subtle and high-risk because the content-update API omits
`sources`, while generation paths may intentionally replace them.

### 3. `generation_model` preservation

`generation_model` is only written when an explicit value is supplied. A
runtime extraction must preserve the current behavior:
- `generation_model=None` leaves the stored value unchanged
- non-`None` value updates the stored value

### 4. Nested transaction behavior

Both runtime callers already wrap the method in `with db.transaction():`, and
the method itself also opens `with self.transaction() as conn:`. This tranche
must preserve that behavior and avoid trying to simplify transaction ownership
at the same time.

### 5. Shared column/row/source packing

The coordinator builds `column_rows`, `row_rows`, and optional `source_rows`,
validates rows through `_normalize_data_table_row_json(...)`, derives row hashes
when absent, soft-deletes current children, reinserts new children, and then
updates table metadata. The runtime helper must continue using the current
instance seams rather than inlining new DB behavior.

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical `persist_data_table_generation(...)` rebound to package runtime
  globals
- legacy `_LegacyMediaDatabase.persist_data_table_generation(...)` delegating
  through a live `import_module(...)` reference

### Focused helper-path tests

Add a new helper test file for the runtime module covering:
- blank `owner_user_id` rejection
- owner mismatch rejection
- `sources is None` preserving existing sources
- `sources == []` clearing sources
- `generation_model=None` preserving current value
- returned table row reflecting updated status/row count after persist

### Broader caller-facing guards

Retain and reuse:
- `tldw_Server_API/tests/DB_Management/test_data_tables_crud.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_api.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_worker.py`

Add one caller-facing regression if needed for the content-update API path to
prove that updating table content without sources does not wipe existing
sources.

## Implementation Shape

Add one package runtime module, likely:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_generation_ops.py`

It should expose:
- `persist_data_table_generation(...)`

The helper should continue calling through the current instance seams:
- `_resolve_data_table_write_client_id(...)`
- `_get_current_utc_timestamp_str()`
- `_generate_uuid()`
- `_normalize_data_table_row_json(...)`
- `_get_data_table_owner_client_id(...)`
- `transaction()`
- `_execute_with_connection(...)`
- `execute_many(...)`
- `get_data_table(...)`

Then:
- rebind the canonical method in `media_database_impl.py`
- convert the legacy method in `Media_DB_v2.py` into a live-module compat shell

`replace_data_table_contents(...)` stays untouched and deferred for a later
compat/dead-code review.

## Success Criteria

- canonical ownership for `persist_data_table_generation(...)` moves off legacy
  globals
- legacy method remains present as a live-module compat shell
- focused helper-path tests pass
- broader CRUD/API/worker guards stay green
- normalized ownership count drops from `117` to `116`
