# Media DB V2 Bootstrap Lifecycle Helper Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind the remaining bootstrap lifecycle trio onto a package-owned
runtime helper while preserving constructor, compatibility-wrapper, and
in-memory SQLite behavior.

**Architecture:** Add a package-owned bootstrap lifecycle runtime module for
`__init__(...)`, `initialize_db(...)`, and `_ensure_sqlite_backend(...)`,
rebind the canonical `MediaDatabase` methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods into live-module compat shells. Leave
`rollback_to_version(...)` untouched.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing canonical regressions asserting:
   - `MediaDatabase.__init__(...)`
   - `MediaDatabase.initialize_db(...)`
   - `MediaDatabase._ensure_sqlite_backend(...)`
   no longer resolve globals from `Media_DB_v2`.
2. Add failing compat-shell delegation regressions proving the legacy methods
   delegate through `runtime/bootstrap_lifecycle_ops.py` via live
   `import_module(...)` references.
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_bootstrap_lifecycle python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '__init__ or initialize_db or _ensure_sqlite_backend'
```

Expected: FAIL

Result: PASS. Added canonical ownership assertions for `__init__(...)`,
`initialize_db(...)`, and `_ensure_sqlite_backend(...)`, plus legacy
delegation regressions for all three methods. Confirmed the red phase before
implementation (`4 failed, 523 deselected, 6 warnings` on the regression file
plus the helper rebind assertion in the dedicated helper file).

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_bootstrap_lifecycle_ops.py`

**Steps:**
1. Add a failing helper-path test asserting canonical rebinding to
   `runtime/bootstrap_lifecycle_ops.py`.
2. Add focused constructor tests covering:
   - explicit backend path still calls `_initialize_schema()` once
   - in-memory SQLite path creates a persistent connection and uses
     `_apply_sqlite_connection_pragmas(...)`
   - constructor failure calls `close_connection()` before raising
3. Add focused wrapper tests covering:
   - `initialize_db(...)` returns `self`
   - `initialize_db(...)` re-wraps bootstrap failures into `DatabaseError`
   - `_ensure_sqlite_backend(...)` is harmless for SQLite and non-SQLite
4. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_bootstrap_lifecycle python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_bootstrap_lifecycle_ops.py
```

Expected: FAIL

Result: PASS. Added the focused helper-path file with rebinding assertions,
constructor behavior checks, `initialize_db(...)` compatibility coverage, and
the harmless `_ensure_sqlite_backend(...)` seam. Confirmed the red phase, then
closed green after implementation (`7 passed, 6 warnings` in the helper file;
`11 passed, 523 deselected, 6 warnings` in the focused tranche slice).

### Task 3: Add The Package-Owned Bootstrap Lifecycle Helper

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/bootstrap_lifecycle_ops.py`

**Steps:**
1. Add `initialize_media_database(...)` with the constructor logic currently
   owned by `Media_DB_v2.__init__(...)`.
2. Add `initialize_db(...)` preserving `return self` and `DatabaseError`
   wrapping.
3. Add `_ensure_sqlite_backend(...)` as the package-owned compatibility no-op.
4. Preserve:
   - path/client validation
   - directory creation
   - backend resolution
   - contextvar setup
   - persistent in-memory SQLite connection setup
   - `_media_insert_lock` and `_scope_cache`
   - failure cleanup via `close_connection()`

Result: PASS. Added
`media_db/runtime/bootstrap_lifecycle_ops.py` with
`initialize_media_database(...)`, `initialize_db(...)`, and
`_ensure_sqlite_backend(...)`, preserving constructor validation, persistent
SQLite in-memory setup, contextvar initialization, and cleanup/wrapping
behavior.

### Task 4: Rebind The Canonical Methods

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the bootstrap lifecycle helpers from
   `runtime/bootstrap_lifecycle_ops.py`.
2. Rebind canonical:
   - `MediaDatabase.__init__`
   - `MediaDatabase.initialize_db`
   - `MediaDatabase._ensure_sqlite_backend`
3. Re-run the Task 1 regression slice.

Expected: canonical ownership assertions pass, compat-shell delegation still red

Result: PASS. Canonical `MediaDatabase.__init__`,
`MediaDatabase.initialize_db`, and
`MediaDatabase._ensure_sqlite_backend` now resolve through
`runtime/bootstrap_lifecycle_ops.py`.

### Task 5: Convert The Legacy Methods To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Replace the legacy bodies for:
   - `__init__(...)`
   - `initialize_db(...)`
   - `_ensure_sqlite_backend(...)`
   with live-module compat shells delegating through `import_module(...)`.
2. Preserve all three signatures exactly.
3. Re-run the Task 1 regression slice and the Task 2 helper slice.

Expected: PASS

Result: PASS. The legacy `__init__(...)`, `initialize_db(...)`, and
`_ensure_sqlite_backend(...)` methods are now live-module compat shells that
delegate through `import_module(...)`.

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
PYTHONPYCACHEPREFIX=/tmp/pycache_bootstrap_lifecycle python -m pytest -q \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_bootstrap_lifecycle_ops.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
  -k '__init__ or initialize_db or _ensure_sqlite_backend or managed_media_database or create_media_database'
```

2. Run Bandit on touched production files.
3. Recount ownership.
4. Run `git diff --check`.

Expected ownership count: `1`

Result: PASS.

- Focused tranche slice:
  `11 passed, 523 deselected, 6 warnings`
- Broader lifecycle caller guard bundle:
  `51 passed, 732 deselected, 11 warnings`
- Bandit on touched production files:
  `0` results, `0` errors
- Normalized ownership count:
  `4 -> 1`
- `git diff --check`:
  clean
