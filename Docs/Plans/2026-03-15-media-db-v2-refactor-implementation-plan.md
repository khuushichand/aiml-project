# Media DB v2 Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the `Media_DB_v2.py` god file with a request-safe `media_db` package for core media persistence while keeping SQLite and Postgres behavior working through an incremental migration.

**Architecture:** Introduce a request-scoped `MediaDbSession` and a `media_db` package with runtime, schema, repository, and query modules. Keep `Media_DB_v2.py` as a temporary compatibility shim while `DB_Deps.py`, `DB_Manager.py`, and the core media callers migrate to the new API in narrow, test-driven slices.

**Tech Stack:** Python 3.11+, FastAPI dependencies, SQLite, PostgreSQL backend abstraction, pytest, loguru, Bandit

---

## Preflight

- Use a dedicated git worktree before implementation. The current planning session did not create one.
- Activate the project environment before every command:

```bash
source .venv/bin/activate
```

- Keep phase 1 limited to:
  - request-scoped session/factory wiring
  - runtime extraction
  - core schema extraction
  - repositories for media, document versions, chunks, keywords, media files
  - query modules for media details, transcripts, prompts, and keyword aggregation
- Do not migrate claims, outputs, audiobook persistence, or TTS history in this first pass. Leave them behind the compatibility shim until phase 2.

### Task 1: Lock Request-Scoped Session Behavior

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/__init__.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/__init__.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/session.py`
- Modify: `tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.DB_Management.media_db.api import MediaDbFactory


def test_factory_returns_distinct_sessions_for_distinct_scopes():
    factory = MediaDbFactory.for_sqlite_path(":memory:", client_id="scope-test")

    first = factory.for_request(org_id=10, team_id=20)
    second = factory.for_request(org_id=11, team_id=21)

    assert first is not second
    assert (first.org_id, first.team_id) == (10, 20)
    assert (second.org_id, second.team_id) == (11, 21)


def test_cached_factory_does_not_mutate_existing_session_scope():
    factory = MediaDbFactory.for_sqlite_path(":memory:", client_id="scope-test")

    first = factory.for_request(org_id=1, team_id=2)
    _ = factory.for_request(org_id=3, team_id=4)

    assert (first.org_id, first.team_id) == (1, 2)
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py -v
```

Expected: FAIL with import errors for `media_db.api` / `MediaDbFactory`.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass(slots=True)
class MediaDbSession:
    db_path: str
    client_id: str
    org_id: int | None = None
    team_id: int | None = None


@dataclass(slots=True)
class MediaDbFactory:
    db_path: str
    client_id: str

    @classmethod
    def for_sqlite_path(cls, db_path: str, client_id: str) -> "MediaDbFactory":
        return cls(db_path=db_path, client_id=client_id)

    def for_request(self, *, org_id: int | None, team_id: int | None) -> MediaDbSession:
        return MediaDbSession(
            db_path=self.db_path,
            client_id=self.client_id,
            org_id=org_id,
            team_id=team_id,
        )
```

Then update `DB_Deps.py` so the cache stores factories or backend providers, not request-mutated `MediaDatabase` instances.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py \
        tldw_Server_API/app/core/DB_Management/media_db/__init__.py \
        tldw_Server_API/app/core/DB_Management/media_db/api.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/__init__.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/session.py \
        tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py
git commit -m "test: lock request scoped media db sessions"
```

### Task 2: Extract Shared Errors And Runtime Primitives

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/errors.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/execution.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/runtime/rows.py`
- Create: `tldw_Server_API/tests/DB_Management/unit/test_media_db_runtime_session.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py`
- Test: `tldw_Server_API/tests/DB_Management/unit/test_media_db_runtime_session.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.DB_Management.media_db.runtime.rows import RowAdapter


def test_row_adapter_supports_index_and_key_access():
    row = RowAdapter({"id": 7, "title": "Doc"}, [("id",), ("title",)])
    assert row[0] == 7
    assert row["title"] == "Doc"
```

Add a second test proving the extracted execution helper closes ephemeral SQLite connections on failure instead of leaking them.

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/unit/test_media_db_runtime_session.py \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py -v
```

Expected: FAIL because the runtime modules do not exist yet.

**Step 3: Write minimal implementation**

```python
class DatabaseError(Exception):
    pass


class SchemaError(DatabaseError):
    pass


class InputError(ValueError):
    pass


class ConflictError(DatabaseError):
    pass
```

```python
class RowAdapter:
    def __init__(self, row_dict: dict[str, object], description: list[tuple] | None = None):
        self._data = row_dict
        self._cols = [entry[0] for entry in (description or []) if entry]

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._cols[key]]
        return self._data[key]
```

Move equivalent logic out of `Media_DB_v2.py` into the new runtime modules, then make `Media_DB_v2.py` import and use those extracted definitions.

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/unit/test_media_db_runtime_session.py \
  tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/errors.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/execution.py \
        tldw_Server_API/app/core/DB_Management/media_db/runtime/rows.py \
        tldw_Server_API/tests/DB_Management/unit/test_media_db_runtime_session.py \
        tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: extract media db runtime primitives"
```

### Task 3: Extract Core Schema Bootstrap Without Creating New Schema God Files

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/__init__.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/bootstrap.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/features/__init__.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/features/core_media.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/features/fts.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/features/policies.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/__init__.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres.py`
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`
- Test: `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.DB_Management.media_db.schema.bootstrap import ensure_media_schema


def test_ensure_media_schema_creates_core_tables(memory_db_factory):
    db = memory_db_factory("schema-core")
    ensure_media_schema(db)
    row = db.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Media'"
    ).fetchone()
    assert row is not None
```

Add a Postgres-side test asserting the bootstrap path delegates to the backend installer instead of embedding all logic in one function.

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py -v
```

Expected: FAIL because the bootstrap modules do not exist.

**Step 3: Write minimal implementation**

```python
def ensure_media_schema(db) -> None:
    if db.backend_type.value == "postgresql":
        ensure_postgres_core_media(db)
        ensure_postgres_fts(db)
        ensure_postgres_policies(db)
        return
    ensure_sqlite_core_media(db)
    ensure_sqlite_fts(db)
```

Move only core-media schema and FTS setup in this task. Leave claims, outputs, and TTS-history schema wiring inside the compatibility shim for later.

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py -v
```

Expected: PASS for the migrated core schema coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/schema \
        tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
        tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
        tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: extract media db core schema bootstrap"
```

### Task 4: Extract Low-Coupling Repositories First

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/__init__.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/keywords_repository.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/media_files_repository.py`
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_keywords_repository.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_media_files.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_keywords_repository.py`
- Test: `tldw_Server_API/tests/MediaDB2/test_media_files.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.DB_Management.media_db.repositories.keywords_repository import KeywordsRepository


def test_keywords_repository_replaces_keyword_set(memory_db_factory):
    db = memory_db_factory("keywords-repo")
    repo = KeywordsRepository.from_legacy_db(db)
    media_id, _, _ = db.add_media_with_keywords(title="Doc", media_type="text", content="body", keywords=["old"])

    repo.replace_keywords(media_id, ["x", "y"])

    assert set(repo.fetch_for_media(media_id)) == {"x", "y"}
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_keywords_repository.py \
  tldw_Server_API/tests/MediaDB2/test_media_files.py -v
```

Expected: FAIL with missing repository imports.

**Step 3: Write minimal implementation**

```python
class KeywordsRepository:
    def __init__(self, session):
        self.session = session

    @classmethod
    def from_legacy_db(cls, db):
        return cls(session=db)

    def fetch_for_media(self, media_id: int) -> list[str]:
        return fetch_keywords_for_media(media_id=media_id, db_instance=self.session)

    def replace_keywords(self, media_id: int, keywords: list[str]) -> None:
        self.session.update_keywords_for_media(media_id, keywords)
```

Do the same for `MediaFilesRepository`, then update `Media_DB_v2.py` to delegate instead of owning the logic inline.

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_keywords_repository.py \
  tldw_Server_API/tests/MediaDB2/test_media_files.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/repositories/__init__.py \
        tldw_Server_API/app/core/DB_Management/media_db/repositories/keywords_repository.py \
        tldw_Server_API/app/core/DB_Management/media_db/repositories/media_files_repository.py \
        tldw_Server_API/tests/DB_Management/test_media_db_keywords_repository.py \
        tldw_Server_API/tests/MediaDB2/test_media_files.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: extract media keyword and file repositories"
```

### Task 5: Extract Core Media, Document Version, And Chunk Repositories

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/media_repository.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/document_versions_repository.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/repositories/chunks_repository.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
- Test: `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
- Test: `tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_repository import MediaRepository


def test_media_repository_creates_media_row(memory_db_factory):
    db = memory_db_factory("media-repo")
    repo = MediaRepository.from_legacy_db(db)

    media_id, media_uuid, _ = repo.add_text_media(
        title="Repo doc",
        content="hello",
        media_type="text",
    )

    assert isinstance(media_id, int)
    assert isinstance(media_uuid, str)
```

Add companion tests for:

- latest document version retrieval
- batched chunk insertion
- Postgres execution path parity for repository methods

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -v
```

Expected: FAIL because the repositories do not exist.

**Step 3: Write minimal implementation**

```python
class MediaRepository:
    def __init__(self, session):
        self.session = session

    @classmethod
    def from_legacy_db(cls, db):
        return cls(session=db)

    def add_text_media(self, *, title: str, content: str, media_type: str = "text"):
        return self.session.add_media_with_keywords(
            title=title,
            media_type=media_type,
            content=content,
            keywords=[],
        )
```

Extract analogous wrappers for document versions and chunks, then collapse duplicated SQL in `Media_DB_v2.py` by delegating to those repositories.

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py -v
```

Expected: PASS for the migrated repository coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/repositories/media_repository.py \
        tldw_Server_API/app/core/DB_Management/media_db/repositories/document_versions_repository.py \
        tldw_Server_API/app/core/DB_Management/media_db/repositories/chunks_repository.py \
        tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
        tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py \
        tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: extract media document and chunk repositories"
```

### Task 6: Extract Read Queries For Media Details, Transcripts, Prompts, And Keywords

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/media_db/queries/__init__.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/queries/media_details_query.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/queries/transcripts_query.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/queries/prompts_query.py`
- Create: `tldw_Server_API/app/core/DB_Management/media_db/queries/keywords_query.py`
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_query_contracts.py`
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_transcripts_upsert.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_query_contracts.py`
- Test: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_transcripts_upsert.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.DB_Management.media_db.queries.media_details_query import MediaDetailsQuery


def test_media_details_query_returns_media_latest_version_and_keywords(memory_db_factory):
    db = memory_db_factory("details-query")
    media_id, _, _ = db.add_media_with_keywords(
        title="Query doc",
        media_type="text",
        content="body",
        keywords=["alpha"],
    )

    result = MediaDetailsQuery.from_legacy_db(db).fetch(media_id, include_content=True)

    assert result["media"]["id"] == media_id
    assert result["latest_version"]["version_number"] == 1
    assert result["keywords"] == ["alpha"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_query_contracts.py \
  tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
  tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py \
  tldw_Server_API/tests/DB_Management/test_media_transcripts_upsert.py -v
```

Expected: FAIL because the query modules do not exist.

**Step 3: Write minimal implementation**

```python
class MediaDetailsQuery:
    def __init__(self, media_repo, versions_repo, keywords_repo):
        self.media_repo = media_repo
        self.versions_repo = versions_repo
        self.keywords_repo = keywords_repo

    def fetch(self, media_id: int, *, include_content: bool) -> dict[str, object] | None:
        media = self.media_repo.get_by_id(media_id)
        if not media:
            return None
        return {
            "media": media,
            "latest_version": self.versions_repo.get_latest(media_id, include_content=include_content),
            "keywords": self.keywords_repo.fetch_for_media(media_id),
        }
```

Then update `DB_Manager.py` to call the new query modules instead of importing bulk helper functions from `Media_DB_v2.py`.

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_query_contracts.py \
  tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
  tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py \
  tldw_Server_API/tests/DB_Management/test_media_transcripts_upsert.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db/queries/__init__.py \
        tldw_Server_API/app/core/DB_Management/media_db/queries/media_details_query.py \
        tldw_Server_API/app/core/DB_Management/media_db/queries/transcripts_query.py \
        tldw_Server_API/app/core/DB_Management/media_db/queries/prompts_query.py \
        tldw_Server_API/app/core/DB_Management/media_db/queries/keywords_query.py \
        tldw_Server_API/tests/DB_Management/test_media_db_query_contracts.py \
        tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
        tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py \
        tldw_Server_API/tests/DB_Management/test_media_transcripts_upsert.py \
        tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: route media read helpers through query modules"
```

### Task 7: Migrate High-Value Callers And Reduce The Shim Surface

**Files:**
- Modify: `tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py`
- Modify: `tldw_Server_API/app/core/DB_Management/DB_Manager.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/document_references.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/item.py`
- Modify: `tldw_Server_API/app/services/quiz_source_resolver.py`
- Modify: `tldw_Server_API/app/services/storage_cleanup_service.py`
- Modify: `tldw_Server_API/app/services/media_files_cleanup_service.py`
- Modify: `tldw_Server_API/tests/Media/test_document_references.py`
- Modify: `tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py`
- Modify: `tldw_Server_API/tests/Media/test_document_outline.py`
- Modify: `tldw_Server_API/tests/Media/test_document_insights.py`
- Modify: `tldw_Server_API/tests/Media/test_media_navigation_content.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Test: `tldw_Server_API/tests/Media/test_document_references.py`
- Test: `tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py`
- Test: `tldw_Server_API/tests/Media/test_document_outline.py`
- Test: `tldw_Server_API/tests/Media/test_document_insights.py`
- Test: `tldw_Server_API/tests/Media/test_media_navigation_content.py`

**Step 1: Write the failing tests**

Add or tighten assertions proving:

- callers depend on `media_db/api.py` or the request-scoped session factory
- `DB_Deps.py` yields request-scoped handles, not cached mutable DB instances
- the migrated endpoints still accept dependency overrides cleanly

Example:

```python
def test_get_media_db_for_user_yields_request_scoped_handle(...):
    handle_one = ...
    handle_two = ...
    assert handle_one is not handle_two
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Media/test_document_references.py \
  tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py \
  tldw_Server_API/tests/Media/test_document_outline.py \
  tldw_Server_API/tests/Media/test_document_insights.py \
  tldw_Server_API/tests/Media/test_media_navigation_content.py -v
```

Expected: FAIL where callers still rely on the legacy object shape or import path.

**Step 3: Write minimal implementation**

```python
from tldw_Server_API.app.core.DB_Management.media_db.api import get_media_db_factory


def _resolve_media_db_for_user(current_user):
    factory = get_media_db_factory(current_user.id)
    scope = get_scope()
    return factory.for_request(
        org_id=getattr(scope, "effective_org_id", None),
        team_id=getattr(scope, "effective_team_id", None),
    )
```

Leave any unmigrated legacy methods in `Media_DB_v2.py` as explicit shim delegates with comments marking them phase-2 debt.

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Media/test_document_references.py \
  tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py \
  tldw_Server_API/tests/Media/test_document_outline.py \
  tldw_Server_API/tests/Media/test_document_insights.py \
  tldw_Server_API/tests/Media/test_media_navigation_content.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py \
        tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/app/api/v1/endpoints/media/document_references.py \
        tldw_Server_API/app/api/v1/endpoints/media/item.py \
        tldw_Server_API/app/services/quiz_source_resolver.py \
        tldw_Server_API/app/services/storage_cleanup_service.py \
        tldw_Server_API/app/services/media_files_cleanup_service.py \
        tldw_Server_API/tests/Media/test_document_references.py \
        tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py \
        tldw_Server_API/tests/Media/test_document_outline.py \
        tldw_Server_API/tests/Media/test_document_insights.py \
        tldw_Server_API/tests/Media/test_media_navigation_content.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py
git commit -m "refactor: migrate core media callers to request scoped api"
```

### Task 8: Verification, Security Scan, And Shim Audit

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/app/core/DB_Management/media_db/api.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_db_manager_config_behavior.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_content_backend_cache.py`
- Test: `tldw_Server_API/tests/DB_Management/test_db_manager_config_behavior.py`
- Test: `tldw_Server_API/tests/DB_Management/test_content_backend_cache.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
- Test: `tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py`
- Test: `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`

**Step 1: Write the failing tests**

Add assertions that:

- `DB_Manager.py` no longer bulk-imports core read helpers from `Media_DB_v2.py`
- the content backend cache still behaves correctly with the new factory/session split
- the compatibility shim exposes only the unmigrated legacy surface

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_db_manager_config_behavior.py \
  tldw_Server_API/tests/DB_Management/test_content_backend_cache.py \
  tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py -v
```

Expected: FAIL until shim/API cleanup is complete.

**Step 3: Write minimal implementation**

Remove migrated helper imports from `DB_Manager.py`, narrow `Media_DB_v2.py` to compatibility exports only, and keep an explicit TODO ledger in comments for deferred domains:

- claims
- outputs
- audiobook persistence
- TTS history

**Step 4: Run full verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py \
  tldw_Server_API/tests/DB_Management/test_db_manager_config_behavior.py \
  tldw_Server_API/tests/DB_Management/test_content_backend_cache.py \
  tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py \
  tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_support.py \
  tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py \
  tldw_Server_API/tests/DB_Management/test_media_transcripts_upsert.py \
  tldw_Server_API/tests/MediaDB2/test_sqlite_db.py \
  tldw_Server_API/tests/MediaDB2/test_media_db_postgres.py \
  tldw_Server_API/tests/Media/test_document_references.py \
  tldw_Server_API/tests/Media/test_media_reprocess_endpoint.py -v
```

Expected: PASS.

Run Bandit on the touched scope:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/DB_Management/media_db \
  tldw_Server_API/app/core/DB_Management/DB_Manager.py \
  tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py \
  -f json -o /tmp/bandit_media_db_refactor.json
```

Expected: no new findings in changed code.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/media_db \
        tldw_Server_API/app/core/DB_Management/DB_Manager.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py \
        tldw_Server_API/tests/DB_Management/test_db_manager_config_behavior.py \
        tldw_Server_API/tests/DB_Management/test_content_backend_cache.py
git commit -m "refactor: finalize media db phase one package split"
```

## Notes For The Implementer

- Keep each extraction slice small enough to revert independently.
- Do not move claims or TTS-history code into the new package during phase 1 unless a failing test proves the dependency is unavoidable.
- When legacy helpers remain in `Media_DB_v2.py`, make them explicit delegates with a comment pointing to the replacement repository or query module.
- Prefer adapting existing tests over inventing new end-to-end coverage unless a gap is real and local.
- If a migration slice reveals hidden coupling after three failed approaches, stop and write down the blocker before widening scope.

