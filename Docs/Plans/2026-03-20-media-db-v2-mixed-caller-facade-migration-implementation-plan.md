# Media DB V2 Mixed Caller Facade Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the next mixed cluster of production Media DB helper callers onto `media_db.api` by adding a `get_media_prompts` facade, migrating direct and lazy imports without changing their import timing, and rebinding `Media_Update_lib.py` aliases to the package seam.

**Architecture:** Keep extracted helper implementations unchanged and extend `media_db.api` with only the missing `get_media_prompts` facade. Migrate callers according to their current shape: direct module imports stay direct, lazy imports stay lazy, and `Media_Update_lib.py` keeps its local alias names. Use existing compat-binding and source-guard tests as the primary boundary checks.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Add The `get_media_prompts` API Facade

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add an API-surface test that patches the extracted helper and confirms the
package API delegates to it:

```python
def test_media_db_api_get_media_prompts_delegates_to_helper(monkeypatch) -> None:
    captured = {}

    def _fake_get_media_prompts(db_instance, media_id: int):
        captured["db_instance"] = db_instance
        captured["media_id"] = media_id
        return [{"id": 1, "prompt": "hello"}]

    monkeypatch.setattr(media_db_legacy_reads, "get_media_prompts", _fake_get_media_prompts)

    sentinel_db = object()
    result = media_db_api.get_media_prompts(sentinel_db, 12)

    assert captured == {"db_instance": sentinel_db, "media_id": 12}
    assert result == [{"id": 1, "prompt": "hello"}]
```

Also extend the tranche-facade exposure test to require `get_media_prompts`.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'get_media_prompts_delegates_to_helper or exposes_tranche_facades'`

Expected: FAIL because `media_db.api` does not expose `get_media_prompts` yet.

**Step 3: Write minimal implementation**

In `media_db.api`:

- add `get_media_prompts(db, media_id)` as a thin delegate to `legacy_reads`
- export it in `__all__`

Do not add optional parameters beyond `db` and `media_id`.

**Step 4: Run test to verify it passes**

Run the same focused command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "feat: add media db prompts facade"
```

### Task 2: Add Tranche-Scoped Guards And Binding Expectations

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_content_query_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py`

**Step 1: Write the failing tests**

Add or update source-guard coverage for exactly these files:

- `tldw_Server_API/app/api/v1/endpoints/slides.py`
- `tldw_Server_API/app/core/Chatbooks/chatbook_service.py`
- `tldw_Server_API/app/core/Embeddings/services/jobs_worker.py`
- `tldw_Server_API/app/api/v1/endpoints/items.py`
- `tldw_Server_API/app/api/v1/endpoints/outputs_templates.py`
- `tldw_Server_API/app/api/v1/endpoints/media_embeddings.py`
- `tldw_Server_API/app/core/Ingestion_Media_Processing/Media_Update_lib.py`

Forbid:

- `tldw_Server_API.app.core.DB_Management.media_db.legacy_reads`
- `tldw_Server_API.app.core.DB_Management.media_db.legacy_wrappers`
- `tldw_Server_API.app.core.DB_Management.media_db.legacy_content_queries`
- `tldw_Server_API.app.core.DB_Management.media_db.legacy_state`

only for the exact files that currently use each helper family.

Update the binding tests so these modules are now expected to bind to
`media_db.api`.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_content_query_imports.py tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py -k 'slides or chatbook or embeddings or outputs_templates or media_embeddings or media_update or items'`

Expected: FAIL on the selected tranche callers before any production change.

**Step 3: Write minimal implementation**

- Add only the new guard cases and expected binding changes.
- Do not touch production code yet.

**Step 4: Run test to verify it fails for the intended offenders**

Run the same command again.

Expected: FAIL only on the selected modules.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_content_query_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py
git commit -m "test: add mixed caller media db facade guards"
```

### Task 3: Migrate Direct Read Callers

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/slides.py`
- Modify: `tldw_Server_API/app/core/Chatbooks/chatbook_service.py`
- Test: `tldw_Server_API/tests/Slides/test_slides_api.py`
- Test: targeted chatbook tests that exercise transcript/prompt export paths

**Step 1: Write the failing test**

Use the updated source guards and compat-binding assertions so:

- `slides.py` binds `get_latest_transcription` from `media_db.api`
- `chatbook_service.py` binds `get_media_prompts` and `get_media_transcripts`
  from `media_db.api`

Keep module-local import seams intact.

**Step 2: Run test to verify it fails**

Run the Task 2 command filtered to `slides or chatbook`.

Then run focused behavior tests:

`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Slides/test_slides_api.py -k 'get_latest_transcription'`

Plus the chatbook-focused test subset you identify for media transcript/prompt
paths.

Expected: boundary/import tests fail before the code change.

**Step 3: Write minimal implementation**

In `slides.py`:

- replace `legacy_reads.get_latest_transcription` import with
  `media_db.api.get_latest_transcription`

In `chatbook_service.py`:

- keep the existing optional import block shape
- replace `legacy_reads.get_media_prompts` and
  `legacy_reads.get_media_transcripts` imports with `media_db.api`

Do not change any fallback `None` assignments in the exception block.

**Step 4: Run test to verify it passes**

Run the two commands from Step 2 again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/slides.py \
        tldw_Server_API/app/core/Chatbooks/chatbook_service.py
git commit -m "refactor: move direct media callers to media db api"
```

### Task 4: Migrate Lazy-Import Fallback Callers Without Changing Laziness

**Files:**
- Modify: `tldw_Server_API/app/core/Embeddings/services/jobs_worker.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/items.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/outputs_templates.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media_embeddings.py`
- Test: existing compat-binding tests
- Test: focused behavior tests covering fallback content/tag enrichment

**Step 1: Write the failing test**

Use the updated source guards and binding assertions so these callers are
expected to source helpers from `media_db.api`.

The test expectation is not “module attribute binding” for the lazy imports; it
is “source no longer imports `legacy_*` directly.”

**Step 2: Run test to verify it fails**

Run the Task 2 command filtered to:
`embeddings or outputs_templates or media_embeddings or items`

Then run the focused behavior tests that currently cover:

- `_media_row_to_item`
- `_build_items_context_from_media_ids`
- media embeddings document-version fallback
- embeddings worker content fallback

Expected: source/import tests fail before the code change.

**Step 3: Write minimal implementation**

In each target file:

- keep the import inside the current function
- change the import source from `legacy_wrappers` /
  `legacy_content_queries` to `media_db.api`

For example:

```python
from tldw_Server_API.app.core.DB_Management.media_db.api import (
    get_document_version,
    fetch_keywords_for_media,
)
```

Do not move these imports to module scope.

**Step 4: Run test to verify it passes**

Run the two commands from Step 2 again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Embeddings/services/jobs_worker.py \
        tldw_Server_API/app/api/v1/endpoints/items.py \
        tldw_Server_API/app/api/v1/endpoints/outputs_templates.py \
        tldw_Server_API/app/api/v1/endpoints/media_embeddings.py
git commit -m "refactor: move lazy media helper imports to media db api"
```

### Task 5: Rebind `Media_Update_lib.py` Aliases To `media_db.api`

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/Media_Update_lib.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing test**

Update the import-binding test so `Media_Update_lib.py` is expected to bind:

- `_check_media_exists` from `media_db.api.check_media_exists`
- `_get_document_version` from `media_db.api.get_document_version`

Keep the local alias names unchanged.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -k 'media_update or process_media_update'`

Expected: import-binding tests fail before the code change.

**Step 3: Write minimal implementation**

In `Media_Update_lib.py`:

- keep `_check_media_exists` and `_get_document_version`
- change their import source to `media_db.api`

Do not change the function bodies.

**Step 4: Run test to verify it passes**

Run the same command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Media_Processing/Media_Update_lib.py \
        tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
git commit -m "refactor: rebind media update helpers to media db api"
```

### Task 6: Run Tranche Verification And Boundary Checks

**Files:**
- No code changes expected unless verification fails

**Step 1: Run the focused tranche verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m pytest -q \
  tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_legacy_content_query_imports.py \
  tldw_Server_API/tests/DB_Management/test_media_db_media_update_imports.py \
  tldw_Server_API/tests/Slides/test_slides_api.py \
  tldw_Server_API/tests/Chatbooks \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py
```

Also run any caller-focused subsets used during Tasks 3-5 if the full set is too
slow or noisy.

**Step 2: Run security and diff checks**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && \
python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db/api.py \
  tldw_Server_API/app/api/v1/endpoints/slides.py \
  tldw_Server_API/app/core/Chatbooks/chatbook_service.py \
  tldw_Server_API/app/core/Embeddings/services/jobs_worker.py \
  tldw_Server_API/app/api/v1/endpoints/items.py \
  tldw_Server_API/app/api/v1/endpoints/outputs_templates.py \
  tldw_Server_API/app/api/v1/endpoints/media_embeddings.py \
  tldw_Server_API/app/core/Ingestion_Media_Processing/Media_Update_lib.py
```

Run:
`git diff --check`

Expected: no new Bandit findings in touched production files; diff check clean.

**Step 3: Commit if verification forced any fixes**

```bash
git add <touched files>
git commit -m "test: finish mixed media db caller facade migration"
```
