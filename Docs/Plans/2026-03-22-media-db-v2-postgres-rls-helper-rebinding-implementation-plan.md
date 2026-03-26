# Media DB V2 Postgres RLS Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the PostgreSQL RLS helper pair onto a package-owned schema
module while preserving non-fatal policy probing and idempotent policy setup.

**Architecture:** Add a `postgres_rls.py` schema helper exposing
`_postgres_policy_exists(...)` and `_ensure_postgres_rls(...)`, rebind the
canonical `MediaDatabase` methods in `media_database_impl.py`, and convert the
legacy `Media_DB_v2` methods into live-module compat shells. Keep constructor,
schema-v1, and rollback methods out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting:
   - `MediaDatabase._postgres_policy_exists(...)`
   - `MediaDatabase._ensure_postgres_rls(...)`
   no longer resolve globals from `Media_DB_v2`.
2. Add failing compat-shell delegation regressions proving the legacy methods
   delegate through `schema/features/postgres_rls.py` via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_postgres_rls python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_postgres_policy_exists or _ensure_postgres_rls'
```

Result: red as expected before rebinding; green after canonical and compat-shell updates.

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_postgres_rls_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the new
   schema helper module.
2. Add focused helper tests covering:
   - successful policy probe behavior
   - false-on-probe-error behavior
   - conditional old media policy drops
   - unconditional media policy drop/recreate
   - sync-log create-if-missing behavior
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_postgres_rls python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_postgres_rls_ops.py
```

Result: red as expected before the helper module existed; green after helper/module rebinding landed.

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/features/postgres_rls.py`

**Steps:**
1. Move the `_postgres_policy_exists(...)` and `_ensure_postgres_rls(...)`
   bodies into the new schema helper module.
2. Preserve:
   - warning-and-false policy probe behavior
   - visibility-aware media predicates
   - sync-log admin/personal/org/team predicates
   - conditional old-policy drops
   - media drop/recreate behavior
   - sync-log create-if-missing behavior
3. Re-run the Task 2 helper slice.

Result: helper module added and helper slice passed after the canonical/legacy rebind completed.

### Task 4: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `_postgres_policy_exists(...)` and `_ensure_postgres_rls(...)` from
   `schema/features/postgres_rls.py`.
2. Rebind canonical `MediaDatabase` methods.
3. Re-run the Task 1 regression slice.

Result: canonical ownership assertions passed once the package-native class rebound to the new helper module.

### Task 5: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy method bodies with live-module compat shells delegating
   through `import_module(...)`.
2. Preserve both public signatures exactly.
3. Re-run the Task 1 regression slice and the Task 2 helper slice.

Result: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_postgres_rls python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_postgres_rls_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
  -k '_postgres_policy_exists or _ensure_postgres_rls or postgres_content_backend or v19'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `9`

**Verification Results**
- Pytest regression slice: `4 passed, 507 deselected, 6 warnings`
- Pytest helper slice: `4 passed, 6 warnings`
- Pytest tranche bundle: `13 passed, 578 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Normalized ownership count: `11 -> 9`
- `git diff --check`: clean
