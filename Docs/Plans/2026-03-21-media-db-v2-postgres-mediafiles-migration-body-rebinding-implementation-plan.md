# Media DB V2 Postgres MediaFiles Migration Body Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind PostgreSQL migration body method `v11` onto a package-owned
helper so the canonical `MediaDatabase` no longer owns that method through the
legacy module, while preserving the `Media_DB_v2` compat shell and keeping the
MediaFiles migration conversion and error-handling semantics unchanged.

**Architecture:** Add one package helper module for the full `v11` migration
body, rebind the canonical class method in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` method to a live-module compat shell. Leave
`migrations.py`, `_MEDIA_FILES_TABLE_SQL`, and
`_convert_sqlite_sql_to_postgres_statements(...)` untouched.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Canonical Ownership And Compat-Shell Delegation Regressions For `v11`

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**

1. Add failing regressions asserting:
   - canonical `MediaDatabase._postgres_migrate_to_v11` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase._postgres_migrate_to_v11(conn)` delegates
     through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v11'
```

Expected: FAIL

### Task 2: Add Focused Helper-Path And Migration-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py`

**Steps:**

1. Add failing helper-path tests asserting:
   - converted statements are executed in order
   - per-statement `BackendDatabaseError` is swallowed and execution continues
   - outer noncritical conversion failure is swallowed cleanly
2. Add one dedicated `v10 -> v11` PostgreSQL repair test that drops the
   `MediaFiles` table, sets schema version to `10`, reruns `_initialize_schema()`,
   and asserts table restoration
3. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v11' \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  -k 'reaches_v11'
```

Expected: FAIL

### Task 3: Add Package Helper Module For `v11`

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_mediafiles.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py`

**Steps:**

1. Create `run_postgres_migrate_to_v11(db, conn)`
2. Preserve the current body semantics exactly:
   - call `db._convert_sqlite_sql_to_postgres_statements(db._MEDIA_FILES_TABLE_SQL)`
   - execute each statement in order through `db.backend.execute(..., connection=conn)`
   - swallow and log per-statement `BackendDatabaseError`
   - swallow and log outer `_MEDIA_NONCRITICAL_EXCEPTIONS`
3. Export the helper module’s public symbols from `migration_bodies/__init__.py`
4. Re-run the Task 1 and Task 2 slices

Expected: still red until canonical rebinding and compat-shell delegation exist

### Task 4: Rebind Canonical `v11`

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**

1. Import the helper function into `media_database_impl.py`
2. Rebind `MediaDatabase._postgres_migrate_to_v11`
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertion passes, compat-shell delegation remains
red until Task 5

### Task 5: Convert Legacy `v11` To A Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**

1. Update `_postgres_migrate_to_v11(conn)` to delegate through `import_module(...)`
   to the new helper module
2. Keep the method present as a compat shell
3. Re-run the Task 1 regression slice

Expected: PASS

### Task 6: Verify The Helper Path And Migration Path

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**

1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v11'
```

Expected: PASS

2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  -k 'reaches_v11'
```

Expected: PASS or SKIP when the local Postgres backend fixture is unavailable

### Task 7: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**

1. Run the focused DB-management bundle:

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

2. Run Bandit on the touched production scope:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_mediafiles.py \
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py \
  tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
```

Expected: no new issues

3. Recount legacy ownership:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python Helper_Scripts/checks/media_db_runtime_ownership_count.py
```

Expected: `207`

4. Run:

```bash
git diff --check
```

Expected: no output
