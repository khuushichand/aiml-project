# Media DB V2 FTS Maintenance Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the FTS maintenance helper cluster onto a package-owned runtime
module so the canonical `MediaDatabase` no longer owns `_update_fts_media`,
`_delete_fts_media`, `_update_fts_keyword`, `_delete_fts_keyword`, and
`sync_refresh_fts_for_entity` through the legacy module, while preserving the
`Media_DB_v2` compat shell and keeping FTS refresh behavior unchanged.

**Architecture:** Add one package runtime module for the five FTS maintenance
helpers, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods to live-module compat shells. Verify
the SQLite synonym path, SQL routing, and sync dispatch behavior with focused
helper tests, then reuse the existing Postgres-support, API-compat, and sync
tests as the broader guard.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._update_fts_media` is no longer legacy-owned
   - canonical `MediaDatabase._delete_fts_media` is no longer legacy-owned
   - canonical `MediaDatabase._update_fts_keyword` is no longer legacy-owned
   - canonical `MediaDatabase._delete_fts_keyword` is no longer legacy-owned
   - canonical `MediaDatabase.sync_refresh_fts_for_entity` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'update_fts_media or delete_fts_media or update_fts_keyword or delete_fts_keyword or sync_refresh_fts_for_entity'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `_update_fts_media(...)` preserves SQLite synonym expansion and fallback
     behavior
   - `_update_fts_media(...)` routes PostgreSQL updates through
     `_execute_with_connection(...)`
   - `_delete_fts_media(...)` routes PostgreSQL deletes through
     `_execute_with_connection(...)`
   - `_update_fts_keyword(...)` routes PostgreSQL updates through
     `_execute_with_connection(...)`
   - `_delete_fts_keyword(...)` routes PostgreSQL deletes through
     `_execute_with_connection(...)`
   - `sync_refresh_fts_for_entity(...)` dispatches correctly for `Media` and
     `Keywords`
   - `sync_refresh_fts_for_entity(...)` no-ops on update when payload omits the
     relevant fields
   - API-layer lightweight-double coverage for `_delete_fts_keyword` was
     investigated, but the existing
     `test_media_db_api_soft_delete_keyword_accepts_partial_legacy_like_db`
     case is already failing on this branch independent of this tranche
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  -k 'update_fts_media or delete_fts_media or update_fts_keyword or delete_fts_keyword or sync_refresh_fts_for_entity'
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/fts_ops.py`

**Steps:**
1. Create package-owned implementations for:
   - `_update_fts_media(...)`
   - `_delete_fts_media(...)`
   - `_update_fts_keyword(...)`
   - `_delete_fts_keyword(...)`
   - `sync_refresh_fts_for_entity(...)`
2. Preserve:
   - SQLite synonym expansion behavior
   - SQLite fallback behavior when synonym lookup fails
   - PostgreSQL `_execute_with_connection(...)` usage
   - current dispatch rules for `Media` and `Keywords`
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the five canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the five legacy methods through `import_module(...)`
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
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/MediaDB2/test_sync_server.py \
  -k 'update_fts_media or delete_fts_media or update_fts_keyword or delete_fts_keyword or sync_refresh_fts_for_entity or rolls_back_when_fts_refresh_fails'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`
5. Note that `test_media_db_api_soft_delete_keyword_accepts_partial_legacy_like_db`
   remains an unrelated pre-existing branch failure and was not used as a
   tranche gate

Expected ownership count: `195`
