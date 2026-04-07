# Media DB V2 Postgres Schema-Version Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_update_schema_version_postgres` onto a package-owned helper
so the canonical `MediaDatabase` no longer owns that PostgreSQL helper through
the legacy module, while preserving the `Media_DB_v2` compat shell and keeping
the exact SQL and parameter contract unchanged.

**Architecture:** Add one package helper module for the PostgreSQL schema
version update helper, rebind the canonical class method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method to a
live-module compat shell.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._update_schema_version_postgres` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase._update_schema_version_postgres(conn, version)`
     delegates through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'update_schema_version_postgres'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Test

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add a failing unit test asserting:
   - exact SQL string
   - exact params tuple `(version,)`
   - connection forwarding
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'update_schema_version_postgres'
```

Expected: FAIL

### Task 3: Add Package Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/postgres_schema_version.py`

**Steps:**
1. Create `update_schema_version_postgres(db, conn, version)`
2. Preserve exact SQL and params
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper
2. Rebind `MediaDatabase._update_schema_version_postgres`
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert Legacy Helper To Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate through `import_module(...)` to the package helper
2. Keep the legacy method present as a compat shell
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
  -k 'update_schema_version_postgres'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `206`
