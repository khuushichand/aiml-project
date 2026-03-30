# Media DB V2 Query Utility Helper Rebinding Design

## Summary

Rebind the small query utility helper cluster onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns
`_keyword_order_expression`, `_append_case_insensitive_like`, or
`_convert_sqlite_placeholders_to_postgres` through legacy globals, while
preserving `Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `_keyword_order_expression(...)`
  - `_append_case_insensitive_like(...)`
  - `_convert_sqlite_placeholders_to_postgres(...)`
- Rebind canonical `MediaDatabase` methods for those three helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting:
  - SQLite keyword ordering still uses `COLLATE NOCASE`
  - Postgres keyword ordering still emits `LOWER(column), column`
  - case-insensitive LIKE appends the right predicate and parameter for each
    backend
  - placeholder conversion still delegates to the shared query utility and
    preserves literal/question-mark behavior

Out of scope:

- Rebinding `_build_tts_history_filters(...)`
- Rebinding `search_media_db(...)`
- Rebinding TTS-history CRUD or filter behavior
- Changing repository search logic
- Changing broader data-table, claims, email, or bootstrap helpers

## Why This Slice

This is the smallest remaining helper-level cluster that already has direct
callers and tests, but does not drag in a broader domain surface. The methods
are adjacent, low-risk, and mostly pure helpers, so they reduce legacy
ownership cleanly while leaving the still-legacy callers unchanged.

## Risks

Low. The key invariants are straightforward:

- SQLite ordering must remain `column COLLATE NOCASE`
- Postgres ordering must remain `LOWER(column), column`
- backend-aware LIKE predicates must still append the same SQL fragments and
  parameter order
- placeholder conversion must keep using the shared query utility behavior
  already covered in `test_backend_utils.py`
- instance monkeypatchability must remain intact because callers bind these
  helpers from the class at runtime in the Postgres search tests

## Test Strategy

Add:

1. canonical ownership regressions for all three methods
2. legacy compat-shell delegation regressions for all three methods
3. focused helper-path tests in `test_backend_utils.py` for:
   - `_keyword_order_expression(...)`
   - `_append_case_insensitive_like(...)`
   - `_convert_sqlite_placeholders_to_postgres(...)`
4. reuse existing broader guards in:
   - `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`
   - `tldw_Server_API/tests/DB_Management/test_backend_utils.py`

## Success Criteria

- canonical helper methods are package-owned
- legacy `Media_DB_v2` helper methods remain live-module compat shells
- focused helper-path tests pass
- existing search/backend utility tests stay green
- normalized ownership count drops from `175` to `172`
