# Media DB V2 Claims Cluster Assignment Rebuild Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `MediaDatabase.rebuild_claim_clusters_from_assignments(...)`
onto a package-owned runtime helper while preserving cleanup order, membership
insert semantics, and the live embeddings-clustering caller path.

**Architecture:** Add one runtime helper module for the assignment-based
cluster rebuild coordinator, rebind the canonical method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Leave exact rebuild and broader claims CRUD/search
surfaces untouched.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Completed

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing regression asserting canonical
   `MediaDatabase.rebuild_claim_clusters_from_assignments` no longer uses
   legacy globals.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2` method delegates through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_assignments python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'rebuild_claim_clusters_from_assignments'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Completed

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_assignment_rebuild_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - canonical `db.rebuild_claim_clusters_from_assignments` is rebound to the
     package helper
   - stale cluster rows, membership rows, and claim assignments are cleared
     before rebuild
   - malformed members without `claim_id` are ignored
   - `claims_assigned` counts valid input members
   - PostgreSQL `RETURNING id` handling remains intact
2. Use a real SQLite DB for cleanup semantics and a lightweight backend stub
   for the PostgreSQL inserted-id path.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_assignments python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_assignment_rebuild_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Completed

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_cluster_assignment_rebuild_ops.py`

**Steps:**
1. Move `rebuild_claim_clusters_from_assignments(...)` into the new runtime
   module.
2. Preserve:
   - stale cluster cleanup and owner-scoped claim reset
   - `cluster_version=1` insert behavior
   - member filtering for missing `claim_id`
   - `claims_assigned` input-count semantics
   - PostgreSQL `RETURNING id` handling
3. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind The Canonical Method

**Status**: Completed

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper from
   `claims_cluster_assignment_rebuild_ops.py`.
2. Rebind canonical
   `MediaDatabase.rebuild_claim_clusters_from_assignments`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Completed

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate legacy `rebuild_claim_clusters_from_assignments(...)` through
   `import_module(...)`.
2. Keep the legacy method present as a compat shell.
3. Leave exact rebuild and adjacent claims methods untouched.
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
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_assignments python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'rebuild_claim_clusters_from_assignments'

source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_assignments python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_cluster_assignment_rebuild_ops.py

source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_cluster_assignments python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_clustering_embeddings.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py::test_claims_clustering_does_not_bind_media_database_from_shim
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `31`

---

## Outcome

- Added package runtime helper:
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_cluster_assignment_rebuild_ops.py`
- Rebound canonical `MediaDatabase.rebuild_claim_clusters_from_assignments` in
  `media_database_impl.py`
- Converted legacy `Media_DB_v2.rebuild_claim_clusters_from_assignments(...)`
  into a live-module compat shell
- Added ownership/delegation regressions in
  `test_media_db_v2_regressions.py`
- Added focused helper-path coverage in
  `test_media_db_claims_cluster_assignment_rebuild_ops.py`

## Verification

- Focused ownership slice:
  - `2 passed, 467 deselected, 6 warnings`
- Focused helper slice:
  - `2 passed, 6 warnings`
- Caller/import guard slice:
  - `3 passed, 10 warnings`
- Bandit on touched production files:
  - `0` results, `0` errors
- Normalized ownership count:
  - `32 -> 31`
- `git diff --check`:
  - clean

## Notes

- A broader run including the full `test_media_db_api_imports.py` file still
  hits unrelated pre-existing branch failures:
  - `test_media_db_api_soft_delete_keyword_accepts_partial_legacy_like_db`
  - `test_app_source_only_compat_hosts_mention_media_db_v2`
- The tranche uses the relevant claims-clustering import guard instead of the
  full file as its completion gate.
