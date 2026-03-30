# Media DB V2 Claims Monitoring Event Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims monitoring event delivery layer onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals while preserving webhook recording, digest
delivery, and analytics/export behavior.

**Architecture:** Add one runtime helper module for the five event delivery
methods, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Keep claims
monitoring config CRUD, alert migration, claims review, clustering, and search
helpers out of scope for this tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `insert_claims_monitoring_event(...)`
   - `list_claims_monitoring_events(...)`
   - `list_undelivered_claims_monitoring_events(...)`
   - `mark_claims_monitoring_events_delivered(...)`
   - `get_latest_claims_monitoring_event_delivery(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep claims monitoring config CRUD, alert migration, claims review,
   clustering, and search helpers out of the regression surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_event python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claims_monitoring_event'
```

Expected: FAIL

Result: PASS after canonical rebinding and legacy compat-shell delegation were
implemented. Red phase:
`10 failed, 405 deselected, 6 warnings`.
Focused regression slice:
`10 passed, 405 deselected, 6 warnings`.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_event_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `insert_claims_monitoring_event(...)` writes a row with `delivered_at`
     stored as `None`
   - `list_claims_monitoring_events(...)` preserves optional filter behavior
     and `created_at ASC` ordering
   - `list_undelivered_claims_monitoring_events(...)` clamps and coerces the
     limit argument the same way the legacy method does
   - `mark_claims_monitoring_events_delivered(...)` returns `0` for an empty id
     list and returns the rowcount for a real update
   - `get_latest_claims_monitoring_event_delivery(...)` returns `None` for no
     rows and preserves tuple-row fallback behavior
2. Keep these tests narrow and use canonical `MediaDatabase` methods.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_event python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_event_ops.py
```

Expected: FAIL

Result: PASS after the package runtime helper was added. Red phase:
collection failed because
`claims_monitoring_event_ops.py` did not exist yet.
Focused helper slice:
`5 passed, 6 warnings`.

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_event_ops.py`

**Steps:**
1. Move the five in-scope methods into the new runtime module.
2. Preserve:
   - created-at writes through `self._get_current_utc_timestamp_str()`
   - `delivered_at=None` on insert
   - list filter semantics and `created_at ASC` ordering
   - undelivered limit coercion and clamp behavior
   - mark-delivered empty-list short circuit and rowcount fallback
   - latest-delivery `None` behavior and tuple-row fallback
3. Re-run the Task 2 helper slice.

Expected: PASS

Result: PASS. Added
`tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_event_ops.py`
and preserved created-at writes through
`self._get_current_utc_timestamp_str()`, `delivered_at=None` on insert, list
filter semantics, undelivered limit clamp behavior, mark-delivered rowcount
fallback, and latest-delivery tuple-row fallback behavior.

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `claims_monitoring_event_ops.py`.
2. Rebind the five canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase` event delivery methods now bind to the
package-owned runtime helpers in `media_database_impl.py`.

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the five legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave config CRUD, alert migration, claims review, clustering, and search
   helpers untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

Result: PASS. The five legacy event delivery methods now delegate through live
`import_module(...)` compat shells in `Media_DB_v2.py`.

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_event python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_event_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_alerts_digest.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_webhook_delivery.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `58`

Result:
- Full tranche pytest bundle:
  `425 passed, 6 warnings`
- Bandit on touched production files:
  `{'results': 0, 'errors': 0}`
- Ownership count:
  `58`
- `git diff --check`:
  clean
