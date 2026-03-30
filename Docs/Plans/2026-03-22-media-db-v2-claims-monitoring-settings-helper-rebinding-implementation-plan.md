# Media DB V2 Claims Monitoring Settings Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims monitoring settings helper pair onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals while preserving the existing
claims-service and monitoring-config API contracts.

**Architecture:** Add one runtime helper module for the two monitoring settings
methods, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Keep alert,
event, health, analytics, and scheduler helpers out of scope for this tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `get_claims_monitoring_settings(...)`
   - `upsert_claims_monitoring_settings(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_settings python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claims_monitoring_settings'
```

Expected: FAIL

Result: PASS after canonical rebinding and legacy compat-shell delegation were
implemented. Focused regression slice: `4 passed, 387 deselected, 6 warnings`.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_settings_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `get_claims_monitoring_settings(...)` returns `{}` for a missing row
   - `upsert_claims_monitoring_settings(...)` insert path persists default
     enabled state when `enabled=None`
   - `upsert_claims_monitoring_settings(...)` no-op update path returns the
     current row unchanged
   - `upsert_claims_monitoring_settings(...)` partial update preserves
     untouched fields and updates supplied ones
2. Keep these tests narrow and use canonical `MediaDatabase` methods.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_settings python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_settings_ops.py
```

Expected: FAIL

Result: PASS after the package runtime helper was added. Focused helper slice:
`3 passed, 6 warnings`.

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_settings_ops.py`

**Steps:**
1. Move the two in-scope methods into the new runtime module.
2. Preserve:
   - empty-dict missing-row behavior
   - insert default-enabled behavior
   - update no-op return behavior
   - partial update plus read-after-write semantics
3. Re-run the Task 2 helper slice.

Expected: PASS

Result: PASS. Added
`tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_settings_ops.py`
and preserved missing-row `{}` behavior, default-enabled inserts, no-op update
returns, partial updates, and read-after-write semantics.

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `claims_monitoring_settings_ops.py`.
2. Rebind the two canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase` monitoring settings methods now bind to
the package-owned runtime helpers in `media_database_impl.py`.

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the two legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave alert, event, health, analytics, and scheduler helpers untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

Result: PASS. The two legacy monitoring settings methods now delegate through
live `import_module(...)` compat shells in `Media_DB_v2.py`.

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_settings python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_settings_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_alerts_digest.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `70`

Result:
- Full tranche pytest bundle:
  `396 passed, 6 warnings`
- Bandit on touched production files: no issues
- Ownership count: `70`
- `git diff --check`: clean
