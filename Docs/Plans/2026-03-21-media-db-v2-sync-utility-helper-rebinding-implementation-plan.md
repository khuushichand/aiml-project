# Media DB V2 Sync Utility Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_generate_uuid`, `_get_current_utc_timestamp_str`,
`_get_next_version`, and `_log_sync_event` onto package-owned runtime helpers
so the canonical `MediaDatabase` no longer owns that shared sync/version
utility cluster through the legacy module, while preserving the `Media_DB_v2`
compat shell and keeping all timestamp/version/sync-log behavior unchanged.

**Architecture:** Add one package runtime helper module for the four utility
methods, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Use
direct ownership/delegation regressions plus a focused helper-path test file to
pin UUID, timestamp, version-lookup, and sync-log behavior before rebinding.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._generate_uuid` is no longer legacy-owned
   - canonical `MediaDatabase._get_current_utc_timestamp_str` is no longer
     legacy-owned
   - canonical `MediaDatabase._get_next_version` is no longer legacy-owned
   - canonical `MediaDatabase._log_sync_event` is no longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_generate_uuid or _get_current_utc_timestamp_str or _get_next_version or _log_sync_event'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_sync_utils.py`

**Steps:**
1. Add failing unit tests asserting:
   - `_generate_uuid(...)` returns a string UUID4
   - `_get_current_utc_timestamp_str(...)` emits millisecond UTC strings ending
     in `Z`
   - `_get_next_version(...)` returns `(current, next)` for active rows,
     returns `None` for deleted rows and non-integer versions, and raises
     `DatabaseError` for unsafe identifiers
   - `_log_sync_event(...)` strips `vector_embedding`, normalizes datetimes,
     no-ops on missing entity/uuid/operation, and preserves SQLite vs Postgres
     write routing
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_sync_utils.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/sync_utility_ops.py`

**Steps:**
1. Add package-owned helpers for the four methods
2. Preserve current timestamp format, UUID version, identifier validation,
   deleted-row filtering, payload pruning, datetime normalization, and backend
   routing behavior
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the four canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the four legacy methods through `import_module(...)`
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
  tldw_Server_API/tests/DB_Management/test_media_db_sync_utils.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  -k '_generate_uuid or _get_current_utc_timestamp_str or _get_next_version or _log_sync_event or sync_utils'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `175`

Actual close-out:
- ownership slice: `8 passed`
- helper slice: `9 passed`
- caller-facing guard slice: `6 passed`
- broader bundle with regressions + helper-path tests: `16 passed, 178 deselected`
- Bandit on touched production files: no issues
- ownership recount: `179 -> 175`
- `git diff --check`: clean

Notes:
- `test_media_db_api_soft_delete_keyword_accepts_partial_legacy_like_db` remains
  a pre-existing branch failure in `media_db_api.soft_delete_keyword(...)` and
  was not used as the tranche gate.
- The API compatibility guard for this tranche used
  `test_media_db_api_get_media_transcripts_unwraps_wrapped_db` instead, because
  it still exercises the structural Media DB protocol that requires
  `_get_current_utc_timestamp_str(...)` and `_log_sync_event(...)`.
