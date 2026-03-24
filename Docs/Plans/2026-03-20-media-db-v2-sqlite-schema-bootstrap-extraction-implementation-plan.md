# Media DB V2 SQLite Schema Bootstrap Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move SQLite schema bootstrap coordination out of legacy `Media_DB_v2`
ownership while keeping the package bootstrap dispatcher stable and deferring
PostgreSQL bootstrap/migration ownership.

**Architecture:** Keep `ensure_media_schema()` as the package dispatcher, replace
the SQLite backend bridge with a package-native coordinator, and centralize the
duplicated SQLite post-core ensure block into package-native helpers. Leave
Postgres bootstrap and heavy migration ownership untouched.

**Tech Stack:** Python 3.11, pytest, SQLite, Config-driven migration tooling, Loguru

---

### Task 1: Add SQLite Backend Bridge Ownership Regressions

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Step 1: Write the failing test**

Add a regression proving that the SQLite backend bridge currently still calls
the legacy private method:

- patch a fake DB object exposing `_initialize_schema_sqlite`
- call `initialize_sqlite_schema(db)`
- assert the legacy method was invoked

Then add the future-state assertion that the bridge should instead call a
package-native coordinator helper.

Expected target after implementation:

- `initialize_sqlite_schema(...)` dispatches to package-native helper logic
- not directly to `db._initialize_schema_sqlite()`

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'sqlite'
```

Expected: FAIL for the intended bridge-ownership reason.

**Step 3: Write minimal implementation**

Only add the regression test in this task.

**Step 4: Re-run to confirm the red phase**

Run the same command again and confirm the failure is the intended one.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py
git commit -m "test: add sqlite schema bootstrap ownership regressions"
```

### Task 2: Extract SQLite Post-Core Ensure Helpers

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite_helpers.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
- Test: `tldw_Server_API/tests/DB_Management/test_email_native_stage1.py`

**Step 1: Use the failing bridge regression as the red anchor**

Also add focused unit tests for any new helper that centralizes the duplicated
post-core ensure block.

Target helper responsibilities:

- ensure collections/content items
- ensure visibility/source hash
- ensure claims extensions
- ensure email schema
- ensure FTS follow-up

**Step 2: Run focused tests to verify red state**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  -k 'sqlite or bootstrap or email_schema'
```

Expected: FAIL for the missing helper path or missing new assertions.

**Step 3: Write minimal implementation**

Create package-native SQLite helper(s) that centralize the duplicated follow-up
ensure block now present in legacy SQLite bootstrap code.

Keep the implementation thin and behavior-preserving:

- call existing DB methods rather than rewriting lower-level schema logic
- do not touch Postgres helpers
- do not move migration tool integration yet

**Step 4: Re-run focused tests**

Run the same command again.

Expected: helper-focused tests pass, bridge ownership still red until Task 3.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite_helpers.py \
        tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
        tldw_Server_API/tests/DB_Management/test_email_native_stage1.py
git commit -m "refactor: extract sqlite schema ensure helpers"
```

### Task 3: Replace The SQLite Backend Bridge

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Step 1: Reuse the failing bridge-ownership regression**

The SQLite bridge should still be red from Task 1.

**Step 2: Run the targeted bootstrap tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'sqlite'
```

Expected: FAIL because `initialize_sqlite_schema()` still delegates directly to
legacy `_initialize_schema_sqlite()`.

**Step 3: Write minimal implementation**

Update `schema/backends/sqlite.py` so `initialize_sqlite_schema(db)` calls the
package-native SQLite coordinator/helper path instead of the legacy private
method directly.

Do not change:

- `ensure_media_schema(...)`
- Postgres bridge
- `MediaDatabase._initialize_schema(...)`
- legacy Postgres migration methods

**Step 4: Re-run the targeted bootstrap tests**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite.py \
        tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py
git commit -m "refactor: route sqlite schema bootstrap through package coordinator"
```

### Task 4: Verify SQLite Bootstrap Behavior End-To-End

**Files:**
- Test only unless gaps are found

**Step 1: Run the focused SQLite bootstrap bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
```

Expected: PASS

**Step 2: Add only the smallest missing regression if needed**

If coverage is missing for one of these scenarios, add one focused test:

- fresh SQLite bootstrap
- already-current SQLite schema keepalive path
- upgraded SQLite schema ensure path

Do not add broad new integration suites.

**Step 3: Re-run the focused SQLite bootstrap bundle**

Run the same command again.

Expected: PASS

**Step 4: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
        tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: verify sqlite schema bootstrap extraction"
```

### Task 5: Close Out The Tranche

**Files:**
- Verify touched files only

**Step 1: Run the tranche close-out bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
```

Expected: PASS

**Step 2: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite_helpers.py
```

Expected: `No issues identified.`

**Step 3: Run ownership recount**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: count decreases from the current `225`.

**Step 4: Diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no diff-check errors; clean worktree after final commit.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite.py \
        tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite_helpers.py \
        tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
        tldw_Server_API/tests/DB_Management/test_email_native_stage1.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: extract sqlite schema bootstrap coordinator"
```

## Notes For The Implementer

- Do not widen this into PostgreSQL bootstrap.
- Do not touch `schema/backends/postgres.py` in this tranche.
- Do not move `_get_postgres_migrations()` or any `_postgres_migrate_to_v*`.
- Keep the package dispatcher stable and focus only on the SQLite backend
  bridge/coordinator.
- If a change starts pulling in Postgres migration ownership, stop and re-scope.
