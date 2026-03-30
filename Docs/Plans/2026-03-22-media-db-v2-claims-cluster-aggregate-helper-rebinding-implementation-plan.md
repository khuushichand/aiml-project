# Media DB V2 Claims Cluster Aggregate Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims cluster aggregate-helper layer onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals while preserving watchlist notification
and claims cluster analytics behavior.

**Architecture:** Add one runtime helper module for the three aggregate helper
methods, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Keep cluster
CRUD, rebuild coordinators, legacy monitoring migration, claims CRUD/search,
and bootstrap/schema helpers out of scope for this tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `get_claim_clusters_by_ids(...)`
   - `get_claim_cluster_member_counts(...)`
   - `update_claim_clusters_watchlist_counts(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep cluster CRUD/rebuild and monitoring migration helpers out of the
   regression surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_aggregate python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claim_clusters_by_ids or claim_cluster_member_counts or update_claim_clusters_watchlist_counts'
```

Result: PASS after Tasks 4-5 (`6 passed, 437 deselected, 6 warnings`)

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_aggregate_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `get_claim_clusters_by_ids([]) == []`
   - `get_claim_cluster_member_counts([]) == {}`
   - `get_claim_cluster_member_counts(...)` preserves tuple-row fallback and
     ignores malformed rows
   - `update_claim_clusters_watchlist_counts({}) == 0`
   - `update_claim_clusters_watchlist_counts(...)` uses `execute_many(...)` and
     returns `len(params)`
2. Keep these tests narrow and use canonical `MediaDatabase` methods or simple
   stubs where backend behavior is not needed.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_aggregate python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_aggregate_ops.py
```

Result: PASS after Task 3 (`5 passed, 6 warnings`)

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_cluster_aggregate_ops.py`

**Steps:**
1. Move the three in-scope methods into the new runtime module.
2. Preserve:
   - empty-input fast returns
   - tuple-row fallback in member counts
   - malformed-row ignore behavior
   - `execute_many(...)` semantics and `len(params)` return value
3. Re-run the Task 2 helper slice.

Result: PASS (`5 passed, 6 warnings`)

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `claims_cluster_aggregate_ops.py`.
2. Rebind the three canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Result: PASS once legacy compat shells were added

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the three legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave cluster CRUD/rebuild and monitoring migration helpers untouched.
4. Re-run the Task 1 regression slice.

Result: PASS (`6 passed, 437 deselected, 6 warnings`)

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_aggregate python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_aggregate_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_cluster_links_and_search.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_service_override_db.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Results:
- Pytest tranche bundle: `457 passed, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Ownership count: `44`
- `git diff --check`: clean
