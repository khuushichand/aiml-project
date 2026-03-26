# Media DB V2 FTS Schema Helper Rebinding Implementation Plan

**Goal:** Rebind `_ensure_fts_structures()`, `_ensure_sqlite_fts()`, and
`_ensure_postgres_fts()` onto a package-owned schema helper module so the
canonical `MediaDatabase` no longer owns that FTS schema cluster through
`Media_DB_v2`, while preserving the legacy compat shell and retargeting
`schema/features/fts.py` away from legacy-owned methods.

**Architecture:** Add one package schema helper module for the FTS schema
cluster, update `schema/features/fts.py` to call it directly, rebind the
canonical methods in `media_database_impl.py`, and convert the legacy methods
in `Media_DB_v2.py` into live-module compat shells. Verify with direct
ownership regressions, focused helper-path tests, and the existing SQLite
bootstrap and claims FTS integration tests.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._ensure_fts_structures` is no longer legacy-owned
   - canonical `MediaDatabase._ensure_sqlite_fts` is no longer legacy-owned
   - canonical `MediaDatabase._ensure_postgres_fts` is no longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_ensure_fts_structures or _ensure_sqlite_fts or _ensure_postgres_fts'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `ensure_fts_structures(...)` dispatches correctly by backend
   - `ensure_sqlite_fts(...)` runs both scripts, verifies required tables, and
     commits in `finally`
   - `ensure_sqlite_fts(...)` raises `DatabaseError` when `media_fts` or
     `keyword_fts` are missing after bootstrap
   - `ensure_postgres_fts(...)` creates the three core FTS tables in order and
     tolerates chunk FTS creation failure
   - `schema/features/fts.py` routes through the package helpers rather than
     legacy DB methods
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'fts_structures or ensure_sqlite_fts or ensure_postgres_fts'
```

Expected: FAIL

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/fts_structures.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/features/fts.py`

**Steps:**
1. Create package-owned implementations for:
   - `ensure_fts_structures(...)`
   - `ensure_sqlite_fts(...)`
   - `ensure_postgres_fts(...)`
2. Retarget `schema/features/fts.py` to the new package helpers
3. Preserve the existing dispatch, verification, commit, and warning behavior
4. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
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
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_claims_schema.py \
  tldw_Server_API/tests/DB_Management/test_claims_fts_triggers.py \
  -k '_ensure_fts_structures or _ensure_sqlite_fts or _ensure_postgres_fts or claims_fts'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `190`
