# Media DB V2 Postgres Migration Registry And Runner Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move PostgreSQL migration registry and sequential runner ownership out
of legacy `Media_DB_v2` while keeping the individual `_postgres_migrate_to_v*()`
methods and their direct compatibility surface intact.

**Architecture:** Turn `schema/migrations.py` into the real owner of migration
map assembly and sequential runner behavior, then keep
`Media_DB_v2._get_postgres_migrations()` and `_run_postgres_migrations()` as
thin delegating shells. Leave the actual migration body methods bound on the DB
instance for this tranche.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Migration Registry And Runner Ownership Regressions

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

Add focused regressions asserting:

- `MediaDatabase._get_postgres_migrations.__globals__["__name__"]` should resolve
  to `tldw_Server_API.app.core.DB_Management.media_db.schema.migrations`
- `MediaDatabase._run_postgres_migrations.__globals__["__name__"]` should resolve
  to the same package module after the extraction

Keep the assertions narrow and ownership-focused.

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migration'
```

Expected: FAIL because both methods are still legacy-owned.

**Step 3: Write minimal implementation**

Only add the regression tests in this task.

**Step 4: Re-run to confirm red**

Run the same command again and confirm the failure is still for ownership.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: add postgres migration ownership regressions"
```

### Task 2: Make `schema/migrations.py` The Real Registry/Runner Owner

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Reuse the failing ownership tests**

The tests from Task 1 should still be red.

**Step 2: Run the targeted regression slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migration'
```

Expected: FAIL on legacy ownership.

**Step 3: Write minimal implementation**

Replace the pass-through helper in `schema/migrations.py` with:

- a protocol that includes:
  - `_postgres_migrate_to_v5` through `_postgres_migrate_to_v22`
  - `_update_schema_version_postgres`
- `build_postgres_migration_map(db)` returning the version-to-bound-method map
- `get_postgres_migrations(db)` delegating to that map builder
- `run_postgres_migrations(db, conn, current_version, target_version)` owning
  the sequential loop, version updates, `ensure_postgres_policies(db, conn)`,
  and incomplete-path `SchemaError`

Do not move any migration body method implementations into this module.

**Step 4: Re-run tests**

Run the same command again.

Expected: ownership tests may still be red until the legacy methods delegate in
Task 3.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: extract postgres migration registry and runner"
```

### Task 3: Delegate Legacy Migration Entry Points

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Reuse the failing ownership regressions**

The regression tests should still identify legacy ownership.

**Step 2: Run the targeted ownership slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migration'
```

Expected: FAIL because `Media_DB_v2` methods still own the behavior directly.

**Step 3: Write minimal implementation**

Update `Media_DB_v2.py` so:

- `_get_postgres_migrations()` returns `get_postgres_migrations(self)`
- `_run_postgres_migrations(...)` calls
  `run_postgres_migrations(self, conn, current_version, target_version)`

Keep both methods present on the legacy class. Do not change the individual
`_postgres_migrate_to_v*()` methods.

**Step 4: Re-run tests**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: delegate postgres migration entry points"
```

### Task 4: Verify Postgres Migration Behavior Stays Stable

**Files:**
- Test only unless gaps are found

**Step 1: Run the focused Postgres migration bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
```

Expected: PASS

**Step 2: Add only the smallest missing regression if needed**

If a gap appears, add one focused test for:

- migration registry reachability
- runner updates schema version after each step
- policy ensure still runs after the loop

Do not add a broad new Postgres suite.

**Step 3: Re-run the focused bundle**

Run the same command again.

Expected: PASS

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: verify postgres migration registry extraction"
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
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
```

Expected: PASS

**Step 2: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
```

Expected: no new issues

**Step 3: Recount normalized legacy-owned methods**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: same or lower count; document the measured result

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
  tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: extract postgres migration registry runner"
```
