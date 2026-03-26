# Media DB V2 Bundled Read-Helper Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the remaining production read-helper caller cluster onto `media_db.api` by adding a narrow `get_media_transcripts` facade and migrating `navigation`, `quiz_source_resolver`, `data_tables.jobs_worker`, and `media_module` off direct compat helper imports.

**Architecture:** Keep the extracted helper implementations unchanged and expose them through `media_db.api`. Migrate each caller to import helper names from that package surface while preserving module-local patchpoints used by tests. Treat the `media_module` delete-path import as an explicit, tested sub-step rather than incidental cleanup.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Add The Narrow `get_media_transcripts` API Facade

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing test**

Add an API-surface test that patches the extracted read helper and confirms the
package API delegates to it:

```python
def test_media_db_api_get_media_transcripts_delegates_to_helper(monkeypatch) -> None:
    captured = {}

    def _fake_get_media_transcripts(db_instance, media_id: int):
        captured["db_instance"] = db_instance
        captured["media_id"] = media_id
        return [{"id": 1, "media_id": media_id}]

    monkeypatch.setattr(legacy_reads, "get_media_transcripts", _fake_get_media_transcripts)

    sentinel_db = object()
    result = media_db_api.get_media_transcripts(sentinel_db, 12)

    assert captured == {"db_instance": sentinel_db, "media_id": 12}
    assert result == [{"id": 1, "media_id": 12}]
```

Also extend the facade-exposure test to require `get_media_transcripts`.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'get_media_transcripts_delegates_to_helper or exposes_tranche_facades'`

Expected: FAIL because `media_db.api` does not expose `get_media_transcripts`
yet.

**Step 3: Write minimal implementation**

In `media_db.api`:

- import or reuse `legacy_reads`
- add `get_media_transcripts(db, media_id)` as a thin delegate
- export it in `__all__`

Do not add optional parameters beyond `db` and `media_id`.

**Step 4: Run test to verify it passes**

Run the same focused command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "feat: add media db transcript facade"
```

### Task 2: Add Tranche-Scoped Guards For The Bundled Caller Slice

**Files:**
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add source-guard coverage for exactly these files:

- `tldw_Server_API/app/api/v1/endpoints/media/navigation.py`
- `tldw_Server_API/app/services/quiz_source_resolver.py`
- `tldw_Server_API/app/core/Data_Tables/jobs_worker.py`
- `tldw_Server_API/app/core/MCP_unified/modules/implementations/media_module.py`

Forbid:

- `tldw_Server_API.app.core.DB_Management.media_db.legacy_reads`
- `tldw_Server_API.app.core.DB_Management.media_db.legacy_wrappers`
- `tldw_Server_API.app.core.DB_Management.media_db.legacy_maintenance`
  only for `media_module.py`

Do not include `app/api/v1/endpoints/media/__init__.py`.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'selected_media_endpoint_sources_no_longer_import_compat_helpers or navigation or quiz_source_resolver or data_tables_jobs_worker or media_module'`

Expected: FAIL because the selected files still import compat helpers directly.

**Step 3: Write minimal implementation**

- Add only the new guard cases.
- Do not touch production code yet.

**Step 4: Run test to verify it fails for the intended offenders**

Run the same command again.

Expected: FAIL only on the selected modules.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "test: add bundled read-helper caller guards"
```

### Task 3: Migrate `quiz_source_resolver.py` And `data_tables.jobs_worker.py`

**Files:**
- Modify: `tldw_Server_API/app/services/quiz_source_resolver.py`
- Modify: `tldw_Server_API/app/core/Data_Tables/jobs_worker.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py`
- Test: `tldw_Server_API/tests/DataTables/test_data_tables_worker.py`

**Step 1: Write the failing test**

Use the new source guards from Task 2 and update the dedicated compat-import
tests so these modules are expected to bind to `media_db.api`, not
`legacy_reads` or `legacy_wrappers`.

Keep module-local monkeypatch seams intact. The tests should still patch:

- `resolver_mod.get_latest_transcription`
- `jobs_worker.get_document_version`
- `jobs_worker.get_latest_transcription`

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py -k 'quiz_source_resolver or data_tables_jobs_worker'`

Then run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py tldw_Server_API/tests/DataTables/test_data_tables_worker.py -k 'latest_transcription or extract_media_text'`

Expected: source/import tests fail before the code change.

**Step 3: Write minimal implementation**

In `quiz_source_resolver.py`:

- replace `legacy_reads.get_latest_transcription` import with
  `media_db.api.get_latest_transcription`

In `jobs_worker.py`:

- replace `legacy_reads.get_latest_transcription` import with
  `media_db.api.get_latest_transcription`
- replace `legacy_wrappers.get_document_version` import with
  `media_db.api.get_document_version`

Import the helper names directly into module scope to preserve monkeypatch
patchpoints.

**Step 4: Run test to verify it passes**

Run the two commands from Step 2 again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/quiz_source_resolver.py \
        tldw_Server_API/app/core/Data_Tables/jobs_worker.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py \
        tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py \
        tldw_Server_API/tests/DataTables/test_data_tables_worker.py
git commit -m "refactor: move quiz and data tables read helpers to media db api"
```

### Task 4: Migrate `navigation.py`

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/navigation.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py`
- Test: `tldw_Server_API/tests/Media/test_media_navigation_content.py`
- Test: navigation endpoint tests discovered under `tldw_Server_API/tests/Media/`

**Step 1: Write the failing test**

Use the source guard plus compat-import assertions so `navigation.py` is
expected to bind:

- `get_document_version` from `media_db.api`
- `get_latest_transcription` from `media_db.api`
- `get_media_transcripts` from `media_db.api`

Keep existing behavior tests patching `navigation_mod.get_document_version`
directly.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py -k 'navigation'`

Then run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Media/test_media_navigation_content.py`

Expected: import-boundary tests fail before the code change.

**Step 3: Write minimal implementation**

In `navigation.py`:

- replace direct imports from `legacy_reads` and `legacy_wrappers` with direct
  imports from `media_db.api`
- update stale call sites that still pass `db_instance=...`
- keep the local `MediaNavigationDb` protocol unchanged

Do not redesign navigation contracts or move package-level exports in
`media/__init__.py`.

**Step 4: Run test to verify it passes**

Run the two commands from Step 2 again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/navigation.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py \
        tldw_Server_API/tests/Media/test_media_navigation_content.py
git commit -m "refactor: move navigation read helpers to media db api"
```

### Task 5: Migrate `media_module.py`, Including Delete Wiring

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/media_module.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py`
- Test: `tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py`

**Step 1: Write the failing test**

Extend import/binding tests so `media_module.py` is expected to bind:

- `get_document_version` from `media_db.api`
- `get_latest_transcription` from `media_db.api`
- `get_media_transcripts` from `media_db.api`
- `permanently_delete_item` from `media_db.api`

Also keep the MCP retrieval tests that monkeypatch module-local helper names.

**Step 2: Run test to verify it fails**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py -k 'media_module'`

Then run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py -k 'get_transcript or get_media_metadata or media_get_includes_description or delete_media_permanent_requires_admin'`

Expected: import-boundary tests fail before the code change.

**Step 3: Write minimal implementation**

In `media_module.py`:

- replace `legacy_reads` imports with `media_db.api`
- replace `legacy_wrappers.get_document_version` import with `media_db.api`
- replace `legacy_maintenance.permanently_delete_item` import with `media_db.api`

Keep helper names imported directly into module scope so the MCP tests can still
patch `media_module_impl.get_*` and `media_module_impl.permanently_delete_item`.

**Step 4: Run test to verify it passes**

Run the two commands from Step 2 again.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/modules/implementations/media_module.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py \
        tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py \
        tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py
git commit -m "refactor: move mcp media helpers to media db api"
```

### Task 6: Verify The Full Bundled Slice

**Files:**
- Verify only

**Step 1: Run the focused bundled test suite**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_reads_imports.py tldw_Server_API/tests/DB_Management/test_media_db_legacy_document_version_imports.py tldw_Server_API/tests/Media/test_media_navigation_content.py tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py tldw_Server_API/tests/DataTables/test_data_tables_worker.py tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py -k 'navigation or quiz_source_resolver or data_tables_jobs_worker or media_module or get_media_transcripts or latest_transcription or get_document_version or delete_media_permanent_requires_admin'`

Expected: PASS

**Step 2: Run Bandit on the touched production files**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db/api.py tldw_Server_API/app/api/v1/endpoints/media/navigation.py tldw_Server_API/app/services/quiz_source_resolver.py tldw_Server_API/app/core/Data_Tables/jobs_worker.py tldw_Server_API/app/core/MCP_unified/modules/implementations/media_module.py -f json`

Expected: no production-scope findings

**Step 3: Run diff hygiene checks**

Run:
`git diff --check`

Expected: no output

**Step 4: Commit the verification-safe end state**

```bash
git status --short --branch
```

Expected: clean worktree after the task commits above
