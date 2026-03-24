# Media DB V2 Data Table Metadata CRUD Rebinding Design

## Summary

Rebind the bounded data-table metadata CRUD layer onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns
`create_data_table`, `get_data_table`, `get_data_table_by_uuid`,
`list_data_tables`, `count_data_tables`, `update_data_table`, or
`soft_delete_data_table` through legacy globals. Preserve the
`Media_DB_v2` live-module compat shell and explicitly defer the
child-summary helper `get_data_table_counts(...)` to a later tranche.

## Scope

In scope:
- `create_data_table`
- `get_data_table`
- `get_data_table_by_uuid`
- `list_data_tables`
- `count_data_tables`
- `update_data_table`
- `soft_delete_data_table`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for:
  - invalid `column_hints` handling on create/update
  - `get_data_table_by_uuid("") -> None`
  - list/count filter parity
  - `soft_delete_data_table(...)` cascade gating
- reuse of broader CRUD/API/worker/export caller tests

Out of scope:
- `get_data_table_counts(...)`
- `insert_data_table_columns/rows/sources`
- `list_data_table_columns/rows/sources`
- `replace_data_table_contents(...)`
- `persist_data_table_generation(...)`
- claims, email, bootstrap/schema, search, and media ingestion helpers

## Why This Slice

The newly extracted internal helper layer now supports a natural next step:
move the public metadata CRUD methods that sit directly above it. This is a
coherent ownership-reduction slice because these methods depend primarily on
the helper seams already moved off `Media_DB_v2`, and they already have strong
caller-facing coverage in:
- `tldw_Server_API/tests/DB_Management/test_data_tables_crud.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_api.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_worker.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_export.py`

`get_data_table_counts(...)` is intentionally excluded because it is not pure
metadata CRUD; it aggregates child-column/source counts and is used as a
summary helper in several API paths. Moving it together with metadata CRUD
would widen the tranche and blur the boundary.

## Existing Risks To Preserve

### 1. `column_hints` validation and serialization

`create_data_table(...)` and `update_data_table(...)` each validate
string-based JSON inputs and serialize structured inputs. The runtime helper
must preserve:
- `InputError("Invalid column_hints JSON: ...")` behavior
- pass-through of valid JSON strings
- `json.dumps(...)` serialization for dict/list payloads

### 2. Owner filtering and admin behavior

These methods depend on `_resolve_data_tables_owner(...)`, which now lives in
the package runtime. The CRUD layer must preserve:
- explicit owner scoping
- non-admin scope fallback behavior
- admin/no-scope unrestricted behavior
- no accidental owner reassignment on admin updates

### 3. Filter parity between list and count

`list_data_tables(...)` and `count_data_tables(...)` currently duplicate
filter-building logic for:
- `deleted`
- `client_id`
- `status`
- `workspace_tag`
- `search`

The runtime extraction must preserve parity so the API’s `total` field stays
consistent with the returned row set.

### 4. `soft_delete_data_table(...)` cascade gating

`soft_delete_data_table(...)` should only cascade into
`_soft_delete_data_table_children(...)` when the parent row was actually
updated. The runtime helper must preserve:
- transaction ownership
- rowcount-based success semantics
- owner-filter behavior
- no child-delete call when the parent update matched zero rows

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical methods rebound to package runtime globals
- legacy `_LegacyMediaDatabase` methods delegating through a live
  `import_module(...)` reference

### Focused helper-path tests

Add a new helper test file for the metadata CRUD runtime module covering:
- invalid `column_hints` on create
- invalid `column_hints` on update
- `get_data_table_by_uuid("") -> None`
- list/count filter parity across owner/status/search/workspace/include_deleted
- `soft_delete_data_table(...)` only invoking the child-delete seam when the
  parent update rowcount is nonzero

### Broader caller-facing guards

Retain the existing caller coverage in:
- `test_data_tables_crud.py`
- `test_data_tables_api.py`
- `test_data_tables_worker.py`
- `test_data_tables_export.py`

## Implementation Shape

Add one package runtime module, likely:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_metadata_ops.py`

It should expose seven methods mirroring the legacy public API and continue
calling through the existing instance seams:
- `_resolve_data_tables_owner(...)`
- `_get_current_utc_timestamp_str()`
- `_generate_uuid()`
- `transaction()`
- `_execute_with_connection(...)`
- `_fetchone_with_connection(...)`
- `execute_query(...)`
- `_soft_delete_data_table_children(...)`

Then:
- rebind the canonical class methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

## Success Criteria

- canonical ownership for the seven methods moves off legacy globals
- legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader CRUD/API/worker/export guards stay green
- normalized ownership count drops from `134` to `127`
