# Media DB V2 Keyword Access Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the remaining keyword-access helpers onto a package-owned
runtime module while preserving repository forwarding for `add_keyword(...)`
and grouped keyword-to-media lookup behavior for `fetch_media_for_keywords(...)`.

**Architecture:** Add a `keyword_access_ops.py` runtime helper owning the two
in-scope methods, rebind the canonical `MediaDatabase` methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods into
live-module compat shells. Keep keyword-link mutation, safe-metadata search,
rollback, and bootstrap/postgres coordinators out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting `MediaDatabase.add_keyword` and
   `MediaDatabase.fetch_media_for_keywords` no longer resolve their globals
   from `Media_DB_v2`.
2. Add failing compat-shell delegation regressions proving the legacy
   `Media_DB_v2` methods delegate through `keyword_access_ops.py` via live
   `import_module(...)` references.
3. Use `inspect.signature(...)`-derived forwarding expectations so defaults are
   not hard-coded incorrectly.
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_keyword_access python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'add_keyword or fetch_media_for_keywords'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_keyword_access_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Add a focused `add_keyword(...)` helper test proving the helper forwards to
   `KeywordsRepository.from_legacy_db(self).add(...)` with exact `keyword` and
   `conn` forwarding.
3. Add focused `fetch_media_for_keywords(...)` helper tests covering:
   - `TypeError` for non-list input
   - `{}` for empty or all-blank inputs
   - lowercase/strip/deduplicate normalization
   - trash filtering controlled by `include_trash`
   - grouped media-item shaping
   - unexpected keyword fallback behavior
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_keyword_access python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_keyword_access_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/keyword_access_ops.py`

**Steps:**
1. Move `fetch_media_for_keywords(...)` into the new runtime module.
2. Add the package-owned `add_keyword(...)` wrapper preserving the repository
   seam.
3. Preserve:
   - input validation and empty-input fast returns
   - normalization and deduplication
   - `include_trash` filtering
   - grouped keyword/media shaping
   - fallback grouping for unexpected DB keywords
4. Re-run the Task 2 helper slice.

Expected: helper slice still red only for canonical binding

### Task 4: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the two helpers from `keyword_access_ops.py`.
2. Rebind canonical `MediaDatabase.add_keyword` and
   `MediaDatabase.fetch_media_for_keywords`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

### Task 5: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the two legacy method bodies with live-module compat shells
   delegating through `import_module(...)`.
2. Preserve the public signatures exactly.
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
PYTHONPYCACHEPREFIX=/tmp/pycache_keyword_access python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_keyword_access_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/VectorStores/test_vector_stores_keyword_match.py \
  -k 'add_keyword or fetch_media_for_keywords or keyword_match'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `20`

**Verification Results**:
- Focused ownership slice: `4 passed, 487 deselected, 6 warnings`
- Focused helper slice: `6 passed, 6 warnings`
- Tranche pytest bundle: `12 passed, 529 deselected, 6 warnings`
- Bandit on touched production files: `0` results, `0` errors
- Ownership count: `20`
- `git diff --check`: clean
