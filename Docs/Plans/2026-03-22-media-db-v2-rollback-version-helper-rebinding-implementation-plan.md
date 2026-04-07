# Media DB V2 Rollback Version Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the final canonical legacy-owned method,
`rollback_to_version(...)`, onto a package-owned runtime helper without
changing the rollback dict/exception contract or caller-facing behavior.

**Architecture:** Move the rollback transaction body into a package-owned
runtime helper module, rebind canonical `MediaDatabase.rollback_to_version` in
`media_database_impl.py`, and convert the legacy method in `Media_DB_v2.py`
into a live-module compat shell. Keep API and DB-manager callers unchanged.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add a failing canonical regression asserting
   `MediaDatabase.rollback_to_version(...)` no longer resolves globals from
   `Media_DB_v2`.
2. Add a failing compat-shell regression proving the legacy method delegates
   through `runtime/document_version_rollback_ops.py` via live
   `import_module(...)`.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_rollback_version python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'rollback_to_version'
```

Observed:
- Added canonical and legacy delegation regressions in
  `test_media_db_v2_regressions.py`.
- Initial red slice failed as expected before implementation:
  `6 failed, 527 deselected, 6 warnings`

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_document_version_rollback_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to
   `runtime/document_version_rollback_ops.py`.
2. Add focused rollback tests covering:
   - missing rollback target returns `{"error": ...}`
   - rollback to latest returns `{"error": ...}`
   - success result includes the expected payload fields
   - post-transaction hook failures remain non-blocking
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_rollback_version python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_document_version_rollback_ops.py
```

Observed:
- Added focused helper coverage in
  `test_media_db_document_version_rollback_ops.py`.
- Initial helper-path slice failed as expected before implementation as part of
  the combined red run:
  `6 failed, 527 deselected, 6 warnings`

### Task 3: Add The Package-Owned Rollback Helper

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/document_version_rollback_ops.py`

**Steps:**
1. Move the full rollback transaction body into
   `rollback_to_version(...)`.
2. Preserve:
   - semantic error dict returns
   - raised-exception behavior
   - sync payload enrichment
   - FTS refresh
   - best-effort collections/vector invalidation hooks

Observed:
- Added package-owned helper module
  `runtime/document_version_rollback_ops.py`.
- Preserved the rollback dict/exception contract, sync payload enrichment,
  post-commit FTS refresh, and best-effort non-blocking hook behavior.

### Task 4: Rebind The Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import `rollback_to_version(...)` from the new runtime helper.
2. Rebind canonical `MediaDatabase.rollback_to_version`.
3. Re-run the Task 1 regression slice.

Observed:
- Canonical `MediaDatabase.rollback_to_version(...)` now rebinds to the runtime
  helper module in `media_database_impl.py`.
- Canonical ownership assertion passed after rebinding; legacy compat-shell
  delegation remained pending until Task 5.

### Task 5: Convert The Legacy Method To A Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy `rollback_to_version(...)` body with a live-module compat
   shell using `import_module(...)`.
2. Preserve the method signature exactly.
3. Re-run the Task 1 regression slice and the Task 2 helper slice.

Observed:
- Legacy `Media_DB_v2.rollback_to_version(...)` now delegates through a live
  `import_module(...)` compat shell.
- Focused regression and helper slices passed after the compat-shell cut:
  `6 passed, 527 deselected, 6 warnings`

### Task 6: Verify The Final Ownership Cut

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_rollback_version python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_document_version_rollback_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
  -k 'rollback_to_version'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Observed:
1. The caller-facing rollback bundle passed:

```bash
9 passed, 614 deselected, 5 warnings
```

2. Bandit on touched production files returned:

```bash
results: 0
errors: 0
```

3. Ownership recount returned:

```bash
0
```

4. `git diff --check` was clean.

Expected ownership count: `0`
