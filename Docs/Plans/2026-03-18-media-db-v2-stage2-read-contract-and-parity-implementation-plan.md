# Media DB V2 Stage 2 Read Contract And Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the canonical Media DB read surface from `Media_DB_v2`, delegate legacy read methods to that extracted contract, migrate current read callers, and prove the read contract across SQLite and Postgres.

**Architecture:** Keep request-scoped DB dependencies unchanged and build the new read surface as package-level `media_db` functions/services that accept the existing `MediaDbLike` / `MediaDbSession`. Implement lookup, search, version reads, and rich details under focused repositories/services, then make `Media_DB_v2` delegate to them before migrating callers. Validate behavior through a backend-neutral contract suite that runs on SQLite and Postgres, with heavier Postgres RLS checks kept separate.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, PostgreSQL, Loguru

---

### Task 1: Introduce The Public Read Contract And Read Protocol

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/validation.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add API surface and boundary tests:

```python
def test_media_db_api_exposes_read_contract_functions() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api

    assert callable(media_db_api.get_media_by_id)
    assert callable(media_db_api.get_media_by_uuid)
    assert callable(media_db_api.search_media)
    assert callable(media_db_api.list_document_versions)


def test_db_deps_still_returns_media_db_session() -> None:
    import inspect
    from tldw_Server_API.app.api.v1.API_Deps import DB_Deps

    assert "MediaDbSession" in inspect.getsource(DB_Deps)
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'read_contract_functions or db_deps_still_returns_media_db_session'`

Expected: FAIL because the new read contract functions do not exist yet.

**Step 3: Write the minimal implementation**

- Expand `media_db/api.py` with package-level read functions that accept a DB handle:
  - `get_media_by_id`
  - `get_media_by_uuid`
  - `search_media`
  - `list_document_versions`
  - `get_full_media_details`
  - `get_full_media_details_rich`
- Add a narrow `MediaDbReadLike` protocol to `runtime/validation.py` that captures
  the DB/session capabilities the new read layer actually requires.
- Do not change `DB_Deps.py`.

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'read_contract_functions or db_deps_still_returns_media_db_session'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/validation.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "refactor: add media db read contract surface"
```

### Task 2: Extract Lookup And Version Reads, Then Delegate The Shim

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/media_lookup_repository.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/repositories/document_versions_repository.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/legacy_wrappers.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/versions.py`
- Test: `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py`

**Step 1: Write the failing tests**

Add/extend tests that prove the repository owns version listing and the shim delegates:

```python
def test_document_versions_repository_lists_versions(memory_db_factory):
    from tldw_Server_API.app.core.DB_Management.media_db.repositories.document_versions_repository import (
        DocumentVersionsRepository,
    )

    db = memory_db_factory("version_repo")
    repo = DocumentVersionsRepository.from_legacy_db(db)
    assert repo.list(media_id=1, include_content=False, include_deleted=False) == []


def test_media_db_v2_get_media_by_id_delegates(monkeypatch, memory_db_factory):
    db = memory_db_factory("delegate_lookup")
    called = {}

    def _fake_get_media_by_id(_db, media_id, **kwargs):
        called["media_id"] = media_id
        return {"id": media_id}

    monkeypatch.setattr(
        "tldw_Server_API.app.core.DB_Management.media_db.api.get_media_by_id",
        _fake_get_media_by_id,
    )

    assert db.get_media_by_id(9) == {"id": 9}
    assert called["media_id"] == 9
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/MediaDB2/test_sqlite_db.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py -k 'delegates or repository_lists_versions'`

Expected: FAIL because the repository list path and delegation do not exist yet.

**Step 3: Write the minimal implementation**

- Create `media_lookup_repository.py` with canonical `by_id` / `by_uuid` helpers.
- Expand `DocumentVersionsRepository` with a `list(...)` method for paged version reads.
- Rewire `media_db/api.py` read functions to use the repositories.
- Rewire `legacy_wrappers.get_document_version(...)` to use the repository path.
- Replace version-listing SQL in `media/versions.py` with the repository-backed API.
- Make `Media_DB_v2.get_media_by_id`, `get_media_by_uuid`, and `get_all_document_versions`
  delegate to `media_db.api`.

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/MediaDB2/test_sqlite_db.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py -k 'get_media_by_id or get_media_by_uuid or versions'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/repositories/media_lookup_repository.py \
        tldw_Server_API/app/core/DB_Management/media_db/repositories/document_versions_repository.py \
        tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/app/core/DB_Management/media_db/legacy_wrappers.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/app/api/v1/endpoints/media/versions.py \
        tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
        tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py
git commit -m "refactor: extract media lookup and version reads"
```

### Task 3: Extract Search As A Canonical Read Service And Add Parity Contracts

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/media_search_repository.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Create: `tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py`
- Create: `tldw_Server_API/tests/MediaDB2/test_read_contract_postgres.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py`

**Step 1: Write the failing tests**

Create contract tests for search parity, including scope-sensitive behavior:

```python
def test_search_media_contract_filters_personal_vs_team_visibility(sqlite_media_db):
    rows, total = search_media(
        sqlite_media_db,
        search_query="shared",
        page=1,
        results_per_page=10,
    )
    assert total >= 0


@pytest.mark.postgres
def test_search_media_contract_matches_postgres_shape(postgres_media_db):
    rows, total = search_media(
        postgres_media_db,
        search_query="shared",
        page=1,
        results_per_page=10,
    )
    assert isinstance(rows, list)
    assert isinstance(total, int)
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py tldw_Server_API/tests/MediaDB2/test_read_contract_postgres.py -k 'search_media_contract'`

Expected: FAIL because the canonical search repository/contract does not exist yet.

**Step 3: Write the minimal implementation**

- Extract `search_media_db` behavior into `media_search_repository.py`.
- Preserve the existing `(rows, total)` contract.
- Preserve SQLite visibility filtering via scope context.
- Preserve Postgres behavior through the same public contract while relying on
  backend RLS where appropriate.
- Make `media_db.api.search_media(...)` delegate to the repository.
- Make `Media_DB_v2.search_media_db(...)` a thin delegate.

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py tldw_Server_API/tests/MediaDB2/test_read_contract_postgres.py tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py -k 'search_media_contract or rls_enforces_scope_postgres'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/repositories/media_search_repository.py \
        tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py \
        tldw_Server_API/tests/MediaDB2/test_read_contract_postgres.py \
        tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py
git commit -m "refactor: extract media search read contract"
```

### Task 4: Extract Rich Details And Migrate Production Read Callers

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/services/media_details_service.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/legacy_media_details.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/item.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/listing.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/items.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/outputs_templates.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/vector_stores_openai.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media_embeddings.py`
- Modify: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py`
- Modify: `tldw_Server_API/app/core/Chatbooks/chatbook_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/media_module.py`
- Modify: `tldw_Server_API/app/core/Data_Tables/jobs_worker.py`
- Modify: `tldw_Server_API/app/core/Embeddings/services/jobs_worker.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py`
- Test: `tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py`

**Step 1: Write the failing tests**

Add migration guards for the key production callers:

```python
def test_media_item_endpoint_uses_media_db_read_contract_in_source() -> None:
    from pathlib import Path

    source = Path("tldw_Server_API/app/api/v1/endpoints/media/item.py").read_text(encoding="utf-8")
    assert "get_full_media_details_rich(" not in source
    assert "get_full_media_details_rich2(" not in source


def test_mcp_media_module_uses_media_db_read_contract_in_source() -> None:
    from pathlib import Path

    source = Path("tldw_Server_API/app/core/MCP_unified/modules/implementations/media_module.py").read_text(encoding="utf-8")
    assert ".search_media_db(" not in source
    assert ".get_media_by_id(" not in source
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'uses_media_db_read_contract_in_source'`

Expected: FAIL because callers still use legacy read methods/wrappers.

**Step 3: Write the minimal implementation**

- Create `media_details_service.py` and move rich-detail assembly there.
- Make `legacy_media_details.py` delegate to the service.
- Make `DB_Manager.get_full_media_details*` remain a thin compat shell.
- Migrate the listed production callers to use `media_db.api` read functions
  while keeping the existing DB/session dependency injection unchanged.
- Keep test-double churn low by using function signatures that still accept the
  DB/session handle directly.

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py -k 'media_db_read_contract or media_item or versions or retrieval'`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/services/media_details_service.py \
        tldw_Server_API/app/core/DB_Management/media_db/legacy_media_details.py \
        tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/app/api/v1/endpoints/media/item.py \
        tldw_Server_API/app/api/v1/endpoints/media/listing.py \
        tldw_Server_API/app/api/v1/endpoints/items.py \
        tldw_Server_API/app/api/v1/endpoints/outputs_templates.py \
        tldw_Server_API/app/api/v1/endpoints/vector_stores_openai.py \
        tldw_Server_API/app/api/v1/endpoints/media_embeddings.py \
        tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py \
        tldw_Server_API/app/core/Chatbooks/chatbook_service.py \
        tldw_Server_API/app/core/MCP_unified/modules/implementations/media_module.py \
        tldw_Server_API/app/core/Data_Tables/jobs_worker.py \
        tldw_Server_API/app/core/Embeddings/services/jobs_worker.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py \
        tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py \
        tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py
git commit -m "refactor: migrate media read callers to extracted contract"
```

### Task 5: Harden Postgres Runtime Validation And Run Final Verification

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/runtime/factory.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

**Step 1: Write the failing tests**

Add explicit runtime-validation tests:

```python
def test_validate_postgres_content_backend_reports_schema_mismatch(monkeypatch):
    ...


def test_validate_postgres_content_backend_reports_missing_policy(monkeypatch):
    ...
```

Add final source-boundary checks for caller migration where helpful.

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py -k 'validate_postgres_content_backend or read_contract_in_source'`

Expected: FAIL until runtime validation and final guards are updated.

**Step 3: Write the minimal implementation**

- Tighten `runtime/factory.py` validation around:
  - missing backend
  - schema version mismatch
  - required RLS policy absence
- Ensure failure messages are deterministic and specific.
- Finalize Stage 2 boundary guards in `test_media_db_api_imports.py`.

**Step 4: Run full verification**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py tldw_Server_API/tests/MediaDB2/test_sqlite_db.py tldw_Server_API/tests/MediaDB2/test_read_contract_sqlite.py tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py tldw_Server_API/tests/MediaDB2/test_read_contract_postgres.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_versions.py tldw_Server_API/app/core/MCP_unified/tests/test_media_retrieval.py`

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/media_db tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/app/core/DB_Management/DB_Manager.py -f json -o /tmp/bandit_media_db_stage2.json`

Expected:
- pytest PASS
- Bandit reports no new production-file findings in touched code

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/runtime/factory.py \
        tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py \
        tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py
git commit -m "test: harden media db read parity and postgres validation"
```
