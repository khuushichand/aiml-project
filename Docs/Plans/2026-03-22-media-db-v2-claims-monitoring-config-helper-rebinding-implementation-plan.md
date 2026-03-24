# Media DB V2 Claims Monitoring Config Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims monitoring-config CRUD and user-id helper
layer onto a package-owned runtime module so the canonical `MediaDatabase`
stops owning those methods through legacy globals while preserving API,
migration, and scheduler behavior.

**Architecture:** Add one runtime helper module for the seven in-scope methods,
rebind the canonical methods in `media_database_impl.py`, and convert the
legacy `Media_DB_v2` methods into live-module compat shells. Keep legacy alert
migration, claims CRUD/search, clustering, and bootstrap/schema helpers out of
scope for this tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `delete_claims_monitoring_configs_by_user(...)`
   - `list_claims_monitoring_configs(...)`
   - `create_claims_monitoring_config(...)`
   - `get_claims_monitoring_config(...)`
   - `update_claims_monitoring_config(...)`
   - `delete_claims_monitoring_config(...)`
   - `list_claims_monitoring_user_ids(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep legacy alert migration and all other claims/email/bootstrap helpers out
   of the regression surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_config python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claims_monitoring_config or claims_monitoring_user_ids'
```

Result: PASS after Tasks 4-5 (`14 passed, 423 deselected`)

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_config_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `create_claims_monitoring_config(...)` keeps backend-specific id retrieval
   - `list_claims_monitoring_configs(...)` preserves `id DESC` ordering
   - `get_claims_monitoring_config(...)` returns `{}` for a missing row
   - `update_claims_monitoring_config(...)` returns the existing row unchanged
     when no fields are provided
   - `update_claims_monitoring_config(...)` applies field coercion and returns a
     refreshed row after a write
   - `list_claims_monitoring_user_ids(...)` preserves mapping-row and tuple-row
     fallback while filtering null/empty ids
2. Keep these tests narrow and use canonical `MediaDatabase` methods or focused
   cursor stubs where backend shape matters.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_config python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_config_ops.py
```

Result: PASS after Task 3 (`5 passed`)

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_config_ops.py`

**Steps:**
1. Move the seven in-scope methods into the new runtime module.
2. Preserve:
   - backend-specific create id retrieval
   - no-op update behavior
   - field coercion and refreshed-row return on update
   - list ordering by `id DESC`
   - mapping-row then tuple-row fallback in
     `list_claims_monitoring_user_ids(...)`
   - null/empty filtering in `list_claims_monitoring_user_ids(...)`
3. Re-run the Task 2 helper slice.

Result: PASS (`5 passed`)

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `claims_monitoring_config_ops.py`.
2. Rebind the seven canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Result: PASS once legacy compat shells were added

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the seven legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave legacy alert migration and all unrelated helpers untouched.
4. Re-run the Task 1 regression slice.

Result: PASS (`14 passed, 423 deselected`)

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_config python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_config_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_alerts_scheduler.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Results:
- Pytest tranche bundle: `445 passed, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Ownership count: `47`
- `git diff --check`: clean
