# Reference Manager Import Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend and connector API foundation for collection-linked reference-manager imports with a generic adapter seam, Zotero as the first provider, import-mode sync, strong dedupe, and normalized bibliographic metadata.

**Architecture:** Extend `External_Sources` with a dedicated `ReferenceManagerAdapter` family instead of forcing scholarly-library items through the existing file-sync adapter contract. Reuse the current external account/source tables, scheduler, and Jobs worker, but add reference-item storage, Zotero normalization, and dedupe helpers specialized for bibliographic imports. This plan intentionally stops at backend/API completion because the current `/connectors` web routes are placeholders; a separate UI plan should consume the stabilized backend contract afterward.

**Tech Stack:** FastAPI, Pydantic, AuthNZ DB pool, Media DB v2, APScheduler, Jobs, Loguru, pytest, httpx/TestClient, Bandit

---

## Scope Lock

Before implementation starts, keep these planning decisions fixed:

- v1 provider surface is `zotero` only
- the abstraction is generic so `mendeley` can be added later without redesigning storage or worker flow
- linked sources are `collection` sources only
- v1 collection traversal is **flat, not recursive**
- child collections must be linked separately in v1
- sync is **import mode**
- upstream edits or deletes do not rewrite or remove local media by default
- annotation/highlight sync is out of scope
- write-back is out of scope

## Canonical V1 Bibliographic Field Map

Every imported or dedupe-linked scholarly item should normalize into this `safe_metadata` shape:

```python
{
    "provider": "zotero",
    "import_mode": "reference_manager",
    "provider_item_key": "ABCD1234",
    "provider_library_id": "123456",
    "collection_key": "COLL1234",
    "collection_name": "Language Models",
    "source_url": "https://www.zotero.org/users/123456/items/ABCD1234",
    "doi": "10.1000/example",
    "title": "Attention Is All You Need",
    "authors": "Ashish Vaswani, Noam Shazeer, ...",
    "publication_date": "2017-06-12",
    "year": "2017",
    "journal": "NeurIPS",
    "abstract": "..."
}
```

Only these fields are canonical in v1. Do not add provider-specific metadata blobs to `safe_metadata` beyond what is needed for debugging or durable identity.

## File Structure

- `tldw_Server_API/app/core/External_Sources/reference_manager_adapter.py`
  Purpose: define the provider-agnostic scholarly-library protocol used by workers and endpoints.
- `tldw_Server_API/app/core/External_Sources/reference_manager_types.py`
  Purpose: define normalized collection, attachment, and reference-item dataclasses for provider-neutral processing.
- `tldw_Server_API/app/core/External_Sources/reference_manager_dedupe.py`
  Purpose: centralize strict-first dedupe ranking and canonical metadata fingerprint generation.
- `tldw_Server_API/app/core/External_Sources/reference_manager_import.py`
  Purpose: orchestrate reference-item enumeration, attachment selection, dedupe decisions, and Media DB import payload generation.
- `tldw_Server_API/app/core/External_Sources/zotero.py`
  Purpose: implement Zotero OAuth, collection listing, flat item listing, attachment discovery, and normalized item mapping.
- `tldw_Server_API/app/core/External_Sources/__init__.py`
  Purpose: export the new adapter/types and register the Zotero connector.
- `tldw_Server_API/app/core/External_Sources/connectors_service.py`
  Purpose: extend provider family constants, create storage for reference-item sync state, and expose helper functions used by endpoints and workers.
- `tldw_Server_API/app/core/External_Sources/policy.py`
  Purpose: allow org policy evaluation to reason about `zotero` as an enabled provider without assuming file-path constraints.
- `tldw_Server_API/app/core/External_Sources/README.md`
  Purpose: document the new reference-manager family, flat collection semantics, and import-mode behavior.
- `tldw_Server_API/app/core/Utils/metadata_utils.py`
  Purpose: reuse and, if needed, extend the worker-safe `normalize_safe_metadata(...)` and `update_version_safe_metadata_in_transaction(...)` helpers instead of routing metadata merges through HTTP endpoints.
- `tldw_Server_API/app/api/v1/schemas/connectors.py`
  Purpose: extend provider, source-type, and sync-summary schemas for reference-manager collections and duplicate/metadata-only counts.
- `tldw_Server_API/app/api/v1/endpoints/connectors.py`
  Purpose: expose Zotero in provider discovery, collection browsing, source creation, and source status endpoints while rejecting unsupported recursive semantics.
- `tldw_Server_API/app/services/connectors_sync_scheduler.py`
  Purpose: enqueue poll-based incremental sync for reference-manager sources.
- `tldw_Server_API/app/services/connectors_worker.py`
  Purpose: branch import jobs by provider family and execute import-mode reference-manager sync without destructive replay.
- `tldw_Server_API/tests/External_Sources/test_reference_manager_contract.py`
  Purpose: lock the generic provider contract and normalized dataclass invariants.
- `tldw_Server_API/tests/External_Sources/test_reference_manager_storage.py`
  Purpose: verify table creation and CRUD helpers for reference-item bindings, cursors, and result counters.
- `tldw_Server_API/tests/External_Sources/test_reference_manager_dedupe.py`
  Purpose: verify DOI-first dedupe ranking, metadata fingerprint conservatism, and metadata enrichment guardrails.
- `tldw_Server_API/tests/External_Sources/test_zotero_connector.py`
  Purpose: verify collection listing, flat item listing, attachment selection, and normalized bibliographic mapping.
- `tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py`
  Purpose: extend the current connector API coverage for Zotero provider listing, collection source creation, and validation errors.
- `tldw_Server_API/tests/External_Sources/test_connectors_sync_scheduler.py`
  Purpose: verify scheduler enqueue behavior for poll-based Zotero sources.
- `tldw_Server_API/tests/External_Sources/test_connectors_worker_reference_sync.py`
  Purpose: verify worker import-mode sync, dedupe outcomes, cursor advancement, and metadata-only skips.
- `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_reference_import_integration.py`
  Purpose: verify end-to-end import into Media DB with stable `safe_metadata` and no destructive replay on duplicate or changed upstream items.

## Stages

### Stage 1: Generic Contract And Storage

**Goal:** Add the provider-neutral reference-manager contract, normalized types, and storage primitives needed for collection-linked scholarly imports.

**Success Criteria:** The backend can persist reference-item sync rows, expose a stable normalized item shape, and recognize `zotero` as a connector provider without yet running real imports.

**Tests:** `python -m pytest tldw_Server_API/tests/External_Sources/test_reference_manager_contract.py tldw_Server_API/tests/External_Sources/test_reference_manager_storage.py -v`

**Status:** Complete

### Stage 2: Zotero Adapter And Dedupe Core

**Goal:** Implement the first concrete provider plus the shared dedupe logic.

**Success Criteria:** Zotero collections and items can be normalized into the canonical bibliographic field map, and dedupe ranking produces deterministic match reasons.

**Tests:** `python -m pytest tldw_Server_API/tests/External_Sources/test_zotero_connector.py tldw_Server_API/tests/External_Sources/test_reference_manager_dedupe.py -v`

**Status:** Complete

### Stage 3: Connector API Surface

**Goal:** Expose Zotero through the existing connectors endpoints and source-creation flow.

**Success Criteria:** Clients can discover the provider, browse collections, create flat collection sources, and retrieve source status with duplicate and metadata-only counters.

**Tests:** `python -m pytest tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py -v`

**Status:** Complete

### Stage 4: Scheduled Import-Mode Sync

**Goal:** Add scheduler and worker execution for reference-manager imports without destructive replay.

**Success Criteria:** Poll-based jobs enumerate new reference items, dedupe them, import new attachments into Media DB, record metadata-only skips, and advance cursors.

**Tests:** `python -m pytest tldw_Server_API/tests/External_Sources/test_connectors_sync_scheduler.py tldw_Server_API/tests/External_Sources/test_connectors_worker_reference_sync.py tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_reference_import_integration.py -v`

**Status:** Complete

### Stage 5: Documentation And Security Verification

**Goal:** Document the new connector family and confirm the touched backend scope does not introduce new Bandit findings.

**Success Criteria:** The README reflects Zotero-first import-mode behavior, targeted tests pass, and Bandit reports zero new findings in the touched scope.

**Tests:** `python -m bandit -r tldw_Server_API/app/core/External_Sources/reference_manager_adapter.py tldw_Server_API/app/core/External_Sources/reference_manager_types.py tldw_Server_API/app/core/External_Sources/reference_manager_dedupe.py tldw_Server_API/app/core/External_Sources/reference_manager_import.py tldw_Server_API/app/core/External_Sources/zotero.py tldw_Server_API/app/core/External_Sources/connectors_service.py tldw_Server_API/app/api/v1/endpoints/connectors.py tldw_Server_API/app/services/connectors_worker.py tldw_Server_API/app/services/connectors_sync_scheduler.py -f json -o /tmp/bandit_reference_manager_import_sync.json`

**Status:** Complete

## Task 1: Add The Generic Reference-Manager Contract And Sync Storage

**Files:**
- Create: `tldw_Server_API/app/core/External_Sources/reference_manager_adapter.py`
- Create: `tldw_Server_API/app/core/External_Sources/reference_manager_types.py`
- Modify: `tldw_Server_API/app/core/External_Sources/__init__.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/connectors.py`
- Test: `tldw_Server_API/tests/External_Sources/test_reference_manager_contract.py`
- Test: `tldw_Server_API/tests/External_Sources/test_reference_manager_storage.py`

- [x] **Step 1: Write the failing contract and storage tests**

Add tests that prove:

1. a `ReferenceManagerAdapter` protocol exists
2. normalized collection and reference-item dataclasses expose the canonical v1 fields
3. connector schemas allow `provider="zotero"` and `type="collection"`
4. a new reference-item storage table can persist provider item identity, collection identity, match reason, and import timestamps
5. reference-manager sources are flat by default and do not depend on recursive file traversal

Use concrete assertions like:

```python
item = NormalizedReferenceItem(
    provider="zotero",
    provider_item_key="ABCD1234",
    provider_library_id="123456",
    collection_key="COLL1234",
    collection_name="Language Models",
    doi="10.1000/example",
    title="Attention Is All You Need",
    authors="Ashish Vaswani, Noam Shazeer",
    publication_date="2017-06-12",
    year="2017",
    journal="NeurIPS",
    abstract="...",
    source_url="https://www.zotero.org/users/123456/items/ABCD1234",
    attachments=[],
)
assert item.collection_name == "Language Models"
assert item.doi == "10.1000/example"
```

```python
payload = ConnectorSourceCreateRequest(
    account_id=1,
    provider="zotero",
    remote_id="COLL1234",
    type="collection",
    options={},
)
assert payload.type == "collection"
```

- [x] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/External_Sources/test_reference_manager_contract.py \
  tldw_Server_API/tests/External_Sources/test_reference_manager_storage.py \
  -v
```

Expected: FAIL because the protocol, normalized types, provider literal, and reference-item storage helpers do not exist yet.

- [x] **Step 3: Implement the minimal contract and storage layer**

Make the smallest backend changes that establish the new family:

- define `ReferenceManagerAdapter` with collection/item/attachment methods
- define `NormalizedReferenceCollection`, `ReferenceAttachmentCandidate`, and `NormalizedReferenceItem`
- extend connector schema literals for `zotero` and `collection`
- add `REFERENCE_MANAGER_PROVIDERS = frozenset({"zotero"})`
- add a new `external_reference_items` table plus helper CRUD in `connectors_service.py`
- keep storage provider-neutral even though only Zotero ships now

Keep the storage boring and explicit:

```python
async def upsert_reference_item_binding(
    db,
    *,
    source_id: int,
    provider: str,
    provider_item_key: str,
    provider_library_id: str | None,
    collection_key: str | None,
    provider_version: str | None,
    provider_updated_at: str | None,
    media_id: int | None,
    dedupe_match_reason: str | None,
    raw_reference_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    ...
```

- [x] **Step 4: Re-run the targeted tests**

Run the same pytest command from Step 2.

Expected: PASS with the new protocol, schema support, and storage helpers in place.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/reference_manager_adapter.py \
  tldw_Server_API/app/core/External_Sources/reference_manager_types.py \
  tldw_Server_API/app/core/External_Sources/__init__.py \
  tldw_Server_API/app/core/External_Sources/connectors_service.py \
  tldw_Server_API/app/api/v1/schemas/connectors.py \
  tldw_Server_API/tests/External_Sources/test_reference_manager_contract.py \
  tldw_Server_API/tests/External_Sources/test_reference_manager_storage.py
git commit -m "feat: add reference manager connector contracts"
```

## Task 2: Implement Zotero Normalization And Shared Dedupe Ranking

**Files:**
- Create: `tldw_Server_API/app/core/External_Sources/zotero.py`
- Create: `tldw_Server_API/app/core/External_Sources/reference_manager_dedupe.py`
- Modify: `tldw_Server_API/app/core/External_Sources/__init__.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Test: `tldw_Server_API/tests/External_Sources/test_zotero_connector.py`
- Test: `tldw_Server_API/tests/External_Sources/test_reference_manager_dedupe.py`

- [x] **Step 1: Write the failing Zotero and dedupe tests**

Add tests that prove:

1. Zotero collection browsing returns collection records, not file-like rows
2. Zotero item listing is flat for a selected collection in v1
3. attachment selection prefers importable PDFs and falls back to no-attachment metadata records cleanly
4. dedupe ranking order is `same_provider_item -> doi -> file_hash -> metadata_fingerprint`
5. metadata fingerprint matching is conservative and does not merge similar but distinct titles

Use focused assertions like:

```python
match = rank_reference_item_match(
    normalized_item,
    same_provider_item=None,
    doi_match={"media_id": 77},
    hash_match=None,
    metadata_match={"media_id": 99},
)
assert match.reason == "doi"
assert match.media_id == 77
```

```python
item = await ZoteroConnector(...).normalize_reference_item(raw_item, raw_attachments)
assert item.provider == "zotero"
assert item.collection_key == "COLL1234"
assert item.attachments[0].mime_type == "application/pdf"
```

- [x] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/External_Sources/test_zotero_connector.py \
  tldw_Server_API/tests/External_Sources/test_reference_manager_dedupe.py \
  -v
```

Expected: FAIL because no Zotero adapter or bibliographic dedupe helper exists yet.

- [x] **Step 3: Implement the Zotero adapter and dedupe helper**

Add the first real provider and its matching logic:

- implement OAuth-specific Zotero connector methods
- implement collection listing and flat collection item listing
- map Zotero payloads into the canonical v1 field map
- emit attachment descriptors separately from bibliographic identity
- implement strict-first dedupe ranking and metadata fingerprint generation
- expose a helper that returns both `match_reason` and optional `metadata_patch`

Keep the fingerprint logic explicit:

```python
def build_metadata_fingerprint(
    *,
    title: str | None,
    authors: str | None,
    year: str | None,
) -> str | None:
    normalized_title = normalize_title(title)
    first_author = normalize_first_author(authors)
    if not normalized_title or not first_author or not year:
        return None
    return f"{normalized_title}|{first_author}|{year}"
```

- [x] **Step 4: Re-run the targeted tests**

Run the same pytest command from Step 2.

Expected: PASS with deterministic normalized Zotero items and conservative dedupe ranking.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/zotero.py \
  tldw_Server_API/app/core/External_Sources/reference_manager_dedupe.py \
  tldw_Server_API/app/core/External_Sources/__init__.py \
  tldw_Server_API/app/core/External_Sources/connectors_service.py \
  tldw_Server_API/tests/External_Sources/test_zotero_connector.py \
  tldw_Server_API/tests/External_Sources/test_reference_manager_dedupe.py
git commit -m "feat: add zotero reference manager adapter"
```

## Task 3: Expose Zotero Collection Sources Through The Connectors API

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/connectors.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/connectors.py`
- Modify: `tldw_Server_API/app/core/External_Sources/policy.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Test: `tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py`
- Test: `tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py`

- [x] **Step 1: Write the failing connector API tests**

Add tests that prove:

1. `GET /api/v1/connectors/providers` includes `zotero`
2. `POST /api/v1/connectors/providers/zotero/authorize` returns an OAuth URL and state
3. `GET /api/v1/connectors/providers/zotero/callback` accepts a valid state and creates an account row
4. the browse flow returns collection-shaped rows for Zotero
5. `POST /api/v1/connectors/sources` accepts `provider="zotero"` and `type="collection"`
6. recursive source options are rejected for Zotero with a clear 4xx message
7. source sync summaries include reference-manager counts like `duplicate_count` and `metadata_only_count`

Example assertions:

```python
response = client.get("/api/v1/connectors/providers", headers=headers)
names = {item["name"] for item in response.json()}
assert "zotero" in names
```

```python
payload = {
    "account_id": 7,
    "provider": "zotero",
    "remote_id": "COLL1234",
    "type": "collection",
    "options": {"recursive": True},
}
response = client.post("/api/v1/connectors/sources", json=payload, headers=headers)
assert response.status_code == 422
assert "flat" in response.text.lower()
```

- [x] **Step 2: Run the targeted connector API tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py \
  tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py \
  -v
```

Expected: FAIL because the provider catalog, browse flow, source validation, and sync summary do not yet understand Zotero collections.

- [x] **Step 3: Implement the minimal endpoint and schema support**

Add the smallest API surface that makes the provider usable:

- include Zotero in provider discovery
- support authorize/callback through the existing generic connector OAuth flow
- let the existing browse flow return normalized collection rows for Zotero
- allow source creation for `type="collection"`
- reject `recursive=True` for Zotero with a clear validation error
- extend sync summary models and serializers with reference-manager counters
- keep current Drive/OneDrive behavior unchanged

Be explicit about the validation rule:

```python
if provider == "zotero" and bool(options.get("recursive")):
    raise HTTPException(
        status_code=422,
        detail="Zotero collection sync is flat in v1; link child collections separately.",
    )
```

- [x] **Step 4: Re-run the targeted connector API tests**

Run the same pytest command from Step 2.

Expected: PASS with a working Zotero connector contract at the API layer.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/connectors.py \
  tldw_Server_API/app/api/v1/endpoints/connectors.py \
  tldw_Server_API/app/core/External_Sources/policy.py \
  tldw_Server_API/app/core/External_Sources/connectors_service.py \
  tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py \
  tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py
git commit -m "feat: expose zotero collection sources in connectors api"
```

## Task 4: Add Import-Mode Reference Sync To The Scheduler And Worker

**Files:**
- Modify: `tldw_Server_API/app/core/External_Sources/reference_manager_adapter.py`
- Create: `tldw_Server_API/app/core/External_Sources/reference_manager_import.py`
- Modify: `tldw_Server_API/app/core/External_Sources/zotero.py`
- Modify: `tldw_Server_API/app/core/Utils/metadata_utils.py`
- Modify: `tldw_Server_API/app/services/connectors_sync_scheduler.py`
- Modify: `tldw_Server_API/app/services/connectors_worker.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Test: `tldw_Server_API/tests/External_Sources/test_reference_manager_contract.py`
- Test: `tldw_Server_API/tests/External_Sources/test_connectors_sync_scheduler.py`
- Test: `tldw_Server_API/tests/External_Sources/test_connectors_worker_reference_sync.py`
- Test: `tldw_Server_API/tests/External_Sources/test_zotero_connector.py`
- Test: `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_reference_import_integration.py`

- [x] **Step 1: Write the failing scheduler, worker, and integration tests**

Add tests that prove:

1. the scheduler enqueues incremental sync for enabled Zotero collection sources
2. the worker enumerates normalized reference items using the new provider family
3. a new paper imports into Media DB with the canonical `safe_metadata`
4. a DOI duplicate records a reference binding and optional metadata enrichment, but does not create a second media record
5. metadata-only records increment `metadata_only_count`
6. upstream edits do not rewrite local content in v1

Use concrete expectations like:

```python
assert result["processed"] == 1
assert result["duplicates"] == 1
assert result["metadata_only"] == 1
assert sync_state["cursor"] == "version-42"
```

```python
latest = get_document_version(media_db, media_id, 1)
assert latest["safe_metadata"]["provider"] == "zotero"
assert latest["safe_metadata"]["doi"] == "10.1000/example"
assert latest["safe_metadata"]["collection_key"] == "COLL1234"
```

- [x] **Step 2: Run the targeted sync tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/External_Sources/test_connectors_sync_scheduler.py \
  tldw_Server_API/tests/External_Sources/test_connectors_worker_reference_sync.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_reference_import_integration.py \
  -v
```

Expected: FAIL because the scheduler and worker are still hard-wired to file-centric import logic.

- [x] **Step 3: Implement import-mode reference-manager sync**

Build the smallest execution path that works end to end:

- teach the scheduler to enqueue poll-based sync for `REFERENCE_MANAGER_PROVIDERS`
- move reference-item enumeration and attachment selection into `reference_manager_import.py`
- branch `_process_import_job()` by provider family
- resolve and download selected attachments through the `ReferenceManagerAdapter` contract
- on new item:
  - select the best importable attachment
  - ingest into Media DB
  - write canonical `safe_metadata`
  - persist the reference-item binding row
- on duplicate:
  - bind the provider item to the existing media record
  - merge only missing canonical metadata fields using `normalize_safe_metadata(...)` and `update_version_safe_metadata_in_transaction(...)`
  - do not overwrite text, title, or versions by default
- on no attachment:
  - persist a metadata-only result row
  - do not fake a successful media import
- persist cursor and source counters

Keep the import-mode guard explicit:

```python
if dedupe_result.matched_media_id is not None:
    await upsert_reference_item_binding(..., media_id=dedupe_result.matched_media_id, dedupe_match_reason=dedupe_result.reason)
    if dedupe_result.metadata_patch:
        await merge_missing_safe_metadata(...)
    return "duplicate"
```

- [x] **Step 4: Re-run the targeted sync tests**

Run the same pytest command from Step 2.

Expected: PASS with scheduler enqueue, worker import, duplicate linking, metadata-only skips, and non-destructive import-mode behavior.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/reference_manager_import.py \
  tldw_Server_API/app/core/Utils/metadata_utils.py \
  tldw_Server_API/app/services/connectors_sync_scheduler.py \
  tldw_Server_API/app/services/connectors_worker.py \
  tldw_Server_API/app/core/External_Sources/connectors_service.py \
  tldw_Server_API/tests/External_Sources/test_connectors_sync_scheduler.py \
  tldw_Server_API/tests/External_Sources/test_connectors_worker_reference_sync.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_reference_import_integration.py
git commit -m "feat: add reference manager import sync worker"
```

## Task 5: Document The New Connector Family And Run Final Verification

**Files:**
- Modify: `tldw_Server_API/app/core/External_Sources/README.md`

- [x] **Step 1: Write the failing documentation and verification checklist**

Add a short checklist section to the README update task that requires documentation to mention:

1. Zotero is the only shipped provider in v1
2. collection sync is flat
3. import mode is non-destructive
4. duplicate and metadata-only counts are surfaced in sync status

Use a direct checklist in the plan execution notes:

```markdown
- [ ] README says child collections must be linked separately
- [ ] README says upstream deletes do not remove local items in v1
```

- [x] **Step 2: Run the full targeted verification suite**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/External_Sources/test_reference_manager_contract.py \
  tldw_Server_API/tests/External_Sources/test_reference_manager_storage.py \
  tldw_Server_API/tests/External_Sources/test_reference_manager_dedupe.py \
  tldw_Server_API/tests/External_Sources/test_zotero_connector.py \
  tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py \
  tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py \
  tldw_Server_API/tests/External_Sources/test_connectors_sync_scheduler.py \
  tldw_Server_API/tests/External_Sources/test_connectors_worker_reference_sync.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_reference_import_integration.py \
  -v
```

Expected: PASS with the entire reference-manager backend slice green.

- [x] **Step 3: Update docs and run Bandit on the touched backend scope**

Document the new behavior in `External_Sources/README.md`, then run:

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/core/External_Sources/reference_manager_adapter.py \
  tldw_Server_API/app/core/External_Sources/reference_manager_types.py \
  tldw_Server_API/app/core/External_Sources/reference_manager_dedupe.py \
  tldw_Server_API/app/core/External_Sources/reference_manager_import.py \
  tldw_Server_API/app/core/External_Sources/zotero.py \
  tldw_Server_API/app/core/External_Sources/connectors_service.py \
  tldw_Server_API/app/api/v1/endpoints/connectors.py \
  tldw_Server_API/app/services/connectors_worker.py \
  tldw_Server_API/app/services/connectors_sync_scheduler.py \
  -f json -o /tmp/bandit_reference_manager_import_sync.json
```

Expected: JSON report written to `/tmp/bandit_reference_manager_import_sync.json` with zero new findings in the touched scope.

- [x] **Step 4: Review the final scoped diff before closing**

Run:

```bash
git status --short
git diff --stat
```

Expected: the scoped diff for the reference-manager slice matches the planned backend files, tests, and docs, even if the wider repository is already dirty.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/README.md
git commit -m "fix: finalize reference manager import sync verification"
```

## Follow-On Plan, Not Part Of This Tranche

The current `/connectors` and `/connectors/*` web routes in `apps/tldw-frontend/pages/connectors/` are placeholders. After this backend/API slice is stable, write a separate plan for:

- account linking UX
- collection picker UX
- source status table
- duplicate and metadata-only counters in the web client
- workspace affordances for imported scholarly metadata
