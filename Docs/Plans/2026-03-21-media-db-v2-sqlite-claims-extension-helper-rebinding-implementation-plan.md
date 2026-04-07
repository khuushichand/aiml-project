# Media DB V2 SQLite Claims Extension Helper Rebinding Implementation Plan

**Goal:** Rebind `_ensure_sqlite_claims_extensions()` onto a package-owned
schema helper module so the canonical `MediaDatabase` no longer owns this
SQLite claims-extension repair helper through `Media_DB_v2`, while preserving
the legacy compat shell and keeping behavior unchanged.

**Architecture:** Add one package schema helper module for the SQLite claims
extension helper, rebind the canonical method in `media_database_impl.py`, and
convert the legacy method in `Media_DB_v2.py` into a live-module compat shell.
Verify with direct ownership regressions, focused helper-path tests, and the
existing SQLite post-core bootstrap ordering guard.

**Tech Stack:** Python 3.11, pytest

---

### Task 1: Add Ownership And Delegation Regressions

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Steps:**
1. Add failing regressions asserting:
   - canonical `_ensure_sqlite_claims_extensions` is no longer legacy-owned
   - legacy method delegates through a package helper module
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  -k '_ensure_sqlite_claims_extensions'
```

Outcome: PASS after canonical rebinding and compat-shell conversion

### Task 2: Add Helper-Path Red Tests

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`

**Steps:**
1. Add failing helper-path tests asserting:
   - missing `Claims` table path executes `_CLAIMS_TABLE_SQL` and returns
   - existing `Claims` table path emits missing extension-column SQL, replays
     `_CLAIMS_TABLE_SQL`, and repairs `delivered_at` plus its index
2. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k 'sqlite_claims_extensions'
```

Outcome: PASS after package helper module creation

### Task 3: Add Package Schema Helper Module

**Status**: Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/sqlite_claims_extensions.py`

**Steps:**
1. Create package-owned implementation:
   - `ensure_sqlite_claims_extensions(...)`
2. Preserve the existing bootstrap, column-repair, `_CLAIMS_TABLE_SQL` replay,
   and `claims_monitoring_events` repair behavior
3. Re-run the Task 2 helper slice

Outcome: PASS

### Task 4: Rebind Canonical Method

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py`

**Steps:**
1. Import the package helper function
2. Rebind the canonical method
3. Re-run the Task 1 regression slice

Outcome: canonical ownership assertion passed

### Task 5: Convert Legacy Helper To Live-Module Compat Shell

**Status**: Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Steps:**
1. Delegate the legacy method through `import_module(...)`
2. Keep the legacy method present as a compat shell
3. Re-run the Task 1 regression slice

Outcome: PASS

### Task 6: Verify The Tranche

**Status**: Complete

**Files:**
- Reuse modified files only

**Steps:**
1. Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  -k '_ensure_sqlite_claims_extensions or sqlite_claims_extensions or ensure_sqlite_post_core_structures_runs_followup_ensures'
```

2. Run Bandit on touched production files
3. Recount ownership
4. Run `git diff --check`

Verification:
- `python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py -k '_ensure_sqlite_claims_extensions or sqlite_claims_extensions or ensure_sqlite_post_core_structures_runs_followup_ensures'`
  - `5 passed, 206 deselected, 6 warnings`
- `python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db/schema/sqlite_claims_extensions.py tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
  - no issues identified
- `python Helper_Scripts/checks/media_db_runtime_ownership_count.py`
  - `184`
- `git diff --check`
  - clean
