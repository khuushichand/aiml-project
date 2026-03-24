# Media DB V2 Postgres Claims/Collections Ensure Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the remaining Postgres claims/collections ensure helpers onto a
package-owned schema module while preserving ordering, warning behavior, and
late-schema DDL coverage.

**Architecture:** Add a `postgres_claims_collection_structures.py` schema
helper exposing the three ensure functions, rebind the canonical
`MediaDatabase` methods in `media_database_impl.py`, and convert the legacy
`Media_DB_v2` methods into live-module compat shells. Keep constructor,
SQLite-backend, schema-v1, and rollback methods out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting:
   - `MediaDatabase._ensure_postgres_claims_tables(...)`
   - `MediaDatabase._ensure_postgres_collections_tables(...)`
   - `MediaDatabase._ensure_postgres_claims_extensions(...)`
   no longer resolve globals from `Media_DB_v2`.
2. Add failing compat-shell delegation regressions proving the legacy methods
   delegate through `schema/postgres_claims_collection_structures.py` via a
   live `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_postgres_claims_collection python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_ensure_postgres_claims_tables or _ensure_postgres_collections_tables or _ensure_postgres_claims_extensions'
```

Result: red as expected before rebinding; green after canonical and compat-shell updates.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_postgres_claims_collection_structures.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the new
   schema helper module.
2. Add focused helper tests covering:
   - claims-table create-table-first ordering plus extension call before
     non-create statements
   - representative collections-table DDL/index coverage
   - representative claims-extension column/backfill/table/index coverage
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_postgres_claims_collection python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_postgres_claims_collection_structures.py
```

Result: red as expected before the helper module existed; green after the helper/module rebinding landed.

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/postgres_claims_collection_structures.py`

**Steps:**
1. Move the `_ensure_postgres_claims_tables(...)`,
   `_ensure_postgres_collections_tables(...)`, and
   `_ensure_postgres_claims_extensions(...)` bodies into the new schema helper
   module.
2. Preserve:
   - claims-table create-table-first ordering
   - extension call before non-create statements
   - collections warning-and-continue behavior
   - representative claims-extension DDL/backfill/index behavior
3. Re-run the Task 2 helper slice.

Result: helper module added and helper slice passed after the canonical/legacy rebind completed.

### Task 4: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the three ensure helpers from
   `schema/postgres_claims_collection_structures.py`.
2. Rebind canonical `MediaDatabase` methods.
3. Re-run the Task 1 regression slice.

Result: canonical ownership assertions passed once the package-native class rebound to the new helper module.

### Task 5: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy method bodies with live-module compat shells delegating
   through `import_module(...)`.
2. Preserve all three method signatures exactly.
3. Re-run the Task 1 regression slice and the Task 2 helper slice.

Result: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_postgres_claims_collection python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_postgres_claims_collection_structures.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_claims_schema.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_claims_fts_triggers.py \
  -k '_ensure_postgres_claims_tables or _ensure_postgres_collections_tables or _ensure_postgres_claims_extensions or claims_tables or claims_extensions or collections'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `6`

**Verification Results**
- Pytest regression slice: `6 passed, 511 deselected, 6 warnings`
- Pytest helper slice: `5 passed, 6 warnings`
- Pytest tranche bundle: `14 passed, 574 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Normalized ownership count: `9 -> 6`
- `git diff --check`: clean
