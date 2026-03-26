# Media DB V2 DB Version Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_get_db_version(...)` onto a package-owned schema helper so
the canonical `MediaDatabase` no longer owns that SQLite schema-version lookup
through `Media_DB_v2`, while preserving the legacy compat shell and keeping all
schema-version behavior unchanged.

**Architecture:** Add one package schema helper module for the SQLite
schema-version lookup, rebind the canonical class method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Use direct ownership/delegation regressions plus a
focused helper-path test file update to pin the version lookup behavior before
rebinding.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._get_db_version` is no longer legacy-owned
   - legacy `_LegacyMediaDatabase._get_db_version` delegates through a package
     helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_get_db_version'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing unit tests asserting:
   - `_get_db_version(...)` returns the integer version from a fetched row
   - `_get_db_version(...)` returns `0` when `fetchone()` is empty
   - `_get_db_version(...)` returns `0` when SQLite raises `no such table: schema_version`
   - `_get_db_version(...)` raises `DatabaseError` for other SQLite failures
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k '_get_db_version'
```

Expected: FAIL

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/sqlite_schema_version.py`

**Steps:**
1. Add a package-owned helper for `_get_db_version(...)`
2. Preserve:
   - integer version return
   - empty-result fallback to `0`
   - missing-table fallback to `0`
   - `DatabaseError` wrapping for other SQLite failures
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper function
2. Rebind canonical `MediaDatabase._get_db_version`
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert Legacy Helper To Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate `_get_db_version(...)` through `import_module(...)`
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
  -k '_get_db_version'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `162`

Actual close-out:
- ownership slice: `2 passed`
- helper slice: `4 passed`
- broader bundle with regressions + helper-path tests: `6 passed, 258 deselected, 6 warnings`
- Bandit on touched production files: no issues
- ownership recount: `163 -> 162`
- `git diff --check`: clean
