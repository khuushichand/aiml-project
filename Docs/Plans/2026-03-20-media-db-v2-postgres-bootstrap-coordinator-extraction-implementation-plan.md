# Media DB V2 Postgres Bootstrap Coordinator Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move PostgreSQL schema bootstrap coordination out of legacy
`Media_DB_v2` ownership while keeping migration bodies and domain-heavy migration
helpers in place.

**Architecture:** Keep `ensure_media_schema()` as the package dispatcher,
replace the Postgres backend bridge with a package-native coordinator, and
centralize the duplicated Postgres post-bootstrap ensure work into one helper.
Leave `_get_postgres_migrations()`, `_run_postgres_migrations()`, and all
`_postgres_migrate_to_v*()` methods legacy-owned in this tranche.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Postgres Backend Bridge Ownership Regressions

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Step 1: Write the failing test**

Add two Postgres-facing bridge tests:

- a characterization test proving the current bridge still calls a fake DB
  object's `_initialize_schema_postgres()`
- a future-state regression asserting the bridge should route through a
  package-native `bootstrap_postgres_schema(...)` helper instead of calling the
  legacy private method directly

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'postgres'
```

Expected: FAIL for the bridge-ownership reason.

**Step 3: Write minimal implementation**

Only add the regression tests in this task.

**Step 4: Re-run to confirm red**

Run the same command again and confirm the failure is still the intended one.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py
git commit -m "test: add postgres schema bootstrap ownership regressions"
```

### Task 2: Extract Postgres Post-Bootstrap Ensure Helper

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres_helpers.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Step 1: Write the failing helper test**

Add a focused unit test for a new helper named
`ensure_postgres_post_core_structures(db, conn)` that asserts it calls, in
order:

1. `db._ensure_postgres_collections_tables(conn)`
2. `db._ensure_postgres_tts_history(conn)`
3. `db._ensure_postgres_data_tables(conn)`
4. `db._ensure_postgres_source_hash_column(conn)`
5. `db._ensure_postgres_claims_extensions(conn)`
6. `db._ensure_postgres_email_schema(conn)`
7. `db._sync_postgres_sequences(conn)`
8. `ensure_postgres_policies(db, conn)`

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'postgres'
```

Expected: FAIL for the missing helper path or missing assertions.

**Step 3: Write minimal implementation**

Create `postgres_helpers.py` with:

- a narrow protocol covering the helper methods above
- `ensure_postgres_post_core_structures(db, conn)` implemented as a thin
  package-native wrapper

Do not move migration bodies in this task.

**Step 4: Re-run tests**

Run the same command again.

Expected: helper test passes, bridge regression still red.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres_helpers.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py
git commit -m "refactor: extract postgres schema ensure helper"
```

### Task 3: Replace The Postgres Backend Bridge And Coordinator

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres_helpers.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Step 1: Reuse the failing bridge regression**

The bridge test from Task 1 should still be red.

**Step 2: Run the targeted Postgres bridge tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'postgres'
```

Expected: FAIL because `initialize_postgres_schema()` still delegates directly to
legacy `_initialize_schema_postgres()`.

**Step 3: Write minimal implementation**

Implement in `postgres_helpers.py`:

- `bootstrap_postgres_schema(db)` as the package-owned Postgres coordinator

Coordinator rules:

- keep migration dispatch via `run_postgres_migrations(db, conn, ...)`
- keep fresh-schema creation via `apply_postgres_core_media_schema(db, conn)`
- use `ensure_postgres_fts(db, conn)` and
  `ensure_postgres_post_core_structures(db, conn)` instead of duplicating the
  inline ensure block
- preserve existing schema-version checks, migration branching, and policy setup

Then update:

- `schema/backends/postgres.py` to call the helper module through a live module
  reference
- `Media_DB_v2._initialize_schema_postgres()` to delegate to
  `bootstrap_postgres_schema(self)`

Do not move `_get_postgres_migrations()`, `_run_postgres_migrations()`, or any
`_postgres_migrate_to_v*()`.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres_helpers.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py
git commit -m "refactor: route postgres schema bootstrap through package coordinator"
```

### Task 4: Verify Postgres Bootstrap Behavior

**Files:**
- Test only unless gaps are found

**Step 1: Run the focused Postgres verification bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
```

Expected: PASS

**Step 2: Add only the smallest missing regression if needed**

If one gap appears, add one focused test for:

- fresh Postgres bootstrap
- already-current Postgres schema keepalive path
- downgraded Postgres migration dispatch

Do not add a broad new integration suite.

**Step 3: Re-run the focused bundle**

Run the same command again.

Expected: PASS

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "test: verify postgres schema bootstrap extraction"
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
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
```

Expected: PASS

**Step 2: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres_helpers.py
```

Expected: `No issues identified.`

**Step 3: Run ownership recount**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: record the updated normalized ownership count for tranche tracking.

**Step 4: Diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: clean diff check, clean worktree after final commit.
