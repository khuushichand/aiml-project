# Media DB V2 Claims Monitoring Alert Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims monitoring alert CRUD layer onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals while preserving alert CRUD, digest, and
legacy-migration behavior.

**Architecture:** Add one runtime helper module for the five alert CRUD
methods, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Keep legacy
config CRUD, migration orchestration, monitoring events, health, analytics, and
scheduler helpers out of scope for this tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `list_claims_monitoring_alerts(...)`
   - `get_claims_monitoring_alert(...)`
   - `create_claims_monitoring_alert(...)`
   - `update_claims_monitoring_alert(...)`
   - `delete_claims_monitoring_alert(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep legacy config CRUD, migration orchestration, monitoring events, and
   health helpers out of the regression surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_alert python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claims_monitoring_alert'
```

Expected: FAIL

Result: PASS after canonical rebinding and legacy compat-shell delegation were
implemented. Focused regression slice:
`10 passed, 391 deselected, 6 warnings`.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_alert_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `list_claims_monitoring_alerts(...)` preserves `id DESC` ordering
   - `get_claims_monitoring_alert(...)` returns `{}` for a missing row
   - `create_claims_monitoring_alert(...)` preserves an explicit `alert_id`
     during the legacy migration path
   - `update_claims_monitoring_alert(...)` returns the current row on a no-op
     update and preserves untouched fields on partial updates
   - `delete_claims_monitoring_alert(...)` removes the row
2. Keep these tests narrow and use canonical `MediaDatabase` methods.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_alert python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_alert_ops.py
```

Expected: FAIL

Result: PASS after the package runtime helper was added. Focused helper slice:
`3 passed, 6 warnings`.

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_alert_ops.py`

**Steps:**
1. Move the five in-scope methods into the new runtime module.
2. Preserve:
   - list ordering by `id DESC`
   - missing-row `{}` behavior
   - explicit `alert_id` insert behavior
   - PostgreSQL `setval(...)` repair in the explicit-id path
   - no-op update return behavior
   - partial update plus read-after-write semantics
3. Re-run the Task 2 helper slice.

Expected: PASS

Result: PASS. Added
`tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_alert_ops.py`
and preserved list ordering, missing-row `{}` behavior, explicit `alert_id`
insert behavior, PostgreSQL `setval(...)` repair, no-op update return
behavior, and partial update read-after-write semantics.

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `claims_monitoring_alert_ops.py`.
2. Rebind the five canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase` alert CRUD methods now bind to the
package-owned runtime helpers in `media_database_impl.py`.

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the five legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave legacy config CRUD, migration orchestration, monitoring events, and
   health helpers untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

Result: PASS. The five legacy alert CRUD methods now delegate through live
`import_module(...)` compat shells in `Media_DB_v2.py`.

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_alert python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_alert_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_alerts_digest.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `65`

Result:
- Full tranche pytest bundle:
  `407 passed, 6 warnings`
- Bandit on touched production files: no issues
- Ownership count: `65`
- `git diff --check`: clean
