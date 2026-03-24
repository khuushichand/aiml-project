# Media DB V2 Backend-Prepare Helper Rebinding Design

## Summary

Rebind `_prepare_backend_statement`, `_prepare_backend_many_statement`, and
`_normalise_params` onto package-owned runtime helpers so the canonical
`MediaDatabase` no longer owns those thin backend-preparation methods through
legacy globals, while preserving `Media_DB_v2` as a live-module compatibility
shell.

## Scope

In scope:

- Add a package runtime helper module for:
  - `_prepare_backend_statement(...)`
  - `_prepare_backend_many_statement(...)`
  - `_normalise_params(...)`
- Rebind canonical `MediaDatabase` methods for those three helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused wrapper tests asserting exact forwarding of:
  - `backend_type`
  - `query`
  - params / params list
  - `apply_default_transform=True`
  - `ensure_returning=False`

Out of scope:

- Changing `prepare_backend_statement(...)`,
  `prepare_backend_many_statement(...)`, or `normalise_params(...)`
- Changing execution helpers or query execution flow
- Changing `_convert_sqlite_sql_to_postgres_statements` or
  `_transform_sqlite_statement_to_postgres`

## Why This Slice

This is the cleanest remaining non-domain helper cluster. The three methods are
already thin wrappers with direct unit coverage for the underlying query-utils
functions, and execution code already calls them through instance seams.

## Risks

Low. The main invariants are the forwarding contract and preserving current
defaults:

- `apply_default_transform=True`
- `ensure_returning=False`
- list params still normalize to tuples for the batch path
- scalar params still normalize the same way through `normalise_params(...)`

## Test Strategy

Add:

1. canonical ownership regressions for all three methods
2. legacy compat-shell delegation regressions for all three methods
3. focused wrapper tests asserting exact forwarding into query-utils helpers
4. reuse existing `test_backend_utils.py`, `test_postgres_returning_and_workflows.py`,
   and `unit/test_postgres_placeholder_prepare.py` as broader guards

## Success Criteria

- canonical helper methods are package-owned
- legacy `Media_DB_v2` helper methods remain live-module compat shells
- focused wrapper tests pass
- existing query-utils tests stay green
- normalized ownership count drops from `205` to `202`
