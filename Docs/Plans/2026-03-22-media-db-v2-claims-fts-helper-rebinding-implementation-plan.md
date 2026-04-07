# Media DB V2 Claims FTS Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `MediaDatabase.rebuild_claims_fts(...)` onto a package-owned
runtime helper while preserving SQLite recovery behavior, PostgreSQL backend
integration, and caller-facing claims-service flows.

**Architecture:** Add one runtime helper module for the claims FTS rebuild
coordinator, rebind the canonical method in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` method into a live-module compat shell. Leave
claims CRUD/search methods and claims cluster rebuild methods untouched.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Completed

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing regression asserting canonical
   `MediaDatabase.rebuild_claims_fts` no longer uses legacy globals.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2` method delegates through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_fts python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'rebuild_claims_fts'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Completed

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_fts_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - canonical `db.rebuild_claims_fts` is rebound to the package helper
   - SQLite rebuild recreates `claims_fts` when the table is missing
   - PostgreSQL helper path still calls `backend.create_fts_table(...)` and
     returns the counted non-deleted rows
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_fts python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_fts_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Completed

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_fts_ops.py`

**Steps:**
1. Move `rebuild_claims_fts(...)` into the new runtime module.
2. Preserve:
   - SQLite `delete-all` reset
   - SQLite missing-table recreate path
   - PostgreSQL `backend.create_fts_table(...)` call
   - `claims_fts_tsv` refresh query
   - backend-specific counts and error normalization
3. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind The Canonical Method

**Status**: Completed

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper from `claims_fts_ops.py`.
2. Rebind canonical `MediaDatabase.rebuild_claims_fts`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Completed

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate legacy `rebuild_claims_fts(...)` through `import_module(...)`.
2. Keep the legacy method present as a compat shell.
3. Leave adjacent claims methods untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Completed

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_fts python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_fts_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_service_override_db.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG/test_dual_backend_end_to_end.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `32`

---

## Outcome

- Added package runtime helper: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_fts_ops.py`
- Rebound canonical `MediaDatabase.rebuild_claims_fts` in `media_database_impl.py`
- Converted legacy `Media_DB_v2.rebuild_claims_fts(...)` into a live-module compat shell
- Added ownership/delegation regressions in `test_media_db_v2_regressions.py`
- Added focused helper-path coverage in `test_media_db_claims_fts_ops.py`

## Verification

- Focused ownership slice:
  - `2 passed, 465 deselected, 6 warnings`
- Focused helper slice:
  - `2 passed, 6 warnings`
- Tranche pytest bundle:
  - `496 passed, 3 skipped, 6 warnings`
- Bandit on touched production files:
  - `0` results, `0` errors
- Normalized ownership count:
  - `33 -> 32`
- `git diff --check`:
  - clean
