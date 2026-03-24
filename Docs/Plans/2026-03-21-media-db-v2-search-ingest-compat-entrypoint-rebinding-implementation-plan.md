# Media DB V2 Search And Ingest Compat Entrypoint Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `search_media_db(...)` and `add_media_with_keywords(...)`
onto package-owned runtime helpers so the canonical `MediaDatabase` no longer
owns those pure compat entrypoints through legacy globals, while preserving the
existing package API and repository seams.

**Architecture:** Add one small runtime helper module for the two compat
entrypoints, rebind the canonical class methods in `media_database_impl.py`,
and convert the legacy `Media_DB_v2` methods into live-module compat shells.
Lock the seams first with ownership/delegation regressions and focused helper
tests that prove `search_media_db(...)` still routes through `media_db.api`
and `add_media_with_keywords(...)` still routes through `MediaRepository`.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `search_media_db(...)` is no longer legacy-owned
   - canonical `add_media_with_keywords(...)` is no longer legacy-owned
   - legacy `Media_DB_v2.search_media_db(...)` delegates through a package
     helper module
   - legacy `Media_DB_v2.add_media_with_keywords(...)` delegates through a
     package helper module
2. For the `add_media_with_keywords(...)` compat-shell regression, derive the
   expected forwarded kwargs from the method signature so the test pins the full
   surface instead of a hand-picked subset.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'search_media_db or add_media_with_keywords'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_entrypoint_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `run_search_media_db(...)` calls `media_db.api.search_media(...)` with the
     exact forwarded kwargs payload
   - `run_add_media_with_keywords(...)` calls
     `MediaRepository.from_legacy_db(db).add_media_with_keywords(...)` with the
     full forwarded kwargs payload
2. Keep the helper tests narrow: prove the two compat seams only, not the
   repository/search implementation internals.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_entrypoint_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/media_entrypoint_ops.py`

**Steps:**
1. Add `run_search_media_db(...)` that delegates only to
   `tldw_Server_API.app.core.DB_Management.media_db.api.search_media(...)`
2. Add `run_add_media_with_keywords(...)` that delegates only to
   `MediaRepository.from_legacy_db(db).add_media_with_keywords(...)`
3. Do not change `media_db/api.py` or `media_db/runtime/validation.py`
4. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind canonical `search_media_db(...)`
3. Rebind canonical `add_media_with_keywords(...)`
4. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate legacy `search_media_db(...)` through `import_module(...)`
2. Delegate legacy `add_media_with_keywords(...)` through `import_module(...)`
3. Keep both legacy methods present as compat shells
4. Re-run the Task 1 regression slice

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
  tldw_Server_API/tests/DB_Management/test_media_db_entrypoint_ops.py \
  tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py \
  tldw_Server_API/tests/MediaDB2/test_sync_server.py \
  tldw_Server_API/tests/Services/test_connectors_worker.py \
  tldw_Server_API/tests/Services/test_document_processing_service.py \
  tldw_Server_API/tests/Services/test_outputs_service.py \
  -k 'search_media_db or add_media_with_keywords or search_media_contract or media_repository'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `114`
