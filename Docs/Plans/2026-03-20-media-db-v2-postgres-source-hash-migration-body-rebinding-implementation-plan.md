# Media DB V2 Postgres Source-Hash Migration Body Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind PostgreSQL migration body method `v16` onto a package-owned
helper so the canonical `MediaDatabase` no longer owns that method through the
legacy module, while preserving the `Media_DB_v2` compat shell and leaving
`_ensure_postgres_source_hash_column(conn)` legacy-owned.

**Architecture:** Add a narrow package helper module for the PostgreSQL
source-hash migration body, rebind the canonical class method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method to a
live-module compat shell. Leave `migrations.py` and
`_ensure_postgres_source_hash_column(conn)` untouched.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Canonical Ownership And Compat-Shell Delegation Regressions For `v16`

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing tests**

Add focused regressions asserting that:

- canonical `MediaDatabase._postgres_migrate_to_v16` is no longer legacy-owned
- legacy `_LegacyMediaDatabase._postgres_migrate_to_v16(conn)` delegates through
  a package helper

Match the style established by the completed `v12`/`v13` tranche.

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v16'
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
git commit -m "test: add postgres source hash migration regressions"
```

### Task 2: Add Package-Native Source-Hash Migration Body Helper

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_source_hash.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py`

**Step 1: Reuse the failing regression**

The Task 1 tests should still be red.

**Step 2: Run the targeted red slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v16'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Create the helper module with:

- a protocol requiring `_ensure_postgres_source_hash_column(conn)`
- `run_postgres_migrate_to_v16(db, conn)` delegating to
  `db._ensure_postgres_source_hash_column(conn)`

Update `migration_bodies/__init__.py` only to export the new module’s public
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
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_source_hash.py
git commit -m "refactor: add postgres source hash migration helper"
```

### Task 3: Rebind Canonical `v16` Method

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Step 1: Reuse the failing regressions**

The Task 1 tests should still be red.

**Step 2: Run the targeted regression slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v16'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Import the package helper function into `media_database_impl.py` and rebind:

- `MediaDatabase._postgres_migrate_to_v16`

Do not change the migration registry/runner.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: partially green, with the canonical ownership assertion passing and
the legacy-shell delegation assertion still red until Task 4.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py
git commit -m "refactor: rebind postgres source hash migration body"
```

### Task 4: Convert Legacy `v16` To A Live-Module Compat Shell

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Step 1: Reuse the remaining failing regression**

The Task 1 tests should still be red because the compat-shell delegation is not
in place yet.

**Step 2: Run the targeted regression slice**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v16'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Update `Media_DB_v2.py` so `_postgres_migrate_to_v16(conn)` delegates through
`import_module(...)` to the new helper module.

Keep the method present as a compat shell. Do not change
`_ensure_postgres_source_hash_column(conn)` or `migrations.py`.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: delegate postgres source hash migration"
```

### Task 5: Add Focused Source-Hash Behavior Check

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
  or `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

Add one small focused test that proves the `v16` path still invokes the
source-hash ensure behavior. Prefer the smallest test that isolates the
`v16` migration body rather than broadening the Postgres suite.

**Step 2: Run the targeted test**

Run the smallest relevant pytest selector and confirm it fails for the intended
reason before implementation.

**Step 3: Write minimal implementation**

Add only the smallest change needed for the focused behavior test to pass.
Prefer test-only refinement unless a real implementation gap is exposed.

**Step 4: Re-run the targeted test**

Confirm it passes.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "test: cover postgres source hash migration path"
```

### Task 6: Verify The Tranche

**Files:**
- Test only unless a gap is found

**Step 1: Run the focused Postgres verification bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py
```

Expected: PASS

**Step 2: Run Bandit on touched production files**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_source_hash.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
```

Expected: no new issues

**Step 3: Recount normalized legacy-owned methods**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: count drops by `1`

**Step 4: Check diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: clean diff and expected branch state
