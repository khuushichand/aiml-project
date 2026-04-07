# Media DB V2 Claims List Read Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind `MediaDatabase.list_claims(...)` onto a package-owned runtime
helper while preserving filter composition, scope visibility, deleted-row
handling, pagination normalization, and caller-facing signature compatibility.

**Architecture:** Add a `claims_list_ops.py` runtime helper that owns the
current `list_claims(...)` coordinator body, rebind the canonical
`MediaDatabase` method in `media_database_impl.py`, and convert the legacy
`Media_DB_v2.list_claims(...)` method into a live-module compat shell. Keep the
remaining claims CRUD/search methods out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing canonical regression asserting
   `MediaDatabase.list_claims.__globals__["__name__"]` no longer points at
   `Media_DB_v2`.
2. Add a failing compat-shell delegation regression proving the legacy
   `Media_DB_v2.list_claims(...)` method delegates through
   `claims_list_ops.py` via a live `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_list_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'list_claims'
```

Expected: FAIL

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_claims_list_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to the package
   helper module.
2. Seed a real SQLite DB and add focused helper tests covering:
   - invalid pagination fallback / clamping
   - deleted-row handling
   - stable ordering by `media_id`, `chunk_index`, `id`
   - `owner_user_id` filtering
   - `review_status`, `reviewer_id`, `review_group`, and `claim_cluster_id`
     filtering
   - non-admin scope exclusion via monkeypatched `get_scope()`
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_list_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_list_ops.py
```

Expected: FAIL

### Task 3: Add Package Runtime Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_list_ops.py`

**Steps:**
1. Move the `list_claims(...)` body into the new runtime module.
2. Preserve:
   - `limit` / `offset` coercion and clamping
   - optional SQL filter composition
   - non-admin visibility filtering through `get_scope()`
   - ordering by `media_id`, `chunk_index`, `id`
3. Re-run the Task 2 helper slice.

Expected: helper slice still red only for canonical binding

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `list_claims` from `claims_list_ops.py`.
2. Rebind canonical `MediaDatabase.list_claims`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertion passes, compat-shell delegation still red

### Task 5: Convert The Legacy Method To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy `list_claims(...)` body with a live-module compat shell
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
PYTHONPYCACHEPREFIX=/tmp/pycache_claims_list_read python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_claims_list_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_items_api.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Claims/test_claims_clustering_embeddings.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Workflows/adapters/test_knowledge_adapters.py \
  -k 'list_claims or claims_list or claims_extract_adapter_list or clustering'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `27`

---

## Outcome

- Added package runtime helper:
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_list_ops.py`
- Rebound canonical `MediaDatabase.list_claims(...)` in
  `media_database_impl.py`
- Converted legacy `Media_DB_v2.list_claims(...)` into a live-module compat
  shell
- Added ownership/delegation regressions in
  `test_media_db_v2_regressions.py`
- Added focused helper-path coverage in
  `test_media_db_claims_list_ops.py`

## Verification

- Focused ownership slice:
  - `16 passed, 461 deselected, 6 warnings`
- Focused helper slice:
  - `2 passed, 6 warnings`
- Tranche pytest bundle:
  - `23 passed, 529 deselected, 6 warnings`
- Bandit on touched production files:
  - `0` results, `0` errors
- Normalized ownership count:
  - `28 -> 27`
- `git diff --check`:
  - clean
