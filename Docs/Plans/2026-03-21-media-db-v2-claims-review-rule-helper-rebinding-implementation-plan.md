# Media DB V2 Claims Review Rule Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims review-rule CRUD layer onto a package-owned
runtime module so the canonical `MediaDatabase` no longer owns those methods
through legacy globals while preserving the existing claims-service and review
assignment contracts.

**Architecture:** Add one runtime helper module for the five claims review-rule
methods, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Keep review
queue, review history, analytics, monitoring, clustering, and broader claims
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
   - `list_claim_review_rules(...)`
   - `create_claim_review_rule(...)`
   - `get_claim_review_rule(...)`
   - `update_claim_review_rule(...)`
   - `delete_claim_review_rule(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claim_review_rule'
```

Expected: FAIL

Result: PASS after canonical rebinding and legacy compat-shell delegation were
implemented. Focused regression slice: `10 passed, 373 deselected, 6 warnings`.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claim_review_rule_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `create_claim_review_rule(...)` returns the stored row
   - `list_claim_review_rules(...)` honors `active_only=True` and priority
     ordering
   - `get_claim_review_rule(...)` returns `{}` for a missing id
   - `update_claim_review_rule(...)` preserves the no-op return path and applies
     a real update
   - `delete_claim_review_rule(...)` removes the row
2. Keep these tests narrow and use canonical `MediaDatabase` methods.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_claim_review_rule_ops.py
```

Expected: FAIL

Result: PASS after the package runtime helper was added. Focused helper slice:
`4 passed, 6 warnings`.

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_review_rule_ops.py`

**Steps:**
1. Move the five in-scope methods into the new runtime module.
2. Preserve:
   - create read-after-write via `get_claim_review_rule(...)`
   - `active_only` filtering and `priority DESC, id DESC` ordering
   - update no-op return behavior
   - delete as a `None`-returning helper
3. Re-run the Task 2 helper slice.

Expected: PASS

Result: PASS. Added
`tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_review_rule_ops.py`
and preserved create read-after-write, `active_only` filtering with
`priority DESC, id DESC` ordering, update no-op returns, and `None`-returning
delete behavior.

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from `claims_review_rule_ops.py`.
2. Rebind the five canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase` review-rule methods now bind to the
package-owned runtime helpers in `media_database_impl.py`.

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the five legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave review queue, analytics, monitoring, clustering, and broader claims
   CRUD/search helpers untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

Result: PASS. The five legacy review-rule methods now delegate through live
`import_module(...)` compat shells in `Media_DB_v2.py`.

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_claim_review_rule_ops.py \
  tldw_Server_API/tests/Claims/test_claim_review_rule_assignment.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `74`

Result:
- Full tranche pytest bundle:
  `389 passed, 6 warnings`
- Bandit on touched production files: no issues
- Ownership count: `74`
- `git diff --check`: clean
