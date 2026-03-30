# Media DB V2 Claims Notification Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims notification helper cluster onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals while preserving the existing
claims-service and claims-notifications contracts.

**Architecture:** Add one runtime helper module for the six claims notification
methods, rebind the canonical methods in `media_database_impl.py`, and convert
the legacy `Media_DB_v2` methods into live-module compat shells. Keep claims
review, monitoring, cluster, and analytics-export helpers out of scope for this
tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `insert_claim_notification(...)`
   - `get_claim_notification(...)`
   - `get_latest_claim_notification(...)`
   - `list_claim_notifications(...)`
   - `get_claim_notifications_by_ids(...)`
   - `mark_claim_notifications_delivered(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claim_notification'
```

Expected: FAIL

Result: PASS after canonical rebinding and legacy compat-shell delegation were
implemented. Focused regression slice: `12 passed, 361 deselected, 6 warnings`.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claim_notification_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `insert_claim_notification(...)` returns the freshly readable row
   - `get_latest_claim_notification(...)` honors optional resource filters
   - `list_claim_notifications(...)` respects delivered filtering and tolerant
     `limit/offset` normalization
   - `get_claim_notifications_by_ids([])` returns `[]`
   - `mark_claim_notifications_delivered([])` returns `0`
   - `mark_claim_notifications_delivered(...)` marks selected rows delivered
2. Keep these tests narrow and use canonical `MediaDatabase` methods.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_claim_notification_ops.py
```

Expected: FAIL

Result: PASS after the package runtime helper was added. Focused helper slice:
`4 passed, 6 warnings`.

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_notification_ops.py`

**Steps:**
1. Move the six in-scope methods into the new runtime module.
2. Preserve:
   - read-after-write via `get_claim_notification(...)`
   - latest lookup ordering and optional resource filters
   - list delivered semantics and tolerant limit/offset handling
   - empty-id fast paths for batch fetch and mark-delivered
3. Re-run the Task 2 helper slice.

Expected: PASS

Result: PASS. Added
`tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_notification_ops.py`
and preserved read-after-write, optional resource filters, delivered filtering,
tolerant paging, and empty-id fast paths.

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from `claims_notification_ops.py`.
2. Rebind the six canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase` notification methods now bind to the
package-owned runtime helpers in `media_database_impl.py`.

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the six legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave claims review, monitoring, cluster, and analytics-export helpers
   untouched.
4. Re-run the Task 1 regression slice.

Expected: PASS

Result: PASS. The six legacy notification methods now delegate through live
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
  tldw_Server_API/tests/DB_Management/test_media_db_claim_notification_ops.py \
  tldw_Server_API/tests/Claims/test_claims_review_notifications.py \
  tldw_Server_API/tests/Claims/test_claims_watchlist_notifications.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `79`

Result:
- Full tranche pytest bundle:
  `380 passed, 6 warnings`
- Bandit on touched production files: no issues
- Ownership count: `79`
- `git diff --check`: clean
