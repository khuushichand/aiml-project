# Media DB V2 TTS History Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the TTS history CRUD/filter cluster onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns those eleven methods
through `Media_DB_v2`, while preserving the legacy compat shell and keeping TTS
history behavior unchanged.

**Architecture:** Add one package runtime helper module for the TTS history
methods, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Use
direct ownership/delegation regressions plus a focused helper-path test file to
pin filter construction, artifact deletion matching, purge ordering, and the
PostgreSQL create return path before rebinding.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical ownership moved off legacy for:
     - `create_tts_history_entry`
     - `_build_tts_history_filters`
     - `list_tts_history`
     - `count_tts_history`
     - `get_tts_history_entry`
     - `update_tts_history_favorite`
     - `soft_delete_tts_history_entry`
     - `mark_tts_history_artifacts_deleted_for_output`
     - `mark_tts_history_artifacts_deleted_for_file_id`
     - `purge_tts_history_for_user`
     - `list_tts_history_user_ids`
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'tts_history'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_tts_history_ops.py`

**Steps:**
1. Add failing unit tests asserting:
   - `_build_tts_history_filters(...)` preserves condition and parameter order
   - `mark_tts_history_artifacts_deleted_for_file_id(...)` matches only rows
     whose parsed `artifact_ids` contain the target `file_id`, ignores malformed
     JSON, and clears matched rows through a single update
   - `purge_tts_history_for_user(...)` runs the retention delete before the
     max-row cap delete and sums removed rows correctly
   - `create_tts_history_entry(...)` returns the PostgreSQL `RETURNING id`
     value when `backend_type` is PostgreSQL
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_tts_history_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/tts_history_ops.py`

**Steps:**
1. Add package-owned implementations for the eleven TTS history methods
2. Preserve:
   - JSON serialization behavior
   - filter ordering and case-insensitive text search behavior
   - malformed artifact JSON tolerance
   - retention-then-cap purge order
   - SQLite/Postgres create return behavior
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the eleven canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the eleven legacy methods through `import_module(...)`
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
  tldw_Server_API/tests/DB_Management/test_media_db_tts_history_ops.py \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_history_endpoints.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_history_artifact_purge.py \
  tldw_Server_API/tests/Services/test_tts_history_cleanup_service.py \
  -k 'tts_history'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `151`

Actual close-out:
- ownership slice: `24 passed, 203 deselected, 6 warnings`
- helper slice: `4 passed, 6 warnings`
- broader TTS tranche bundle: `42 passed, 242 deselected, 6 warnings`
- Bandit on touched production files: no issues
- ownership recount: `162 -> 151`
- `git diff --check`: clean

Notes:
- The original compat-shell delegation regression under-modeled the shell
  contract by expecting only user-supplied kwargs. The final regression now
  derives the exact forwarded kwargs from the legacy method signature, which
  matches the explicit compat-shell behavior and avoids duplicating every
  default parameter in the test table.
