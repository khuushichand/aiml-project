# Media DB V2 Postgres Data Tables Migration Body Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move PostgreSQL data-tables migration body behavior for `v14` and
`v15` behind package-native helpers while keeping `Media_DB_v2` as the
compat-shell entrypoint and keeping `_ensure_postgres_data_tables` plus the
bound-method migration surface intact.

**Architecture:** Add one narrow package-native helper module for the `v14` and
`v15` migration bodies, then keep
`Media_DB_v2._postgres_migrate_to_v14/_v15` as thin delegating compat shells
that call through a live module reference. The migration registry and runner
stay untouched in this tranche, `_ensure_postgres_data_tables(conn)` remains
legacy-owned, and the normalized ownership count may stay flat because the
registry still binds to the legacy shell methods.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Data-Tables Migration Body Delegation Regressions

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

Add focused regressions asserting that:

- `_postgres_migrate_to_v14(conn)` delegates through a package helper
- `_postgres_migrate_to_v15(conn)` delegates through a package helper

Because these methods remain compat shells, test delegation by monkeypatching
the package helper module names rather than asserting raw `__globals__`
ownership. Lock this invariant down here; do not leave it as a later decision.

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v14 or postgres_migrate_to_v15'
```

Expected: FAIL because `Media_DB_v2` still owns the body methods directly.

**Step 3: Write minimal implementation**

Only add the regression tests in this task.

**Step 4: Re-run to confirm red**

Run the same command again and confirm the failure is still for delegation not
being present yet.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: add postgres data tables migration regressions"
```

### Task 2: Add Package-Native Data-Tables Migration Body Helpers

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_data_tables.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py`

**Step 1: Reuse the failing regression**

The tests from Task 1 should still be red.

**Step 2: Run the targeted red slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v14 or postgres_migrate_to_v15'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Create the package-native helper module with:

- a protocol that requires `_ensure_postgres_data_tables(conn)`
- `run_postgres_migrate_to_v14(db, conn)` delegating to
  `db._ensure_postgres_data_tables(conn)`
- `run_postgres_migrate_to_v15(db, conn)` delegating to
  `db._ensure_postgres_data_tables(conn)`

Do not change `Media_DB_v2.py` yet.

**Step 4: Re-run tests**

Run the same command again.

Expected: still red until `Media_DB_v2` delegates in Task 3.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_data_tables.py
git commit -m "refactor: add postgres data tables migration helpers"
```

### Task 3: Delegate Legacy `v14` And `v15` Body Methods

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Reuse the failing delegation regressions**

The Task 1 tests should still be red.

**Step 2: Run the targeted regression slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v14 or postgres_migrate_to_v15'
```

Expected: FAIL because the legacy methods still own the body behavior directly.

**Step 3: Write minimal implementation**

Update `Media_DB_v2.py` so:

- `_postgres_migrate_to_v14(conn)` calls the helper through a live module
  reference, not a statically imported function name
- `_postgres_migrate_to_v15(conn)` does the same

Keep both methods present as compat shells. Do not change
`_ensure_postgres_data_tables(conn)`.

Do not reinterpret the Task 1 tests here; they should already be written as
delegation checks.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: delegate postgres data tables migrations"
```

### Task 4: Verify Data-Tables Migration Behavior

**Files:**
- Test only unless a gap is found

**Step 1: Run the focused Postgres verification bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
```

Expected: PASS

**Step 2: Add only the smallest missing regression if needed**

If a gap appears, add one focused test for:

- `v14` calling the data-tables ensure helper
- `v15` calling the data-tables ensure helper
- downgraded migration path still restoring `workspace_tag`

Do not add a broad new Postgres suite.

**Step 3: Re-run the focused bundle**

Run the same command again.

Expected: PASS

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: verify postgres data tables migration extraction"
```

### Task 5: Close Out The Tranche

**Files:**
- Verify touched files only

**Step 1: Run the tranche close-out bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
```

Expected: PASS

**Step 2: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_data_tables.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
```

Expected: no new issues

**Step 3: Recount normalized legacy-owned methods**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: same or lower count; document the measured result, but do not treat a
flat count as failure for this compat-shell slice.

**Step 4: Check diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: clean diff check; only intended tracked changes before final commit,
clean worktree after final commit

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_data_tables.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: extract postgres data tables migration bodies"
```
