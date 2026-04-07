# Media DB V2 Postgres TTS/Source-Hash Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_ensure_postgres_tts_history` and
`_ensure_postgres_source_hash_column` onto package-owned schema helpers so the
canonical `MediaDatabase` no longer owns that small PostgreSQL post-core
ensure pair through the legacy module, while preserving the `Media_DB_v2`
compat shell and keeping the emitted SQL order unchanged.

**Architecture:** Add one package schema helper module for the TTS-history and
source-hash ensure pair, rebind the canonical class methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods into
live-module compat shells. Verify emitted SQL order with focused helper tests
and reuse existing `v16` and `v20` helper-path coverage as the broader guard.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._ensure_postgres_tts_history` is no longer
     legacy-owned
   - canonical `MediaDatabase._ensure_postgres_source_hash_column` is no
     longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_ensure_postgres_tts_history or _ensure_postgres_source_hash_column'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing unit tests asserting:
   - `_ensure_postgres_tts_history(...)` emits the table statement first and
     then the expected six indexes
   - `_ensure_postgres_source_hash_column(...)` emits the column add before the
     index creation
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'postgres_tts_source_hash_structures'
```

Expected: FAIL

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/postgres_tts_source_hash_structures.py`

**Steps:**
1. Add package-owned helpers for the two methods
2. Preserve existing emitted SQL order and warning-only behavior
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the two canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the two legacy methods through `import_module(...)`
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
  -k '_ensure_postgres_tts_history or _ensure_postgres_source_hash_column or postgres_tts_source_hash_structures or run_postgres_migrate_to_v16 or run_postgres_migrate_to_v20'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `179`

Actual close-out:
- ownership slice: `4 passed`
- helper slice: `2 passed`
- broader bundle: `8 passed, 218 deselected, 6 warnings`
- Bandit on touched production files: no issues
- ownership recount: `181 -> 179`
- `git diff --check`: clean
