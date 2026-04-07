# Media DB V2 Bootstrap Dispatch Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the thin bootstrap/migration dispatcher methods onto the
existing package-owned schema helpers while preserving legacy compat entrypoints.

**Architecture:** Rebind the canonical `MediaDatabase` methods in
`media_database_impl.py` directly to the package helpers already defined under
`media_db.schema.*`, and convert the corresponding legacy `Media_DB_v2` methods
into live-module compat shells. Keep constructor, schema-v1, RLS, and rollback
methods out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting the following methods no longer
   resolve globals from `Media_DB_v2`:
   - `_initialize_schema(...)`
   - `_initialize_schema_sqlite(...)`
   - `_initialize_schema_postgres(...)`
   - `_run_postgres_migrations(...)`
   - `_get_postgres_migrations(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through:
   - `media_db.schema.bootstrap`
   - `media_db.schema.backends.sqlite_helpers`
   - `media_db.schema.backends.postgres_helpers`
   - `media_db.schema.migrations`
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_bootstrap_dispatch python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_initialize_schema or _run_postgres_migrations or _get_postgres_migrations'
```

Result: `6 passed, 501 deselected, 6 warnings`

### Task 2: Move Helper-Path Coverage To The Canonical Package Seam

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Update the existing `_initialize_schema(...)` helper-path test so it patches
   the package bootstrap module rather than `Media_DB_v2`.
2. Add focused canonical helper-path tests for:
   - `_initialize_schema_sqlite(...)`
   - `_initialize_schema_postgres(...)`
   - `_run_postgres_migrations(...)`
   - `_get_postgres_migrations(...)`
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_bootstrap_dispatch python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'initialize_schema or postgres_migrations'
```

Result: `5 passed, 58 deselected, 6 warnings`

### Task 3: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the existing package helpers:
   - `ensure_media_schema`
   - `bootstrap_sqlite_schema`
   - `bootstrap_postgres_schema`
   - `run_postgres_migrations`
   - `get_postgres_migrations`
2. Rebind canonical `MediaDatabase` methods to those helpers.
3. Re-run the Task 1 regression slice.

Result: canonical ownership assertions passed

### Task 4: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the five legacy method bodies with live-module compat shells using
   `import_module(...)`.
2. Preserve each public signature exactly.
3. Re-run the Task 1 regression slice and the Task 2 helper slice.

Result: compat-shell delegation and helper-path slices passed

### Task 5: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_bootstrap_dispatch python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  -k '_initialize_schema or _run_postgres_migrations or _get_postgres_migrations or postgres_migrations'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `11`

**Verification Results**
- Pytest tranche bundle: `13 passed, 575 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Normalized ownership count: `16 -> 11`
- `git diff --check`: clean
