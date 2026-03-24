# Media DB V2 Constructor Resolution Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind Media DB backend-resolution ownership to a package-native runtime module without moving schema/bootstrap coordinators or Postgres migration domains.

**Architecture:** Add a dedicated `media_db.runtime.backend_resolution` module, move only `_resolve_backend` there, and lock current constructor behavior with focused regressions before and after the rebind. Keep `__init__` as the compat-owned coordinator for path validation, in-memory connection setup, and schema initialization.

**Tech Stack:** Python 3.11, pytest, SQLite, PostgreSQL backend abstractions, ConfigParser, Loguru

---

### Task 1: Add Ownership And Constructor-Path Regressions

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Write the failing tests**

Add a new ownership regression asserting:

```python
MediaDatabase.__dict__["_resolve_backend"].__globals__["__name__"] == (
    "tldw_Server_API.app.core.DB_Management.media_db.runtime.backend_resolution"
)
```

Add constructor-path regressions for these behaviors:

1. explicit backend parameter wins
2. env-forced Postgres resolution uses configured backend when available
3. pytest/test-mode with explicit file path suppresses forced Postgres
4. `:memory:` constructor still creates the persistent SQLite connection
5. constructor failure calls `close_connection()` before raising `DatabaseError`

Prefer monkeypatching config/env helpers and `_initialize_schema` rather than
building large integration fixtures.

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'resolve_backend or constructor'
```

Expected: FAIL on the ownership assertion and any constructor-path tests that
depend on the future runtime module.

**Step 3: Write minimal implementation**

Only add the tests in this task.

**Step 4: Run tests again to verify the red phase is real**

Run the same command again and confirm the failures are for the intended
ownership/constructor reasons.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "test: add media db constructor resolution regressions"
```

### Task 2: Add The Runtime Backend-Resolution Module

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/backend_resolution.py`

**Step 1: Reuse the failing ownership test**

No new test file is needed. The Task 1 ownership test is the red phase.

**Step 2: Run the red test**

Run the Task 1 command again.

Expected: FAIL because the runtime module does not exist and `_resolve_backend`
is still legacy-owned.

**Step 3: Write minimal implementation**

Create `backend_resolution.py` with a method-shaped `_resolve_backend(self, *, backend, config)` that preserves the exact current logic:

- explicit backend precedence
- config loading fallback
- env-forced Postgres mode
- config-driven Postgres mode
- pytest/test-mode SQLite suppression for explicit file paths
- SQLite fallback for explicit `db_path`
- configured backend fallback
- final `DatabaseError` when nothing resolves

Do not move `__init__`, `_initialize_schema`, or any migration/bootstrap logic
into this module.

**Step 4: Run the ownership test**

Run the Task 1 command again.

Expected: still FAIL until the canonical class is rebound.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/backend_resolution.py
git commit -m "feat: add media db backend resolution runtime module"
```

### Task 3: Rebind Canonical `_resolve_backend`

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Step 1: Reuse the failing ownership test**

The Task 1 ownership assertion should still be red.

**Step 2: Run it**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'resolve_backend'
```

Expected: FAIL because the canonical class is not yet rebound.

**Step 3: Write minimal implementation**

In `media_database_impl.py`:

- import `_resolve_backend` from
  `media_db.runtime.backend_resolution`
- assign it onto `MediaDatabase`

Example:

```python
MediaDatabase._resolve_backend = _resolve_backend
```

Do not move or rewrite `__init__`.
Do not rebind `_initialize_schema*`.
Do not touch `_get_postgres_migrations` or any FTS helpers.

**Step 4: Run the ownership test**

Run the Task 2 command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py
git commit -m "refactor: rebind media db backend resolution"
```

### Task 4: Verify Constructor Behavior Did Not Change

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Finish any missing behavior regressions**

If any of these are still missing after Task 1, add only the smallest
remaining tests:

- explicit backend parameter bypasses env/config resolution
- forced Postgres path still works
- pytest explicit-path SQLite suppression still works
- `:memory:` constructor still keeps the persistent connection branch
- constructor cleanup still calls `close_connection()` on init failure

**Step 2: Run targeted constructor tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'resolve_backend or constructor or persistent_connection'
```

Expected: PASS

**Step 3: Run runtime-factory safety checks**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
```

Expected: PASS

**Step 4: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "test: verify media db constructor resolution behavior"
```

### Task 5: Close Out The Tranche

**Files:**
- Verify touched files only

**Step 1: Run the close-out DB-management bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py
```

Expected: PASS

**Step 2: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/runtime/backend_resolution.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py
```

Expected: `No issues identified.`

**Step 3: Run ownership recount**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: count decreases from the current `226`.

**Step 4: Check diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no diff-check errors; worktree clean after final commit.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/backend_resolution.py \
        tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "refactor: rebind media db constructor resolution"
```

## Notes For The Implementer

- Do not let this tranche drift into schema/bootstrap extraction.
- Do not move `_initialize_schema*`, `_apply_schema_v1_sqlite`, or any
  migration helper here.
- Do not move `_get_postgres_migrations` here.
- Keep the change centered on backend resolution and constructor-path
  regressions only.
- If a fix seems to require touching schema coordinators, stop and re-scope the
  tranche instead of widening it ad hoc.
