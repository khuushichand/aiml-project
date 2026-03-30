# Media DB V2 Claims Monitoring Legacy Migration Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the legacy claims monitoring alert migration coordinator onto a
package-owned runtime helper so the canonical `MediaDatabase` no longer owns
this method through legacy globals while preserving alerts API migration
behavior.

**Architecture:** Add one runtime helper module for
`migrate_legacy_claims_monitoring_alerts(...)`, rebind the canonical method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Keep the already-rebound alert/config helper layers
and all other claims surfaces out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing regression asserting canonical ownership moved off legacy
   globals for `migrate_legacy_claims_monitoring_alerts(...)`.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2` method delegates through a package helper module via a live
   `import_module(...)` reference.
3. Keep all monitoring CRUD helpers and claims cluster/search surfaces out of
   the regression surface.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_legacy_migration python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'migrate_legacy_claims_monitoring_alerts'
```

Result: PASS after Tasks 4-5 (`1 passed, 444 deselected, 6 warnings`)

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_migration_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - existing alerts short-circuit with `0`
   - missing legacy rows short-circuit with `0`
   - migrated alerts preserve explicit ids and delete configs after migration
   - malformed/truthy `email_recipients` still enables the email channel
2. Keep these tests narrow and use simple stubs instead of a real database when
   backend behavior is not needed.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_legacy_migration python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_migration_ops.py
```

Result: PASS after Task 3 (`4 passed, 6 warnings`)

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_migration_ops.py`

**Steps:**
1. Move `migrate_legacy_claims_monitoring_alerts(...)` into the new runtime
   module.
2. Preserve:
   - existing-alert short circuit
   - empty-legacy short circuit
   - explicit-id migration into alert rows
   - email channel derivation for JSON lists and malformed truthy strings
   - delete-after-migrate semantics
3. Re-run the Task 2 helper slice.

Result: PASS (`4 passed, 6 warnings`)

### Task 4: Rebind Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper from `claims_monitoring_migration_ops.py`.
2. Rebind the canonical method onto the package-owned helper.
3. Re-run the Task 1 regression slice.

Result: PASS once the legacy compat shell was added

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the legacy method through `import_module(...)`.
2. Keep the legacy method present as a compat shell.
3. Leave all monitoring CRUD and other claims helpers untouched.
4. Re-run the Task 1 regression slice.

Result: PASS (`1 passed, 444 deselected, 6 warnings`)

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_monitoring_legacy_migration python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_migration_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_monitoring_api.py
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Results:
- Pytest tranche bundle: `451 passed, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Ownership count: `43`
- `git diff --check`: clean
