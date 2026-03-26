# Media DB V2 Claims Analytics Export Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims analytics export helper cluster onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals while preserving the existing claims
service and API contract.

**Architecture:** Add one runtime helper module for the five claims analytics
export methods, rebind the canonical methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Keep
claims notifications, monitoring, review, and cluster logic out of scope for
this tranche.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `create_claims_analytics_export(...)`
   - `get_claims_analytics_export(...)`
   - `list_claims_analytics_exports(...)`
   - `count_claims_analytics_exports(...)`
   - `cleanup_claims_analytics_exports(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'claims_analytics_export'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_analytics_export_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `create_claims_analytics_export(...)` returns the freshly readable row
   - `get_claims_analytics_export(...)` honors the optional `user_id` filter
   - `list_claims_analytics_exports(...)` and
     `count_claims_analytics_exports(...)` stay in filter parity for `status`
     and `format`
   - `cleanup_claims_analytics_exports(...)` returns `0` for invalid and
     non-positive `retention_hours`
2. Keep these tests narrow and use canonical `MediaDatabase` methods.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_claims_analytics_export_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_analytics_export_ops.py`

**Steps:**
1. Move the five in-scope methods into the new runtime module.
2. Preserve:
   - read-after-write via `get_claims_analytics_export(...)`
   - `status` and `format` filter parity between list and count
   - optional `user_id` scoping on get
   - tolerant `retention_hours` handling for cleanup
3. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from
   `claims_analytics_export_ops.py`.
2. Rebind the five canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the five legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave claims notifications, monitoring, review, and cluster methods
   untouched.
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
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_claims_analytics_export_ops.py \
  tldw_Server_API/tests/Claims/test_claims_analytics_exports_cleanup.py \
  tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py \
  -k 'claims_analytics_export or analytics_export or analytics export'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `85`

Result: Achieved. The focused ownership/delegation slice passed, the canonical
helper-path tests passed, the broader claims analytics bundle passed, Bandit
reported `0` results and `0` errors on touched production files, `git diff
--check` was clean, the spec and code-quality review gates returned no
findings, and the normalized ownership count dropped from `90` to `85`.
