# Media DB V2 Claims Review Read Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims review read layer onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals while preserving the existing claims-service and review
API contracts.

**Architecture:** Add one runtime helper module for the two claims review read
methods, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Keep review
mutation, review rules, analytics, monitoring, clustering, and broader claims
CRUD/search helpers out of scope for this tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `list_claim_review_history(...)`
   - `list_review_queue(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claim_review_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claim_review_history or review_queue'
```

Expected: FAIL

Result: PASS after canonical rebinding and legacy compat-shell delegation were
implemented. Focused regression slice: `4 passed, 383 deselected, 6 warnings`.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claim_review_read_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `list_claim_review_history(...)` returns rows in `created_at ASC` order
   - `list_review_queue(...)` preserves limit/offset normalization
   - `list_review_queue(...)` honors joined filters for status, reviewer,
     review_group, media_id, extractor, owner_user_id, and `include_deleted`
   - `list_review_queue(...)` respects module-level `get_scope()` visibility
     filtering for personal/team/org visibility and the `(0 = 1)` fallback
2. Keep these tests narrow and use canonical `MediaDatabase` methods.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claim_review_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claim_review_read_ops.py
```

Expected: FAIL

Result: PASS after the package runtime helper was added and the seed path was
aligned with the Media/Claims version triggers. Focused helper slice:
`3 passed, 6 warnings`.

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_review_read_ops.py`

**Steps:**
1. Move the two in-scope methods into the new runtime module.
2. Preserve:
   - history ordering via `created_at ASC`
   - queue limit/offset normalization and `100/0` fallback
   - queue joined filters and `reviewed_at DESC, id DESC` ordering
   - module-level `get_scope()` visibility semantics and `(0 = 1)` fallback
3. Re-run the Task 2 helper slice.

Expected: PASS

Result: PASS. Added
`tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_review_read_ops.py`
and preserved history ordering, queue paging normalization, joined filtering,
and the module-level `get_scope()` visibility semantics.

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from `claims_review_read_ops.py`.
2. Rebind the two canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase` review read methods now bind to the
package-owned runtime helpers in `media_database_impl.py`.

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the two legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave review mutation, review rules, analytics, monitoring, clustering, and
   broader claims CRUD/search helpers untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

Result: PASS. The two legacy review read methods now delegate through live
`import_module(...)` compat shells in `Media_DB_v2.py`.

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claim_review_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claim_review_read_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_review_api.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `72`

Result:
- Full tranche pytest bundle:
  `392 passed, 6 warnings`
- Bandit on touched production files: no issues
- Ownership count: `72`
- `git diff --check`: clean
