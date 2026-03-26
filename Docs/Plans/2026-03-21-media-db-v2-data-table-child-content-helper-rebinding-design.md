# Media DB V2 Data Table Child-Content Helper Rebinding Design

**Date:** 2026-03-21  
**Branch:** `codex/media-db-v2-stage1-caller-first`

## Objective

Reduce the remaining canonical legacy-owned Media DB surface by extracting the
bounded data-table child-content layer into a package-owned runtime module.

## Scope

This tranche is limited to:

- `get_data_table_counts`
- `insert_data_table_columns`
- `list_data_table_columns`
- `soft_delete_data_table_columns`
- `insert_data_table_rows`
- `list_data_table_rows`
- `soft_delete_data_table_rows`
- `insert_data_table_sources`
- `list_data_table_sources`
- `soft_delete_data_table_sources`

## Explicitly Deferred

These methods stay legacy-owned for now:

- `replace_data_table_contents`
- `persist_data_table_generation`

They coordinate multi-table replacement, owner validation, and metadata updates
in one transaction, which is a wider seam than the basic child-content CRUD and
summary layer.

## Why This Slice

The remaining ownership surface at `127` is no longer dominated by tiny helpers.
The safest bounded cluster is the data-table child-content layer immediately
under the metadata CRUD methods that were just rebound:

- the methods are cohesive
- they already rely on recently extracted helper seams
- they are caller-facing through existing data-table CRUD/API/worker/export tests
- rebinding them should materially reduce legacy ownership without crossing into
  claims, email, or bootstrap coordination

## Risks

### Owner-gating behavior

`insert_data_table_columns`, `insert_data_table_rows`, and
`insert_data_table_sources` all short-circuit to `0` when an explicit
`owner_user_id` does not own the table. That guard must remain unchanged.

### Row validation behavior

`insert_data_table_rows` depends on `list_data_table_columns(...)` and
`_normalize_data_table_row_json(...)` when `validate_keys=True`. The runtime
module must preserve the `data_table_columns_required` failure path when rows are
inserted before columns exist.

### Summary parity

`get_data_table_counts(...)` summarizes child counts across columns and sources.
It belongs with the child-content layer, but it needs focused tests so this
tranche does not silently regress API summary behavior.

### Limit/order behavior

`list_data_table_rows(...)` clamps `limit/offset` and orders by
`row_index ASC, id ASC`. That exact behavior needs direct helper-path coverage.

## Test Strategy

Add direct ownership/delegation regressions for the 10 methods and add focused
helper-path tests covering:

- `get_data_table_counts(...)` aggregation behavior
- insert owner-gating for columns/rows/sources
- `insert_data_table_rows(...)` failure when key validation is enabled and the
  table has no columns
- `list_data_table_rows(...)` limit/offset normalization and order SQL
- rowcount returns from the three soft-delete methods

Reuse caller-facing coverage from:

- `tldw_Server_API/tests/DB_Management/test_data_tables_crud.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_api.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_worker.py`
- `tldw_Server_API/tests/DataTables/test_data_tables_export.py`

## Architecture

Add one runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/data_table_child_ops.py`

Rebind the canonical `MediaDatabase` methods in:

- `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

Convert the legacy methods in:

- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

into `import_module(...)` compat shells that delegate to the package runtime.

## Success Criteria

- Canonical `MediaDatabase` methods for the 10-method child-content layer are no
  longer legacy-owned.
- `_LegacyMediaDatabase` retains live-module compat shells for the same methods.
- Focused helper-path tests pass.
- Existing data-table CRUD/API/worker/export tests stay green.
- Normalized ownership count drops from `127` to `117`.
