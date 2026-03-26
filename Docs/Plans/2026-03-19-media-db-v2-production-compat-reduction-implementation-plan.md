# Media DB V2 Production Compat Reduction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move a bounded set of production media endpoints off `legacy_*` helper imports and off the `DB_Manager` listing wrapper path by adding thin package-native facades in `media_db.api`.

**Architecture:** Keep the current extracted helper implementations in place, but stop importing them directly from the selected production callers. Add a narrow caller-facing surface in `media_db.api`, migrate the chosen endpoints to that surface, and enforce the new boundary with tranche-scoped source guards.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Add Tranche-Scoped Boundary Tests For The New Caller Surface

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add tests that fail when the selected endpoints still import compat helpers:

```python
@pytest.mark.parametrize(
    ("relative_path", "forbidden_fragment"),
    [
        (
            "tldw_Server_API/app/api/v1/endpoints/media/item.py",
            "media_db.legacy_content_queries",
        ),
        (
            "tldw_Server_API/app/api/v1/endpoints/media/item.py",
            "media_db.legacy_maintenance",
        ),
        (
            "tldw_Server_API/app/api/v1/endpoints/media/listing.py",
            "core.DB_Management.DB_Manager import (\n    get_paginated_files",
        ),
    ],
)
def test_selected_media_endpoint_source_no_longer_imports_compat_helpers(
    relative_path: str,
    forbidden_fragment: str,
) -> None:
    source = _read_repo_file(relative_path)
    assert forbidden_fragment not in source


def test_media_db_api_exposes_production_compat_reduction_facades() -> None:
    expected = [
        "get_paginated_files",
        "get_paginated_trash_files",
        "fetch_keywords_for_media",
        "fetch_keywords_for_media_batch",
        "get_document_version",
        "check_media_exists",
        "permanently_delete_item",
        "get_latest_transcription",
    ]
    for name in expected:
        assert callable(getattr(media_db_api, name, None))
```

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'selected_media_endpoint_source_no_longer_imports_compat_helpers or production_compat_reduction_facades'`

Expected: FAIL because the endpoints still import `legacy_*` helpers and `listing.py` still imports the `DB_Manager` listing wrappers.

**Step 3: Write minimal implementation**

- Add the new source-guard tests only.
- Do not change production code yet.

**Step 4: Run test to verify the guards fail for the right reason**

Run the same command again.

Expected: FAIL with offender source fragments from the selected endpoint files.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "test: add media endpoint compat boundary guards"
```

### Task 2: Add Thin Package-Native Facades To `media_db.api`

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`

**Step 1: Write the failing test**

Extend the API-surface test to call through lightweight doubles where practical:

```python
def test_media_db_api_get_paginated_files_prefers_db_methods() -> None:
    class StubDb:
        def get_paginated_files(self, page: int, results_per_page: int):
            return (["row"], 4, page, 99)

    rows, total_pages, current_page, total_items = media_db_api.get_paginated_files(
        StubDb(),
        page=2,
        results_per_page=25,
    )

    assert rows == ["row"]
    assert total_pages == 4
    assert current_page == 2
    assert total_items == 99
```

Add analogous direct-call tests for:

- `get_paginated_trash_files`
- `fetch_keywords_for_media`
- `fetch_keywords_for_media_batch`
- `get_latest_transcription`

For the repository/helper-backed wrappers, it is enough to assert the function is
present and delegates through patched module functions.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'production_compat_reduction_facades or get_paginated_files_prefers_db_methods or get_paginated_trash_files_prefers_db_methods or fetch_keywords_for_media_accepts or latest_transcription'`

Expected: FAIL because the new API wrappers do not exist yet.

**Step 3: Write minimal implementation**

In `media_db.api` add these functions:

- `get_paginated_files`
- `get_paginated_trash_files`
- `fetch_keywords_for_media`
- `fetch_keywords_for_media_batch`
- `get_document_version`
- `check_media_exists`
- `permanently_delete_item`
- `get_latest_transcription`

Implementation rules:

- Prefer direct DB methods for paginated listing when present:
  - `get_paginated_files`
  - `get_paginated_media_list`
  - `get_paginated_trash_list`
- Delegate the rest to the existing extracted helper modules:
  - `legacy_content_queries`
  - `legacy_wrappers`
  - `legacy_state`
  - `legacy_maintenance`
  - `legacy_reads`
- Keep signatures caller-friendly and aligned with the current endpoint call
  sites.

**Step 4: Run test to verify it passes**

Run the same focused command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "feat: add media db api compat reduction facades"
```

### Task 3: Migrate `item.py` To The Package-Native Surface

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/item.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py`
- Test: existing media item endpoint tests discovered in the repo

**Step 1: Write the failing test**

Use the source-boundary test from Task 1 and, if needed, add a focused endpoint
test covering:

- permanent delete
- keyword update/list behavior

Only add a new behavior test if the existing suite does not already cover those
paths.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'item.py'`

Then run the focused existing behavior tests for media item delete/keywords.

Expected: FAIL on the source guard.

**Step 3: Write minimal implementation**

- Replace `legacy_content_queries.fetch_keywords_for_media` with
  `media_db.api.fetch_keywords_for_media`
- Replace `legacy_maintenance.permanently_delete_item` with
  `media_db.api.permanently_delete_item`
- Preserve all HTTP/status/error behavior

**Step 4: Run test to verify it passes**

Run the source guard and the focused item behavior tests.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/item.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        <focused_item_test_files>
git commit -m "refactor: move media item endpoint off compat helpers"
```

### Task 4: Migrate `listing.py` Off `DB_Manager` And Compat Helpers

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/listing.py`
- Test: existing listing endpoint tests under `tldw_Server_API/tests/`

**Step 1: Write the failing test**

Use the source-boundary guard and add a direct API test if needed for:

- active listing
- trash listing
- keyword inclusion
- empty trash behavior

Only add behavior tests if the existing suite does not already cover these
paths.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'listing.py or production_compat_reduction_facades'`

Expected: FAIL because `listing.py` still imports `DB_Manager` and `legacy_*`.

**Step 3: Write minimal implementation**

- Replace `DB_Manager.get_paginated_files` with `media_db.api.get_paginated_files`
- Replace `DB_Manager.get_paginated_trash_files` with
  `media_db.api.get_paginated_trash_files`
- Replace `fetch_keywords_for_media_batch` with the API wrapper
- Replace `permanently_delete_item` with the API wrapper
- Preserve all payload, ETag, logging, and graceful-degradation behavior

**Step 4: Run test to verify it passes**

Run the source guard and the focused listing tests.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/listing.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        <focused_listing_test_files>
git commit -m "refactor: move media listing endpoint off compat wrappers"
```

### Task 5: Migrate `versions.py`

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/versions.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py`
- Test: existing versions endpoint tests

**Step 1: Write the failing test**

Use the source-boundary guard and add behavior tests only if existing versions
tests do not already cover:

- media existence check before listing
- specific version lookup
- rollback/latest-version reads

**Step 2: Run test to verify it fails**

Run the guard plus the focused versions tests.

Expected: FAIL on the source guard.

**Step 3: Write minimal implementation**

- Replace `check_media_exists` with `media_db.api.check_media_exists`
- Replace `get_document_version` with `media_db.api.get_document_version`
- Keep `list_document_versions` on the existing package-native path

**Step 4: Run test to verify it passes**

Run the same focused versions command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/versions.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py \
        <focused_versions_test_files>
git commit -m "refactor: move media versions endpoint off compat helpers"
```

### Task 6: Migrate `document_insights.py` And `document_references.py`

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/document_insights.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/document_references.py`
- Test: existing document insights/references tests

**Step 1: Write the failing test**

Use the source-boundary guard to codify that these files should no longer import
`legacy_reads.get_latest_transcription`.

**Step 2: Run test to verify it fails**

Run the guard plus the focused insights/references tests.

Expected: FAIL on the source guard.

**Step 3: Write minimal implementation**

- Replace `legacy_reads.get_latest_transcription` with
  `media_db.api.get_latest_transcription`
- Preserve cache behavior and parsing/enrichment logic unchanged

**Step 4: Run test to verify it passes**

Run the same focused command.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/document_insights.py \
        tldw_Server_API/app/api/v1/endpoints/media/document_references.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        <focused_document_workspace_test_files>
git commit -m "refactor: move document workspace endpoints off compat reads"
```

### Task 7: Run Post-Tranche Verification

**Files:**
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Test: focused endpoint suites for item, listing, versions, document insights, and document references
- Test: any touched helper tests

**Step 1: Run focused pytest verification**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py <focused_endpoint_test_files>`

Expected: PASS

**Step 2: Run Bandit on the touched scope**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db/api.py tldw_Server_API/app/api/v1/endpoints/media/item.py tldw_Server_API/app/api/v1/endpoints/media/listing.py tldw_Server_API/app/api/v1/endpoints/media/versions.py tldw_Server_API/app/api/v1/endpoints/media/document_insights.py tldw_Server_API/app/api/v1/endpoints/media/document_references.py -f json -o /tmp/bandit_media_db_production_compat_reduction.json`

Expected: no new production-scope findings

**Step 3: Run diff and status checks**

Run:
`git diff --check`

Expected: clean

Run:
`git status --short --branch`

Expected: clean worktree on `codex/media-db-v2-stage1-caller-first`

**Step 4: Commit final verification-only fixes if needed**

```bash
git add <verification_fix_files>
git commit -m "test: fix media db production compat reduction regressions"
```
