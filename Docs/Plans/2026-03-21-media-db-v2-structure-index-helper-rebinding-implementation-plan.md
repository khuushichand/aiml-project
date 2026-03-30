# Media DB V2 Structure Index Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `_write_structure_index_records`,
`write_document_structure_index`, and
`delete_document_structure_for_media` onto package-owned runtime helpers so
the canonical `MediaDatabase` no longer owns that DocumentStructureIndex write
cluster through legacy globals, while preserving the `Media_DB_v2` compat
shell and keeping structure-index behavior unchanged.

**Architecture:** Add one package runtime helper module for the three
structure-index write helpers, rebind the canonical class methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods into
live-module compat shells. Use direct ownership/delegation regressions plus
focused helper-path tests for clear-then-insert order, invalid-row skipping,
public transaction wrapping, and delete rowcount behavior before rebinding,
then verify against the existing structure-index integration tests.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase._write_structure_index_records` is no longer
     legacy-owned
   - canonical `MediaDatabase.write_document_structure_index` is no longer
     legacy-owned
   - canonical `MediaDatabase.delete_document_structure_for_media` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_write_structure_index_records or write_document_structure_index or delete_document_structure_for_media'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_structure_index_ops.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `_write_structure_index_records(...)` clears old rows before inserting new
     ones
   - invalid records are skipped while valid records still insert
   - `write_document_structure_index(...)` rejects falsey `media_id` and wraps
     the internal helper with `transaction()`
   - `delete_document_structure_for_media(...)` returns `rowcount` and returns
     `0` for falsey `media_id`
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_structure_index_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/structure_index_ops.py`

**Steps:**
1. Add package-owned helpers for the three structure-index write methods
2. Preserve current:
   - clear-then-insert order
   - invalid-row skip semantics
   - timestamp generation and client-id propagation
   - SQLite vs Postgres deleted-flag encoding
   - public validation and transaction behavior
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
  tldw_Server_API/tests/DB_Management/test_media_db_structure_index_ops.py \
  tldw_Server_API/tests/RAG_NEW/unit/test_structure_index.py \
  tldw_Server_API/tests/Media/test_media_navigation.py \
  -k '_write_structure_index_records or write_document_structure_index or delete_document_structure_for_media or structure_index_ops or DocumentStructureIndex'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `145`

Actual close-out:
- regression slice: `6 passed, 233 deselected, 6 warnings`
- helper slice: `4 passed, 6 warnings`
- broader filtered tranche bundle: `10 passed, 251 deselected, 9 warnings`
- caller-facing guards:
  - `test_structure_index.py`: `4 passed, 6 warnings`
  - `test_media_navigation.py`: `14 passed, 9 warnings`
- Bandit on touched production files: no issues
- ownership recount: `148 -> 145`
- `git diff --check`: clean
