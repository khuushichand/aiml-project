# Media DB V2 Postgres Claims Migration Body Rebinding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebind PostgreSQL migration body methods `v10` and `v17` onto a
package-owned helper so the canonical `MediaDatabase` no longer owns those
methods through the legacy module, while preserving the `Media_DB_v2` compat
shell and keeping the current claims-helper invocation order unchanged.

**Architecture:** Add one package helper module for the paired claims migration
bodies, rebind the canonical class methods in `media_database_impl.py`, and
convert the legacy `Media_DB_v2` methods to live-module compat shells. Leave
`migrations.py`, `_ensure_postgres_claims_tables(...)`, and
`_ensure_postgres_claims_extensions(...)` untouched.

**Tech Stack:** Python 3.11, pytest, PostgreSQL backend abstraction, Loguru

---

### Task 1: Add Canonical Ownership And Compat-Shell Delegation Regressions For `v10` And `v17`

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**

1. Add failing regressions asserting:
   - canonical `MediaDatabase._postgres_migrate_to_v10` is no longer
     legacy-owned
   - canonical `MediaDatabase._postgres_migrate_to_v17` is no longer
     legacy-owned
   - legacy `_LegacyMediaDatabase._postgres_migrate_to_v10(conn)` delegates
     through a package helper
   - legacy `_LegacyMediaDatabase._postgres_migrate_to_v17(conn)` delegates
     through a package helper
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k 'postgres_migrate_to_v10 or postgres_migrate_to_v17'
```

Expected: FAIL

### Task 2: Add Focused Helper-Path Red Tests For Claims Helper Order

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**

1. Add failing unit tests asserting:
   - `run_postgres_migrate_to_v10(db, conn)` calls
     `_ensure_postgres_claims_tables(conn)` then
     `_ensure_postgres_claims_extensions(conn)`
   - `run_postgres_migrate_to_v17(db, conn)` does the same in the same order
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v10 or run_postgres_migrate_to_v17'
```

Expected: FAIL

### Task 3: Add Package Helper Module For `v10` And `v17`

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_claims.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/__init__.py`

**Steps:**

1. Create:
   - `run_postgres_migrate_to_v10(db, conn)`
   - `run_postgres_migrate_to_v17(db, conn)`
2. Preserve current order exactly for both methods:
   - `db._ensure_postgres_claims_tables(conn)`
   - `db._ensure_postgres_claims_extensions(conn)`
3. Export the helper module’s public symbols from `migration_bodies/__init__.py`
4. Re-run the Task 1 and Task 2 slices

Expected: still red until canonical rebinding and compat-shell delegation exist

### Task 4: Rebind Canonical `v10` And `v17`

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**

1. Import the helper functions into `media_database_impl.py`
2. Rebind:
   - `MediaDatabase._postgres_migrate_to_v10`
   - `MediaDatabase._postgres_migrate_to_v17`
3. Re-run the Task 1 regression slice

Expected: canonical ownership assertions pass, compat-shell delegation remains
red until Task 5

### Task 5: Convert Legacy `v10` And `v17` To Live-Module Compat Shells

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**

1. Update `_postgres_migrate_to_v10(conn)` and `_postgres_migrate_to_v17(conn)`
   to delegate through `import_module(...)` to the new helper module
2. Keep both methods present as compat shells
3. Re-run the Task 1 regression slice

Expected: PASS

### Task 6: Verify The Helper Order And Migration Path

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**

1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'run_postgres_migrate_to_v10 or run_postgres_migrate_to_v17'
```

Expected: PASS

2. Run the broader migration-path guard:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  -k 'workspace_tag'
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
  tldw_Server_API/app/core/DB_Management/media_db/schema/migration_bodies/postgres_claims.py \
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

Expected: `208`

4. Run:

```bash
git diff --check
```

Expected: no output
