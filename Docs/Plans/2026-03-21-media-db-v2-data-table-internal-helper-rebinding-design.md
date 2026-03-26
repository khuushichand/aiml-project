# Media DB V2 Data Table Internal Helper Rebinding Design

## Summary

Rebind the bounded internal data-table helper cluster onto package-owned
runtime helpers so the canonical `MediaDatabase` no longer owns
`_resolve_data_tables_owner`, `_resolve_data_table_write_client_id`,
`_get_data_table_owner_client_id`, `_soft_delete_data_table_children`, or
`_normalize_data_table_row_json` through legacy globals, while preserving
`Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `_resolve_data_tables_owner(...)`
  - `_resolve_data_table_write_client_id(...)`
  - `_get_data_table_owner_client_id(...)`
  - `_soft_delete_data_table_children(...)`
  - `_normalize_data_table_row_json(...)`
- Rebind canonical `MediaDatabase` methods for those five helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions for the five methods
- Add focused helper-path tests asserting:
  - explicit owner, request-scope fallback, and admin/no-scope behavior for
    `_resolve_data_tables_owner(...)`
  - explicit owner override, table lookup fallback, and missing-owner error
    behavior for `_resolve_data_table_write_client_id(...)`
  - `None`/string return behavior for `_get_data_table_owner_client_id(...)`
  - validation and normalization behavior for `_normalize_data_table_row_json(...)`
  - table child soft-delete fanout and owner-filter propagation for
    `_soft_delete_data_table_children(...)`
- Reuse the existing data-table CRUD, API, worker, and export tests as
  broader guards

Out of scope:

- Rebinding public data-table CRUD/read/write methods like
  `create_data_table(...)`, `list_data_tables(...)`,
  `replace_data_table_contents(...)`, or `persist_data_table_generation(...)`
- Rebinding claims, email, search, or bootstrap/schema surfaces
- Changing data-table owner semantics, row JSON validation rules, or child
  soft-delete behavior

## Why This Slice

This is the smallest coherent remaining helper cluster inside the data-table
domain. It is internal-only, already feeds a broad caller surface, and can
deliver a real ownership reduction without immediately widening into the
larger public CRUD/write methods.

The remaining large clusters are materially riskier:

- claims: too large and operationally broad
- email: mixes sync state, backfill, retention, and search parsing
- public data tables: coherent but wider, because the CRUD and generation
  paths depend on these helpers

## Risks

Medium. The main invariants are:

- canonical helper methods must stop resolving through `Media_DB_v2`
- legacy `Media_DB_v2` methods must remain present and delegate through a live
  module reference
- `_resolve_data_tables_owner(...)` must preserve explicit-owner precedence and
  non-admin scope fallback behavior
- `_resolve_data_table_write_client_id(...)` must preserve the explicit-owner
  override, table-owner fallback lookup, and `InputError` paths
- `_get_data_table_owner_client_id(...)` must keep the current fetch contract
- `_normalize_data_table_row_json(...)` must preserve JSON parsing and unknown
  column validation semantics
- `_soft_delete_data_table_children(...)` must continue to fan out the
  soft-delete update to all three child tables and keep owner filtering intact

## Test Strategy

Add:

1. canonical ownership regressions for all five helper methods
2. legacy compat-shell delegation regressions for all five methods
3. focused helper-path tests in
   `tldw_Server_API/tests/DB_Management/test_media_db_data_table_helper_ops.py`
   for:
   - owner resolution behavior
   - write-client resolution behavior
   - owner-client lookup behavior
   - row JSON normalization/validation
   - child soft-delete fanout behavior
4. reuse the broader guards in:
   - `tldw_Server_API/tests/DB_Management/test_data_tables_crud.py`
   - `tldw_Server_API/tests/DataTables/test_data_tables_api.py`
   - `tldw_Server_API/tests/DataTables/test_data_tables_worker.py`
   - `tldw_Server_API/tests/DataTables/test_data_tables_export.py`

## Success Criteria

- canonical data-table helper methods are package-owned
- legacy `Media_DB_v2` helper methods remain live-module compat shells
- focused helper-path tests pass
- broader data-table caller-facing tests stay green
- normalized ownership count drops from `139` to `134`
