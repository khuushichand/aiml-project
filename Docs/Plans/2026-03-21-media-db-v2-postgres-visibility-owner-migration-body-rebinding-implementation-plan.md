# Media DB V2 Postgres Visibility/Owner Migration Body Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind PostgreSQL migration body method `v9` onto a package-owned
helper so the canonical `MediaDatabase` no longer owns that method through the
legacy module, while preserving the `Media_DB_v2` compat shell and keeping the
ordered visibility/owner migration SQL unchanged.

**Architecture:** Add one package-native helper module for the full `v9`
migration body, rebind the canonical class method in
`media_database_impl.py`, and convert the legacy `Media_DB_v2` method to a
live-module compat shell. Leave `migrations.py` untouched and pin exact SQL
order in a focused helper-path test plus one dedicated `v8 -> v9` Postgres
repair test.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Canonical Ownership And Compat-Shell Delegation Regressions For `v9`

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing tests**

Add focused regressions asserting that:

- canonical `MediaDatabase._postgres_migrate_to_v9` is no longer legacy-owned
- legacy `_LegacyMediaDatabase._postgres_migrate_to_v9(conn)` delegates through
  a package helper

Match the style established by the completed `v12` through `v22` tranches and
the `v5` through `v8` tranche.

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v9'
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
git commit -m "test: add postgres visibility-owner migration regressions"
```

### Task 2: Add Focused SQL-Order Helper And Migration-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py`

**Step 1: Write the failing tests**

Add:

- one helper-path test asserting the exact ordered SQL sequence for the `v9`
  migration body
- one dedicated `v8 -> v9` PostgreSQL repair test that removes `visibility`,
  `owner_user_id`, and `idx_media_visibility`, sets schema version to `8`, then
  reruns `_initialize_schema()`

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v9' \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  -k 'v8_to_v9 or visibility'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Only add the tests in this task.

**Step 4: Re-run to confirm red**

Run the same command again and confirm the failures still reflect the missing
helper seam.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py
git commit -m "test: add postgres visibility-owner migration guards"
```

### Task 3: Add Package-Native Visibility/Owner Migration Body Helper

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_visibility_owner.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py`

**Step 1: Reuse the failing regressions**

The Task 1 and Task 2 tests should still be red.

**Step 2: Run the targeted red slices**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v9' \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v9'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Create the helper module with:

- a protocol that exposes `backend`
- `run_postgres_migrate_to_v9(db, conn)` that preserves the current ordered SQL
  sequence exactly, including:
  - `visibility` column add
  - constraint block
  - `owner_user_id` column add
  - numeric `client_id` backfill
  - `idx_media_visibility`
  - `idx_media_owner_user_id`

Update `migration_bodies/__init__.py` only to export the new module’s public
symbols.

Do not change `Media_DB_v2.py`, `media_database_impl.py`, or `migrations.py`
yet.

**Step 4: Re-run tests**

Run the same command again.

Expected: still red until canonical rebinding and legacy compat-shell updates
are in place.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_visibility_owner.py
git commit -m "refactor: add postgres visibility-owner migration helper"
```

### Task 4: Rebind Canonical `v9` Method

**Status**: Complete

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
  -k 'postgres_migrate_to_v9'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Import the package helper function into `media_database_impl.py` and rebind:

- `MediaDatabase._postgres_migrate_to_v9`

Do not change the migration registry/runner.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: partially green, with the canonical ownership assertion passing and
the legacy-shell delegation assertion still red until Task 5.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py
git commit -m "refactor: rebind postgres visibility-owner migration body"
```

### Task 5: Convert Legacy `v9` To A Live-Module Compat Shell

**Status**: Complete

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
  -k 'postgres_migrate_to_v9'
```

Expected: FAIL

**Step 3: Write minimal implementation**

Update `Media_DB_v2.py` so `_postgres_migrate_to_v9(conn)` delegates through
`import_module(...)` to the new helper module.

Keep the method present as a compat shell. Do not change `migrations.py` or the
later claims/mediafiles migration bodies.

**Step 4: Re-run the targeted tests**

Run the same command again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: delegate postgres visibility-owner migration"
```

### Task 6: Verify The Helper Order And Migration Path

**Status**: Complete

**Files:**
- Reuse already modified files only

**Step 1: Run the focused helper-order test**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v9'
```

Expected: PASS

**Step 2: Run the dedicated migration-path guard**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  -k 'v8_to_v9 or visibility'
```

Expected: PASS or SKIP when the local Postgres backend fixture is unavailable

**Step 3: Commit**

```bash
git add \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py
git commit -m "test: cover postgres visibility-owner migration path"
```

### Task 7: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse already modified files only

**Step 1: Run the focused DB-management bundle**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py
```

Expected: PASS, with only environment-dependent PostgreSQL skips if the backend
fixture is unavailable

**Step 2: Run Bandit on the touched production scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_visibility_owner.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
```

Expected: no new issues

**Step 3: Recount legacy ownership**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: `210`

**Step 4: Check diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_visibility_owner.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py
git commit -m "refactor: rebind postgres visibility-owner migration body"
```
