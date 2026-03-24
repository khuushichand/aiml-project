# Media DB V2 Visual Documents Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the VisualDocuments helper trio onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns
`insert_visual_document`, `list_visual_documents_for_media`, or
`soft_delete_visual_documents_for_media` through legacy globals, while
preserving the `Media_DB_v2` compat shell and keeping VisualDocuments behavior
unchanged.

**Architecture:** Add one package runtime helper module for the three
VisualDocuments methods, rebind the canonical class methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods into
live-module compat shells. Use direct ownership/delegation regressions and
focused helper-path tests in `test_media_db_visual_documents.py`, then verify
against the existing VisualDocuments behavior and visual-ingestion tests.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase.insert_visual_document` is no longer
     legacy-owned
   - canonical `MediaDatabase.list_visual_documents_for_media` is no longer
     legacy-owned
   - canonical `MediaDatabase.soft_delete_visual_documents_for_media` is no
     longer legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'insert_visual_document or list_visual_documents_for_media or soft_delete_visual_documents_for_media'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_visual_documents.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `insert_visual_document(...)` delegates to `_execute_with_connection(...)`
     and `_log_sync_event(...)`
   - `list_visual_documents_for_media(...)` delegates to
     `_fetchall_with_connection(...)` with the expected query and parameters
   - `soft_delete_visual_documents_for_media(...)` covers both the soft-delete
     and hard-delete helper paths
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_visual_documents.py \
  -k 'helper_path'
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/visual_document_ops.py`

**Steps:**
1. Add package-owned helpers for the three VisualDocuments methods
2. Preserve current UUID generation, deleted-row filtering, ordering, sync-log
   payloads, and hard/soft delete behavior
3. Re-run the Task 2 helper slice

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
  tldw_Server_API/tests/DB_Management/test_media_db_visual_documents.py \
  tldw_Server_API/tests/MediaIngestion_NEW/unit/test_visual_ingestion.py \
  -k 'insert_visual_document or list_visual_documents_for_media or soft_delete_visual_documents_for_media or helper_path or visual_documents'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `163`

Actual close-out:
- ownership slice: `6 passed`
- helper slice: `3 passed`
- broader bundle: `11 passed, 197 deselected`
- Bandit on touched production files: no issues
- ownership recount: `166 -> 163`
- `git diff --check`: clean
