# Media DB V2 Claims Write Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the remaining direct claims write helpers onto a package-owned
runtime module while preserving insert defaults, review conflict behavior,
audit-log writes, version bumps, and backend-specific FTS side effects.

**Architecture:** Add a `claims_write_ops.py` runtime helper that owns
`upsert_claims(...)`, `update_claim(...)`, `update_claim_review(...)`, and
`soft_delete_claims_for_media(...)`, rebind the canonical `MediaDatabase`
methods in `media_database_impl.py`, and convert the legacy `Media_DB_v2`
methods into live-module compat shells. Keep list/search, cluster rebuild, and
broader claims-service coordinators out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting the four canonical
   `MediaDatabase` methods no longer resolve their globals from `Media_DB_v2`.
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through `claims_write_ops.py` via live
   `import_module(...)` references.
3. Use `inspect.signature(...)`-derived forwarding expectations for the legacy
   delegation checks so defaults are not hard-coded incorrectly.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_write python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'upsert_claims or update_claim or update_claim_review or soft_delete_claims_for_media'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_write_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Add focused `upsert_claims(...)` helper tests covering:
   - empty-input fast return
   - default extractor / extractor_version / client_id shaping
   - generated UUID / timestamp fallback behavior
   - returned insert count
3. Add focused `update_claim(...)` helper tests covering:
   - no-op return path
   - SQLite update path bumping `version`, `last_modified`, and `client_id`
   - PostgreSQL stub branch refreshing `claims_fts_tsv` only when
     `claim_text` changes
4. Add focused `update_claim_review(...)` helper tests covering:
   - optimistic-lock conflict return
   - corrected-text path with review-log insert
   - PostgreSQL stub FTS refresh on corrected text
   - no-op return path
5. Add focused `soft_delete_claims_for_media(...)` helper tests covering:
   - SQLite affected-row count and `claims_fts` delete statement
   - PostgreSQL branch skipping SQLite cleanup
6. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_write python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_write_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_write_ops.py`

**Steps:**
1. Move the four write-method bodies into the new runtime module.
2. Preserve:
   - insert-row shaping and defaults in `upsert_claims(...)`
   - no-op and final readback behavior in `update_claim(...)`
   - conflict handling, review logging, and corrected-text mutation in
     `update_claim_review(...)`
   - backend-specific soft-delete cleanup in
     `soft_delete_claims_for_media(...)`
3. Re-run the Task 2 helper slice.

Expected: helper slice still red only for canonical binding

### Task 4: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the four helpers from `claims_write_ops.py`.
2. Rebind canonical `MediaDatabase.upsert_claims`,
   `MediaDatabase.update_claim`, `MediaDatabase.update_claim_review`, and
   `MediaDatabase.soft_delete_claims_for_media`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the four legacy method bodies with live-module compat shells
   delegating through `import_module(...)`.
2. Preserve the public signatures exactly.
3. Re-run the Task 1 regression slice.

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_write python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_write_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_metrics_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_claims_fts_triggers.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_add_endpoint.py \
  -k 'upsert_claims or update_claim or update_claim_review or soft_delete_claims_for_media or claims_review or claims_fts'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `22`

**Verification Results**:
- Focused ownership slice: `22 passed, 465 deselected, 6 warnings`
- Focused helper slice: `10 passed, 6 warnings`
- Tranche pytest bundle: `53 passed, 471 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Ownership count: `22`
- `git diff --check`: clean
