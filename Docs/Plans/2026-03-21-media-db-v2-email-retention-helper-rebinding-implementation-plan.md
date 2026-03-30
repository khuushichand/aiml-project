# Media DB V2 Email Retention Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the email retention and tenant hard-delete layer onto a
package-owned runtime module so the canonical `MediaDatabase` no longer owns
those methods through legacy globals while preserving retention and cleanup
behavior.

**Architecture:** Add one runtime helper module for the retention layer,
rebind the canonical methods in `media_database_impl.py`, and convert the
legacy `Media_DB_v2` methods into live-module compat shells. Keep tenant
resolution as an existing instance seam, and keep the tiny datetime parser
module-local instead of expanding the class surface.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting canonical ownership moved off legacy
   globals for:
   - `_cleanup_email_orphans_for_tenant(...)`
   - `enforce_email_retention_policy(...)`
   - `hard_delete_email_tenant_data(...)`
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through a package helper module via a live
   `import_module(...)` reference.
3. Keep `_resolve_email_tenant_id(...)` and
   `_parse_email_retention_datetime(...)` out of the regression surface for
   this tranche.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'cleanup_email_orphans_for_tenant or enforce_email_retention_policy or hard_delete_email_tenant_data'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_email_retention_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `_parse_email_retention_datetime(...)` parses ISO and RFC-2822 values
   - `_cleanup_email_orphans_for_tenant(...)` removes only orphaned rows and
     optional empty sources for the target tenant
   - `enforce_email_retention_policy(...)` respects `limit` and
     `include_missing_internal_date`
   - `hard_delete_email_tenant_data(...)` preserves tenant scope through the
     helper path
2. Keep these tests narrow: prove retention/helper behavior only, not the
   wider backfill or upsert surface.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_email_retention_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_retention_ops.py`

**Steps:**
1. Move the three in-scope helper bodies into the new runtime module.
2. Keep `_parse_email_retention_datetime(...)` as a module-local helper inside
   the runtime module.
3. Preserve current delete routing, tenant scoping, cleanup counts, and limit
   behavior.
4. Keep `_resolve_email_tenant_id(...)` routed through the DB instance.
5. Re-run the Task 2 helper slice.

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions from `email_retention_ops.py`.
2. Rebind the three canonical methods onto the package-owned helpers.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate each of the three legacy methods through `import_module(...)`.
2. Keep the legacy methods present as compat shells.
3. Leave `_resolve_email_tenant_id(...)`, backfill, and upsert methods
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
  tldw_Server_API/tests/DB_Management/test_media_db_email_retention_ops.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  -k 'cleanup_email_orphans_for_tenant or enforce_email_retention_policy or hard_delete_email_tenant_data or retention'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `94`

Result: Achieved. Focused retention verification passed, Bandit reported no
issues on touched production files, `git diff --check` was clean, and the
normalized ownership count dropped from `97` to `94`.
