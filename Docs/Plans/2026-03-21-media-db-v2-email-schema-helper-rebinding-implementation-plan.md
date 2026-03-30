# Media DB V2 Email Schema Helper Rebinding Implementation Plan

**Goal:** Rebind `_ensure_sqlite_email_schema()` and
`_ensure_postgres_email_schema()` onto a package-owned schema helper module so
the canonical `MediaDatabase` no longer owns that email schema ensure pair
through `Media_DB_v2`, while preserving the legacy compat shell and keeping
email-native schema/index behavior unchanged.

**Architecture:** Add one package schema helper module for the email schema
ensure pair, rebind the canonical methods in `media_database_impl.py`, and
convert the legacy methods in `Media_DB_v2.py` into live-module compat shells.
Verify with direct ownership regressions, focused helper-path tests, and the
existing SQLite email and Postgres v22 migration guards.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._ensure_sqlite_email_schema` is no longer
     legacy-owned
   - canonical `MediaDatabase._ensure_postgres_email_schema` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_ensure_sqlite_email_schema or _ensure_postgres_email_schema'
```

Outcome: PASS after canonical rebinding and compat-shell conversion

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `ensure_sqlite_email_schema(...)` executes schema/index/FTS scripts in
     order and only rebuilds when `email_fts` did not previously exist
   - `ensure_postgres_email_schema(...)` executes converted schema/index
     statements in order and tolerates one failing statement
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'email_schema'
```

Outcome: PASS after package helper module creation

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/email_schema_structures.py`

**Steps:**
1. Create package-owned implementations for:
   - `ensure_sqlite_email_schema(...)`
   - `ensure_postgres_email_schema(...)`
2. Preserve the existing rebuild gating, conversion, and warning-only behavior
3. Re-run the Task 2 helper slice

Outcome: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the two canonical methods
3. Re-run the Task 1 regression slice

Outcome: canonical ownership assertions passed

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the two legacy methods through `import_module(...)`
2. Keep the legacy methods present as compat shells
3. Re-run the Task 1 regression slice

Outcome: PASS

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
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  -k '_ensure_sqlite_email_schema or _ensure_postgres_email_schema or email_schema'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Verification:
- `python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py tldw_Server_API/tests/DB_Management/test_email_native_stage1.py tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py -k '_ensure_sqlite_email_schema or _ensure_postgres_email_schema or email_schema'`
  - `8 passed, 1 skipped, 214 deselected, 6 warnings`
- `python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db/schema/email_schema_structures.py tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
  - no issues identified
- `python Helper_Scripts/checks/media_db_runtime_ownership_count.py`
  - `188`
- `git diff --check`
  - clean
