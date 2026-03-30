# Media DB V2 Claims Direct Read Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the three direct claims read helpers onto a package-owned
runtime module while preserving ordering, deleted-row handling, media visibility
filtering, and UUID lookup semantics.

**Architecture:** Add one runtime helper module for the direct claims read
surface, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Leave
`list_claims(...)` and the broader claims CRUD/search methods untouched.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical:
   - `MediaDatabase.get_claims_by_media`
   - `MediaDatabase.get_claim_with_media`
   - `MediaDatabase.get_claims_by_uuid`
   no longer use legacy globals.
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_direct_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'get_claims_by_media or get_claim_with_media or get_claims_by_uuid'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claim_read_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - canonical bindings are rebound to the package helper module
   - `get_claims_by_media(...)` excludes deleted rows and preserves ordering
   - `get_claim_with_media(...)` respects `include_deleted` and scope filtering
   - `get_claims_by_uuid([])` fast-returns `[]`
   - `get_claims_by_uuid(...)` returns the selected rows for multiple UUIDs
2. Use a real SQLite DB setup and monkeypatch `get_scope()` only where needed
   for the visibility-filter branch.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_direct_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claim_read_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_read_ops.py`

**Steps:**
1. Move the three direct-read helper bodies into the new runtime module.
2. Preserve:
   - media-ordering and deleted filtering in `get_claims_by_media(...)`
   - scope-aware visibility filtering in `get_claim_with_media(...)`
   - empty-input fast return and placeholder expansion in `get_claims_by_uuid(...)`
3. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helpers from `claims_read_ops.py`.
2. Rebind canonical:
   - `MediaDatabase.get_claims_by_media`
   - `MediaDatabase.get_claim_with_media`
   - `MediaDatabase.get_claims_by_uuid`
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the three legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave `list_claims(...)` and adjacent claims methods untouched.
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
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_direct_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claim_read_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_ingestion_claims_sql.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_endpoints_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_items_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claim_review_rule_assignment.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `28`

---

## Outcome

- Added package runtime helper:
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_read_ops.py`
- Rebound canonical `MediaDatabase.get_claims_by_media(...)`,
  `MediaDatabase.get_claim_with_media(...)`, and
  `MediaDatabase.get_claims_by_uuid(...)` in `media_database_impl.py`
- Converted the legacy `Media_DB_v2` methods into live-module compat shells
- Added ownership/delegation regressions in
  `test_media_db_v2_regressions.py`
- Added focused helper-path coverage in
  `test_media_db_claim_read_ops.py`

## Verification

- Focused ownership slice:
  - `6 passed, 469 deselected, 6 warnings`
- Focused helper slice:
  - `1 passed, 6 warnings`
- Tranche pytest bundle:
  - `483 passed, 6 warnings`
- Bandit on touched production files:
  - `0` results, `0` errors
- Normalized ownership count:
  - `31 -> 28`
- `git diff --check`:
  - clean
