# Media DB V2 SQLite-To-Postgres Conversion Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_convert_sqlite_sql_to_postgres_statements` and
`_transform_sqlite_statement_to_postgres` onto a package-owned schema helper so
the canonical `MediaDatabase` no longer owns those conversion methods through
the legacy module, while preserving the `Media_DB_v2` compat shell and keeping
the MediaFiles migration behavior unchanged.

**Architecture:** Add one package schema helper module for the conversion pair,
rebind the canonical class methods in `media_database_impl.py`, and convert the
legacy `Media_DB_v2` methods to live-module compat shells. Verify direct helper
behavior with focused tests and reuse the existing MediaFiles migration tests as
the broader guard.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._convert_sqlite_sql_to_postgres_statements` is no
     longer legacy-owned
   - canonical `MediaDatabase._transform_sqlite_statement_to_postgres` is no
     longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'convert_sqlite_sql_to_postgres_statements or transform_sqlite_statement_to_postgres'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing unit tests asserting:
   - SQLite-only lines are filtered and statements are collected in order
   - conversion delegates each buffered statement through the transform helper
   - one direct transform example keeps the existing rewrite contract
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'convert_sqlite_sql_to_postgres_statements or transform_sqlite_statement_to_postgres'
```

Expected: FAIL

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/postgres_sqlite_conversion.py`

**Steps:**
1. Create package-owned helper functions for the conversion pair
2. Preserve the current filtering and token-level rewrite behavior
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the two canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the two legacy methods through `import_module(...)`
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
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'convert_sqlite_sql_to_postgres_statements or transform_sqlite_statement_to_postgres'
```

2. Re-run the existing MediaFiles migration tests:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v11'
```

3. Run Bandit on touched production files
4. Recount ownership
5. Run `git diff --check`

Expected ownership count: `200`
