# Media DB V2 Claims Cluster Exact Rebuild Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `MediaDatabase.rebuild_claim_clusters_exact(...)` onto a
package-owned runtime helper while preserving exact clustering behavior and
caller-facing claims-service flows.

**Architecture:** Add one runtime helper module for the active exact-rebuild
coordinator, rebind the canonical method in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` method into a live-module compat shell. Leave
`rebuild_claim_clusters_from_assignments(...)` untouched for a later tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing regression asserting canonical
   `MediaDatabase.rebuild_claim_clusters_exact` no longer uses legacy globals.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2` method delegates through a package helper module via a live
   `import_module(...)` reference.
3. Keep `rebuild_claim_clusters_from_assignments(...)` out of this regression
   surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_exact python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'rebuild_claim_clusters_exact'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_exact_rebuild_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - invalid `min_size` normalizes to the legacy default behavior
   - exact rebuild groups claims by normalized text
   - preexisting clusters, membership rows, and claim assignments are cleared
     before rebuild
   - created clusters end with `cluster_version=2`
   - PostgreSQL `RETURNING id` handling remains intact
2. Use real SQLite DB setup for rebuild semantics and a lightweight backend
   stub for the PostgreSQL id-return path.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_exact python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_exact_rebuild_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_cluster_exact_rebuild_ops.py`

**Steps:**
1. Move `rebuild_claim_clusters_exact(...)` into the new runtime module.
2. Preserve:
   - `min_size` normalization
   - exact-text normalization via lowercase plus collapsed whitespace
   - old cluster cleanup and `Claims.claim_cluster_id` reset
   - PostgreSQL `RETURNING id` handling
   - membership insert semantics and final cluster version bump
3. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper from `claims_cluster_exact_rebuild_ops.py`.
2. Rebind canonical `MediaDatabase.rebuild_claim_clusters_exact`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate legacy `rebuild_claim_clusters_exact(...)` through
   `import_module(...)`.
2. Keep the legacy method present as a compat shell.
3. Leave `rebuild_claim_clusters_from_assignments(...)` untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_exact python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_exact_rebuild_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_service_override_db.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `33`

**Verification Results**:
- Focused regression slice: `2 passed, 463 deselected, 6 warnings`
- Focused helper slice: `2 passed, 6 warnings`
- Tranche pytest bundle: `475 passed, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Ownership recount: `33`
- `git diff --check`: clean
