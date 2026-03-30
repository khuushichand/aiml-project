# Media DB V2 Backend-Prepare Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_prepare_backend_statement`,
`_prepare_backend_many_statement`, and `_normalise_params` onto package-owned
runtime helpers so the canonical `MediaDatabase` no longer owns those
backend-preparation methods through the legacy module, while preserving the
`Media_DB_v2` compat shell and keeping the exact forwarding contract unchanged.

**Architecture:** Add one package runtime helper module for the backend-prep
wrappers, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods to live-module compat shells. Verify
exact forwarding with focused wrapper tests and reuse the existing query-utils
test suite as the broader guard.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._prepare_backend_statement` is no longer
     legacy-owned
   - canonical `MediaDatabase._prepare_backend_many_statement` is no longer
     legacy-owned
   - canonical `MediaDatabase._normalise_params` is no longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'prepare_backend_statement or prepare_backend_many_statement or normalise_params'
```

Expected: FAIL

### Task 2: Add Wrapper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_backend_utils.py`

**Steps:**
1. Add failing unit tests asserting exact forwarding for:
   - `_prepare_backend_statement`
   - `_prepare_backend_many_statement`
   - `_normalise_params`
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_backend_utils.py \
  -k 'media_db_runtime_prepare'
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/backend_prepare_ops.py`

**Steps:**
1. Create package-owned wrapper functions for the three helper methods
2. Preserve exact forwarding defaults
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package wrapper functions
2. Rebind the three canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the three legacy methods through `import_module(...)`
2. Keep the legacy methods present as compat shells
3. Re-run the Task 1 regression slice

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
  tldw_Server_API/tests/DB_Management/test_backend_utils.py \
  tldw_Server_API/tests/DB_Management/test_postgres_returning_and_workflows.py \
  tldw_Server_API/tests/DB_Management/unit/test_postgres_placeholder_prepare.py \
  -k 'prepare_backend_statement or prepare_backend_many_statement or normalise_params or media_db_runtime_prepare'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `202`
