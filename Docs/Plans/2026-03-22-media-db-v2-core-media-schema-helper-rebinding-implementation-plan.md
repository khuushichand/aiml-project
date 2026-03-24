# Media DB V2 Core Media Schema Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the schema-v1 SQLite/PostgreSQL core apply pair onto the
package-owned `core_media` helper module while preserving validation, ordering,
and schema-version behavior.

**Architecture:** Move the real SQLite and PostgreSQL schema-v1 apply bodies
into `media_db/schema/features/core_media.py`, rebind the canonical
`MediaDatabase` methods in `media_database_impl.py`, and convert the legacy
`Media_DB_v2` methods into live-module compat shells. Keep constructor/init,
SQLite-backend, and rollback behavior out of scope.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting:
   - `MediaDatabase._apply_schema_v1_sqlite(...)`
   - `MediaDatabase._apply_schema_v1_postgres(...)`
   no longer resolve globals from `Media_DB_v2`.
2. Add failing compat-shell delegation regressions proving the legacy methods
   delegate through `schema/features/core_media.py` via a live
   `import_module(...)` reference.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_core_media_schema python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_apply_schema_v1_sqlite or _apply_schema_v1_postgres'
```

Expected: FAIL

Result: PASS. Added the four ownership/delegation regressions and confirmed the
red phase before implementation (`4 failed, 517 deselected, 6 warnings`).

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_core_media_schema_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to
   `schema/features/core_media.py`.
2. Add focused SQLite helper tests covering:
   - email ensure runs after schema script
   - Media validation failure raises
   - FTS failure stays warning-only
3. Add focused PostgreSQL helper tests covering:
   - create-table-first ordering
   - must-table validation
   - email ensure and schema-version normalization
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_core_media_schema python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_core_media_schema_ops.py
```

Expected: FAIL

Result: PASS. Added the focused helper-path file, confirmed the red phase, then
tightened the PostgreSQL missing-table negative-path assertion during review.
Final helper slice result after implementation: `6 passed, 6 warnings`.

### Task 3: Move Core Schema Apply Bodies Into The Package Helper

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/features/core_media.py`

**Steps:**
1. Replace the current thin helper bodies with the real SQLite and PostgreSQL
   schema-v1 apply logic.
2. Preserve the existing helper names:
   - `apply_sqlite_core_media_schema(...)`
   - `apply_postgres_core_media_schema(...)`
3. Preserve:
   - SQLite validation + version checks
   - SQLite warning-only FTS failure behavior
   - PostgreSQL create-table-first ordering
   - PostgreSQL must-table validation
   - PostgreSQL email ensure and schema-version normalization
4. Re-run the Task 2 helper slice.

Expected: helper slice still red only for canonical binding

Result: PASS. `core_media.py` now owns the real SQLite/PostgreSQL schema-v1
apply logic, including SQLite validation/version checks, warning-only FTS
ensure behavior, and PostgreSQL create-table-first ordering with must-table
validation.

### Task 4: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the `core_media` helper functions from
   `schema/features/core_media.py`.
2. Rebind canonical `MediaDatabase._apply_schema_v1_sqlite` and
   `MediaDatabase._apply_schema_v1_postgres`.
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase._apply_schema_v1_sqlite` and
`MediaDatabase._apply_schema_v1_postgres` now resolve through
`schema/features/core_media.py`.

### Task 5: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy method bodies with live-module compat shells delegating
   through `import_module(...)`.
2. Preserve both method signatures exactly.
3. Re-run the Task 1 regression slice and the Task 2 helper slice.

Expected: PASS

Result: PASS. The legacy `_apply_schema_v1_sqlite(...)` and
`_apply_schema_v1_postgres(...)` methods are now live-module compat shells that
delegate through `import_module(...)`.

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_core_media_schema python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_core_media_schema_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
  -k '_apply_schema_v1_sqlite or _apply_schema_v1_postgres or core_media or initialize_sqlite_schema or initialize_postgres_schema'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `4`

Result: PASS.

- Focused regression slice:
  `4 passed, 517 deselected, 6 warnings`
- Focused helper slice:
  `6 passed, 6 warnings`
- Tranche pytest bundle:
  `12 passed, 591 deselected, 6 warnings`
- Bandit on touched production files:
  `0` results, `0` errors
- Normalized ownership count:
  `6 -> 4`
- `git diff --check`:
  clean
