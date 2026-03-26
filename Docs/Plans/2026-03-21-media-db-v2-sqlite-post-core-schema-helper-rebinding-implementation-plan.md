# Media DB V2 SQLite Post-Core Schema Helper Rebinding Implementation Plan

**Goal:** Rebind `_ensure_sqlite_visibility_columns()`,
`_ensure_sqlite_source_hash_column()`, and `_ensure_sqlite_data_tables()` onto
a package-owned schema helper module so the canonical `MediaDatabase` no longer
owns that small SQLite post-core schema trio through `Media_DB_v2`, while
preserving the legacy compat shell and keeping behavior unchanged.

**Architecture:** Add one package schema helper module for the three SQLite
schema ensures, rebind the canonical methods in `media_database_impl.py`, and
convert the legacy methods in `Media_DB_v2.py` into live-module compat shells.
Verify with direct ownership regressions, focused helper-path tests, and the
existing SQLite post-core bootstrap ordering guard.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `_ensure_sqlite_visibility_columns` is no longer legacy-owned
   - canonical `_ensure_sqlite_source_hash_column` is no longer legacy-owned
   - canonical `_ensure_sqlite_data_tables` is no longer legacy-owned
   - legacy methods delegate through a package helper module
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_ensure_sqlite_visibility_columns or _ensure_sqlite_source_hash_column or _ensure_sqlite_data_tables'
```

Outcome: PASS after canonical rebinding and compat-shell conversion

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - visibility helper emits the expected SQLite statements when artifacts are
     missing and no-ops when present
   - source-hash helper emits the expected SQLite statements when artifacts are
     missing and no-ops when present
   - data-tables helper runs `_DATA_TABLES_SQL` and tolerates SQLite errors
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'sqlite_visibility_columns or sqlite_source_hash_column or sqlite_data_tables'
```

Outcome: PASS after package helper module creation

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/sqlite_post_core_structures.py`

**Steps:**
1. Create package-owned implementations for:
   - `ensure_sqlite_visibility_columns(...)`
   - `ensure_sqlite_source_hash_column(...)`
   - `ensure_sqlite_data_tables(...)`
2. Preserve the existing introspection, missing-artifact gating, no-op, and
   warning-only behavior
3. Re-run the Task 2 helper slice

Outcome: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the three canonical methods
3. Re-run the Task 1 regression slice

Outcome: canonical ownership assertions passed

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the three legacy methods through `import_module(...)`
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
  -k '_ensure_sqlite_visibility_columns or _ensure_sqlite_source_hash_column or _ensure_sqlite_data_tables or sqlite_visibility_columns or sqlite_source_hash_column or sqlite_data_tables'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Verification:
- `python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py -k '_ensure_sqlite_visibility_columns or _ensure_sqlite_source_hash_column or _ensure_sqlite_data_tables or sqlite_visibility_columns or sqlite_source_hash_column or sqlite_data_tables or ensure_sqlite_post_core_structures_runs_followup_ensures'`
  - `10 passed, 197 deselected, 6 warnings`
- `python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db/schema/sqlite_post_core_structures.py tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
  - no issues identified
- `python Helper_Scripts/checks/media_db_runtime_ownership_count.py`
  - `185`
- `git diff --check`
  - clean
