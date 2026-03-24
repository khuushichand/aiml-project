# Media DB V2 Postgres Collections Migration Body Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind PostgreSQL migration body methods `v12` and `v13` onto
package-owned helpers so the canonical `MediaDatabase` no longer owns those two
methods through the legacy module, while preserving `Media_DB_v2` compat shells
and leaving `_ensure_postgres_collections_tables(conn)` legacy-owned.

**Architecture:** Add a narrow package helper module for the `v12` and `v13`
PostgreSQL collections migration bodies, rebind the canonical class methods in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` methods to live-
module compat shells. Leave `migrations.py` untouched because it already builds
the migration map from the active DB object's bound methods.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Canonical Ownership And Compat-Shell Delegation Regressions

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing tests**

Add focused regressions asserting that:

- canonical `MediaDatabase._postgres_migrate_to_v12` is no longer legacy-owned
- canonical `MediaDatabase._postgres_migrate_to_v13` is no longer legacy-owned
- legacy `_postgres_migrate_to_v12(conn)` delegates through a package helper
- legacy `_postgres_migrate_to_v13(conn)` delegates through a package helper

Use the same style as earlier canonical ownership regressions and the existing
`v14`/`v15` compat-shell delegation tests.

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v12 or postgres_migrate_to_v13'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Only add the regression tests in this task.

**Step 4: Re-run to confirm red**

Run the same command again and confirm the failures still match the missing
ownership/delegation seam.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: add postgres collections migration regressions"
```

### Task 2: Add Package-Native Collections Migration Body Helpers

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_collections.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py`

**Step 1: Reuse the failing regression**

The Task 1 tests should still be red.

**Step 2: Run the targeted red slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v12 or postgres_migrate_to_v13'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Create the helper module with:

- a protocol requiring `_ensure_postgres_collections_tables(conn)`
- `run_postgres_migrate_to_v12(db, conn)` delegating to
  `db._ensure_postgres_collections_tables(conn)`
- `run_postgres_migrate_to_v13(db, conn)` delegating to
  `db._ensure_postgres_collections_tables(conn)`

Update `migration_bodies/__init__.py` only to export the new module's public
symbols.

Do not change `Media_DB_v2.py`, `media_database_impl.py`, or `migrations.py`
yet.

**Step 4: Re-run tests**

Run the same command again.

Expected: still red until Task 3 and Task 4 are implemented.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_collections.py
git commit -m "refactor: add postgres collections migration helpers"
```

### Task 3: Rebind Canonical `v12` And `v13` Methods

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Step 1: Reuse the failing ownership/delegation regressions**

The Task 1 tests should still be red.

**Step 2: Run the targeted regression slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v12 or postgres_migrate_to_v13'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Import the package helper functions into `media_database_impl.py` and rebind:

- `MediaDatabase._postgres_migrate_to_v12`
- `MediaDatabase._postgres_migrate_to_v13`

Do not change the migration registry/runner.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: still red until the legacy compat shells are updated in Task 4.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py
git commit -m "refactor: rebind postgres collections migration bodies"
```

### Task 4: Convert Legacy `v12` And `v13` To Live-Module Compat Shells

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Step 1: Reuse the remaining failing regressions**

The Task 1 tests should still be red because the compat-shell delegation is not
in place yet.

**Step 2: Run the targeted regression slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v12 or postgres_migrate_to_v13'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Update `Media_DB_v2.py` so:

- `_postgres_migrate_to_v12(conn)` delegates through `import_module(...)`
  to the new helper module
- `_postgres_migrate_to_v13(conn)` does the same

Keep both methods present as compat shells. Do not change
`_ensure_postgres_collections_tables(conn)` or `migrations.py`.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: delegate postgres collections migrations"
```

### Task 5: Verify Postgres Collections Migration Rebinding

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

If a gap appears, add a focused test for:

- canonical `v12` ownership
- canonical `v13` ownership
- legacy `v12` helper delegation
- legacy `v13` helper delegation

Do not add a broad new Postgres suite.

**Step 3: Re-run the focused bundle**

Run the same command again.

Expected: PASS

**Step 4: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_collections.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
```

Expected: no new issues

**Step 5: Recount normalized legacy-owned methods**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: count drops by `2`

**Step 6: Check diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: clean diff and expected branch state
