# Media DB V2 Chunk FTS Helper Rebinding Implementation Plan

**Goal:** Rebind `ensure_chunk_fts()` and
`maybe_rebuild_chunk_fts_if_empty()` onto a package-owned runtime module so the
canonical `MediaDatabase` no longer owns the chunk-FTS helper pair through
`Media_DB_v2`, while preserving the legacy compat shell and keeping chunk FTS
bootstrap behavior unchanged.

**Architecture:** Add one runtime helper module for the chunk-FTS pair, rebind
the canonical class in `media_database_impl.py`, and convert the legacy
methods in `Media_DB_v2.py` into live-module compat shells. Verify with direct
ownership regressions, focused helper-path tests, and the existing chunk FTS
integration test.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `MediaDatabase.ensure_chunk_fts` is no longer legacy-owned
   - canonical `MediaDatabase.maybe_rebuild_chunk_fts_if_empty` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase` methods delegate through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'ensure_chunk_fts or maybe_rebuild_chunk_fts_if_empty'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - `ensure_chunk_fts()` creates the virtual table and rebuilds only when the
     table is new
   - `maybe_rebuild_chunk_fts_if_empty()` creates the table on missing, then
     rebuilds when empty
   - `maybe_rebuild_chunk_fts_if_empty()` skips rebuild when the count is
     already nonzero
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'chunk_fts'
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_fts_ops.py`

**Steps:**
1. Create package-owned implementations for:
   - `ensure_chunk_fts(...)`
   - `maybe_rebuild_chunk_fts_if_empty(...)`
2. Preserve:
   - SQLite-only no-op behavior
   - create-if-missing and rebuild-if-empty behavior
   - debug-log swallowing of noncritical exceptions
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
  tldw_Server_API/tests/RAG_NEW/unit/test_chunk_fts_integration.py \
  -k 'ensure_chunk_fts or maybe_rebuild_chunk_fts_if_empty or chunk_fts'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Expected ownership count: `193`
