# Media DB V2 Stage 1 Caller-First Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** Complete on `codex/media-db-v2-stage1-caller-first` as of 2026-03-18.

**Goal:** Decouple the new Media DB seam from `DB_Manager`, replace the last direct app import of `MediaDatabase`, and migrate the first non-compat test batch onto seam-based fixtures.

**Architecture:** Extract one shared runtime-defaults provider under `media_db/runtime`, consume it from both `media_db.api` and `DB_Manager`, then introduce a real protocol for app-facing typing. After the app-side boundary is clean, add seam-based test helpers and migrate only non-compat tests while preserving explicit compatibility suites.

**Tech Stack:** Python 3.11, FastAPI-adjacent service layer, pytest, SQLite/PostgreSQL backend abstraction, Loguru

## Execution Summary

- Task 1 completed with a new shared runtime-defaults module at
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/defaults.py`
- Task 2 completed with a real `MediaDbLike` protocol and the removal of the
  last direct app import of `Media_DB_v2.MediaDatabase`
- Task 3 completed with seam-backed fixtures in `tldw_Server_API/tests/conftest.py`
  and the first migrated non-compat batch in Chat, External Sources, Media, and
  the DataTables app factory
- Task 4 completed with seam-boundary regression guards in
  `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

Fresh verification snapshot:

- `153 passed, 29 deselected, 10 warnings`
- Bandit on the touched scope reported only low-severity test-file findings;
  touched production files had no findings

---

### Task 1: Extract Shared Media DB Runtime Defaults

**Status:** Complete

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/defaults.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

**Step 1: Write the failing test**

Add source-boundary assertions that prove the seam no longer relies on `DB_Manager` as its runtime-default provider.

```python
def test_media_db_api_no_longer_mentions_db_manager() -> None:
    import inspect
    from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api

    assert "DB_Manager" not in inspect.getsource(media_db_api)
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'api_no_longer_mentions_db_manager'`

Expected: FAIL because `media_db.api` still imports `DB_Manager`

**Step 3: Write minimal implementation**

Create `runtime/defaults.py` with a single helper that resolves:

- `default_db_path`
- `default_config`
- `postgres_content_mode`
- `backend_loader`

Then update `media_db.api` and `DB_Manager` to use that helper rather than
having `api.py` import `DB_Manager`.

**Step 4: Run tests to verify they pass**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/defaults.py \
        tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py
git commit -m "refactor: extract shared media db runtime defaults"
```

### Task 2: Replace the Last Direct App Import With a Real Protocol

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/validation.py`
- Modify: `tldw_Server_API/app/core/Sharing/shared_workspace_resolver.py`
- Test: `tldw_Server_API/tests/Sharing/test_cross_user_access.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add a boundary test that proves the sharing resolver no longer imports the
legacy Media DB class directly.

```python
def test_shared_workspace_resolver_no_longer_mentions_media_db_v2() -> None:
    import inspect
    from tldw_Server_API.app.core.Sharing import shared_workspace_resolver

    assert "Media_DB_v2" not in inspect.getsource(shared_workspace_resolver)
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'shared_workspace_resolver_no_longer_mentions_media_db_v2'`

Expected: FAIL because `shared_workspace_resolver.py` still imports `MediaDatabase`

**Step 3: Write minimal implementation**

Add a real protocol to `runtime/validation.py` for the resolver-facing Media DB
surface, then update `shared_workspace_resolver.py` to type against that
protocol instead of `Media_DB_v2.MediaDatabase`.

**Step 4: Run tests to verify they pass**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Sharing/test_cross_user_access.py tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'shared_workspace_resolver_no_longer_mentions_media_db_v2 or cross_user_access'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/validation.py \
        tldw_Server_API/app/core/Sharing/shared_workspace_resolver.py \
        tldw_Server_API/tests/Sharing/test_cross_user_access.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: remove legacy media db import from sharing resolver"
```

### Task 3: Add Seam-Based Test Helpers and Migrate the First Non-Compat Batch

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/conftest.py`
- Modify: `tldw_Server_API/tests/Chat/test_fixtures.py`
- Modify: `tldw_Server_API/tests/External_Sources/test_sync_coordinator.py`
- Modify: `tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py`
- Indirectly updated via fixture: `tldw_Server_API/tests/DataTables/test_data_tables_api.py`
- Test: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`

**Step 1: Write the failing test**

Add or extend a helper-usage regression that proves the first migrated tests can
seed content without importing `Media_DB_v2.MediaDatabase` directly.

```python
def test_migrated_feature_tests_use_media_db_api_helper() -> None:
    import inspect
    from tldw_Server_API.tests.Media import test_media_reprocess_endpoint

    assert "Media_DB_v2" not in inspect.getsource(test_media_reprocess_endpoint)
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'migrated_feature_tests_use_media_db_api_helper'`

Expected: FAIL because the selected feature tests still import `MediaDatabase`

**Step 3: Write minimal implementation**

Create small seam-based helpers in `tldw_Server_API/tests/conftest.py` that
construct test DBs via `media_db.api.create_media_database` and
`managed_media_database`, then migrate the selected non-compat tests to those
helpers. Do not touch:

- `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- `tldw_Server_API/tests/MediaDB2/*`

Those remain the compatibility/contract quarantine for Stage 1.

**Step 4: Run tests to verify they pass**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/test_fixtures.py tldw_Server_API/tests/External_Sources/test_sync_coordinator.py tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py tldw_Server_API/tests/DataTables/test_data_tables_api.py -k 'test_generate_and_get_data_table or test_reconcile_ or test_reprocess_' tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/conftest.py \
        tldw_Server_API/tests/Chat/test_fixtures.py \
        tldw_Server_API/tests/External_Sources/test_sync_coordinator.py \
        tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py \
        tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py
git commit -m "test: migrate first media db callers to seam fixtures"
```

### Task 4: Add Regression Guards for Stage 1 Boundaries

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add a small boundary ledger that asserts:

- `media_db.api` does not mention `DB_Manager`
- `shared_workspace_resolver.py` does not mention `Media_DB_v2`
- explicit compatibility suites still do mention legacy surfaces where intended

```python
def test_db_manager_wrapper_suite_remains_explicit_compat_surface() -> None:
    import inspect
    from tldw_Server_API.tests.DB_Management import test_db_manager_wrappers

    assert "MediaDatabase" in inspect.getsource(test_db_manager_wrappers)
```

**Step 2: Run test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'compat_surface'`

Expected: FAIL until the boundary ledger is complete

**Step 3: Write minimal implementation**

Complete the boundary assertions and keep them narrow so they guard only the
Stage 1 seam decisions.

**Step 4: Run tests to verify they pass**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py
git commit -m "test: add media db seam boundary guards"
```
