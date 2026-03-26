# Media DB V2 Synced Document Update Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `apply_synced_document_content_update(...)` onto a package-owned
runtime helper while preserving media-row updates, document-version creation,
sync logging, FTS refresh, and post-commit best-effort hooks.

**Architecture:** Add a `synced_document_update_ops.py` runtime helper for the
single in-scope coordinator, rebind the canonical `MediaDatabase` method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method into a
live-module compat shell. Keep rollback, safe-metadata search, and bootstrap
coordinators out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing canonical regression asserting
   `MediaDatabase.apply_synced_document_content_update(...)` no longer resolves
   globals from `Media_DB_v2`.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2.apply_synced_document_content_update(...)` delegates through
   `synced_document_update_ops.py` via a live `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_synced_document_update python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'apply_synced_document_content_update'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_synced_document_update_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Add focused helper tests covering:
   - missing content rejection
   - not-found rejection
   - optimistic conflict rejection
   - transactional ordering across media update, document version creation,
     sync log, and FTS refresh
   - post-commit collections/vector hooks remaining best-effort
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_synced_document_update python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_synced_document_update_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/synced_document_update_ops.py`

**Steps:**
1. Move the `apply_synced_document_content_update(...)` body into the new
   runtime module.
2. Replace legacy `_CollectionsDB` usage with the package loader from
   `media_db/runtime/collections.py`.
3. Preserve:
   - validation and optimistic conflict semantics
   - media-row update payload and return payload
   - document-version creation before sync logging / FTS refresh
   - post-commit best-effort highlight/vector hooks
   - existing exception wrapping behavior
4. Re-run the Task 2 helper slice.

Expected: helper slice still red only for canonical binding

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `apply_synced_document_content_update(...)` from
   `synced_document_update_ops.py`.
2. Rebind canonical `MediaDatabase.apply_synced_document_content_update`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy method body with a live-module compat shell delegating
   through `import_module(...)`.
2. Preserve the public signature exactly.
3. Re-run the Task 1 regression slice.

Expected: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_synced_document_update python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_synced_document_update_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_sync_coordinator.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Ingestion_Sources/test_media_sink.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_connectors_worker_file_sync.py \
  -k 'apply_synced_document_content_update or version_created or sync'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `18`

**Verification Results**:
- Focused ownership slice: `2 passed, 493 deselected, 6 warnings`
- Focused helper slice: `7 passed, 6 warnings`
- Tranche pytest bundle: `43 passed, 471 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Normalized ownership count: `19 -> 18`
- `git diff --check`: clean
