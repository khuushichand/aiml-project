# Media DB V2 Media Files Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the repository-backed MediaFiles wrapper cluster onto
package-owned runtime helpers so the canonical `MediaDatabase` no longer owns
`insert_media_file`, `get_media_file`, `get_media_files`,
`has_original_file`, `soft_delete_media_file`, or
`soft_delete_media_files_for_media` through legacy globals, while preserving
the `Media_DB_v2` compat shell and keeping MediaFiles behavior unchanged.

**Architecture:** Add one package runtime helper module for the six MediaFiles
wrapper methods, rebind the canonical class methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods into
live-module compat shells. Use direct ownership/delegation regressions and
focused helper-path forwarding tests in `test_media_files.py`, then verify
against the existing MediaFiles behavior suite and media consumers that mock
`get_media_file(...)`.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase.insert_media_file` is no longer legacy-owned
   - canonical `MediaDatabase.get_media_file` is no longer legacy-owned
   - canonical `MediaDatabase.get_media_files` is no longer legacy-owned
   - canonical `MediaDatabase.has_original_file` is no longer legacy-owned
   - canonical `MediaDatabase.soft_delete_media_file` is no longer legacy-owned
   - canonical `MediaDatabase.soft_delete_media_files_for_media` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'insert_media_file or get_media_file or get_media_files or has_original_file or soft_delete_media_file or soft_delete_media_files_for_media'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/MediaDB2/test_media_files.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `insert_media_file(...)` forwards into
     `MediaFilesRepository.from_legacy_db(...).insert(...)`
   - `get_media_file(...)`, `get_media_files(...)`, and
     `has_original_file(...)` forward into the repository with the expected
     arguments
   - `soft_delete_media_file(...)` and
     `soft_delete_media_files_for_media(...)` forward into the repository
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/MediaDB2/test_media_files.py \
  -k 'forwards_to_repository'
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/media_file_ops.py`

**Steps:**
1. Add package-owned wrappers for the six MediaFiles methods
2. Preserve the current forwarding contract into
   `MediaFilesRepository.from_legacy_db(self)`
3. Re-run the Task 2 helper slice

Expected: PASS

### Task 4: Rebind Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper functions
2. Rebind the six canonical methods
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert Legacy Helpers To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the six legacy methods through `import_module(...)`
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
  tldw_Server_API/tests/MediaDB2/test_media_files.py \
  tldw_Server_API/tests/Media/test_document_outline.py \
  tldw_Server_API/tests/Media/test_media_navigation.py \
  -k 'insert_media_file or get_media_file or get_media_files or has_original_file or soft_delete_media_file or soft_delete_media_files_for_media or forwards_to_repository'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `166`

Actual close-out:
- ownership slice: `12 passed`
- helper slice: `4 passed`
- broader bundle: `28 passed, 222 deselected`
- Bandit on touched production files: no issues
- ownership recount: `172 -> 166`
- `git diff --check`: clean
