# Media DB V2 Claims Search Read Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `MediaDatabase.search_claims(...)` onto a package-owned runtime
helper while preserving FTS behavior, fallback semantics, scope filtering, and
caller-facing signature compatibility.

**Architecture:** Add a `claims_search_ops.py` runtime helper that owns the
current `search_claims(...)` coordinator body, rebind the canonical
`MediaDatabase` method in `media_database_impl.py`, and convert the legacy
`Media_DB_v2.search_claims(...)` method into a live-module compat shell. Keep
the remaining claims write helpers out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing canonical regression asserting
   `MediaDatabase.search_claims.__globals__["__name__"]` no longer points at
   `Media_DB_v2`.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2.search_claims(...)` method delegates through
   `claims_search_ops.py` via a live `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_search_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'search_claims'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_search_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Seed a real SQLite DB and add focused helper tests covering:
   - empty-query early return
   - invalid-limit normalization
   - SQLite FTS success path
   - `fallback_to_like=False` suppressing fallback
   - `fallback_to_like=True` returning `LIKE` fallback rows
   - non-admin scope exclusion
3. Add a backend-stub helper test covering the PostgreSQL branch:
   - `FTSQueryTranslator.normalize_query(...)` result used for `to_tsquery`
   - normalized tsquery passed twice to the FTS query
   - `ILIKE` fallback used when FTS returns no rows
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_search_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_search_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_search_ops.py`

**Steps:**
1. Move the `search_claims(...)` body into the new runtime module.
2. Preserve:
   - query trimming and empty-query early return
   - limit normalization
   - SQLite FTS rebuild and MATCH path
   - PostgreSQL tsquery path
   - visibility and owner filters
   - optional `LIKE` / `ILIKE` fallback
3. Re-run the Task 2 helper slice.

Expected: helper slice still red only for canonical binding

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `search_claims` from `claims_search_ops.py`.
2. Rebind canonical `MediaDatabase.search_claims`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy `search_claims(...)` body with a live-module compat shell
   delegating through `import_module(...)`.
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
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_search_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_search_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_cluster_links_and_search.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG/test_claims_retriever.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/RAG/test_dual_backend_end_to_end.py \
  -k 'search_claims or claims_search or retriever or cluster_links'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `26`

---

## Outcome

- Added package runtime helper:
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_search_ops.py`
- Rebound canonical `MediaDatabase.search_claims(...)` in
  `media_database_impl.py`
- Converted legacy `Media_DB_v2.search_claims(...)` into a live-module compat
  shell
- Added ownership/delegation regressions in
  `test_media_db_v2_regressions.py`
- Added focused helper-path coverage in
  `test_media_db_claims_search_ops.py`

## Verification

- Focused ownership slice:
  - `2 passed, 477 deselected, 6 warnings`
- Focused helper slice:
  - `3 passed, 6 warnings`
- Tranche pytest bundle:
  - `9 passed, 481 deselected, 6 warnings`
- Bandit on touched production files:
  - `0 results, 0 errors`
- Normalized ownership count:
  - `27 -> 26`
- `git diff --check`:
  - `clean`
