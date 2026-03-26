# Media DB V2 Query Utility Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_keyword_order_expression`,
`_append_case_insensitive_like`, and
`_convert_sqlite_placeholders_to_postgres` onto package-owned runtime helpers
so the canonical `MediaDatabase` no longer owns that small query utility
cluster through the legacy module, while preserving the `Media_DB_v2` compat
shell and keeping backend-aware SQL behavior unchanged.

**Architecture:** Add one package runtime helper module for the three query
utility methods, rebind the canonical class methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods into
live-module compat shells. Use direct ownership/delegation regressions and
focused helper-path tests in `test_backend_utils.py`, then verify against the
existing Postgres search tests that bind these helpers from the class.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._keyword_order_expression` is no longer
     legacy-owned
   - canonical `MediaDatabase._append_case_insensitive_like` is no longer
     legacy-owned
   - canonical `MediaDatabase._convert_sqlite_placeholders_to_postgres` is no
     longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_keyword_order_expression or _append_case_insensitive_like or _convert_sqlite_placeholders_to_postgres'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_backend_utils.py`

**Steps:**
1. Add failing unit tests asserting:
   - `_keyword_order_expression(...)` returns SQLite and Postgres expressions
   - `_append_case_insensitive_like(...)` appends the correct clause and
     parameter for SQLite and Postgres
   - `_convert_sqlite_placeholders_to_postgres(...)` delegates to the shared
     query utility behavior
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_backend_utils.py \
  -k 'keyword_order_expression or append_case_insensitive_like or convert_sqlite_placeholders_to_postgres'
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/query_utility_ops.py`

**Steps:**
1. Add package-owned helpers for the three methods
2. Preserve SQLite/Postgres ordering behavior, LIKE clause behavior, and
   placeholder conversion behavior
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the three canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the three legacy methods through `import_module(...)`
2. Keep the legacy methods present as compat shells
3. Re-run the Task 1 regression slice

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_backend_utils.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py::test_search_media_db_postgres_uses_tsquery \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py::test_search_media_db_postgres_uses_weighted_ts_rank_when_boost_fields_set
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `172`

Actual close-out:
- ownership slice: `4 passed`
- helper slice: `7 passed`
- broader Postgres search guards: `2 passed`
- Bandit on touched production files: no issues
- ownership recount: `175 -> 172`
- `git diff --check`: clean
