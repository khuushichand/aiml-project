# External File Hosting Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add version-aware bootstrap import and ongoing sync for Google Drive and Microsoft OneDrive using the existing connectors stack, Jobs execution model, and native `Media` / `DocumentVersions` persistence.

**Architecture:** Extend `External_Sources/` with a provider sync adapter contract and a shared sync coordinator. Evolve `external_items` into the canonical remote-to-media binding table, persist source-level cursors and run fences in the AuthNZ connector storage layer, run all sync work through the existing connectors Jobs worker using source-scoped idempotency, and reconcile remote content changes into atomic `Media` + `DocumentVersions` updates while archiving items on upstream removal.

**Tech Stack:** FastAPI, existing connectors OAuth services, JobManager, APScheduler, SQLite/PostgreSQL via existing connector service abstractions, Media DB v2, pytest, loguru

---

### Task 1: Add the sync adapter contract

**Files:**
- Create: `tldw_Server_API/app/core/External_Sources/sync_adapter.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connector_base.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Test: `tldw_Server_API/tests/External_Sources/test_sync_adapter_contract.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncChange


def test_file_sync_change_normalizes_required_fields():
    change = FileSyncChange(
        event_type="content_updated",
        remote_id="abc123",
        remote_name="report.pdf",
    )
    assert change.event_type == "content_updated"
    assert change.remote_id == "abc123"
    assert change.remote_name == "report.pdf"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_sync_adapter_contract.py
```

Expected: FAIL because `sync_adapter.py` and `FileSyncChange` do not exist yet.

**Step 3: Write minimal implementation**

Create:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FileSyncChange:
    event_type: str
    remote_id: str
    remote_name: str | None = None
    metadata: dict[str, Any] | None = None
```

Then add a protocol or base class for:

- `list_children`
- `list_changes`
- `get_item_metadata`
- `download_or_export`
- `resolve_shared_link`
- `subscribe_webhook`
- `renew_webhook`
- `revoke_webhook`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_sync_adapter_contract.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/sync_adapter.py \
        tldw_Server_API/app/core/External_Sources/connector_base.py \
        tldw_Server_API/app/core/External_Sources/connectors_service.py \
        tldw_Server_API/tests/External_Sources/test_sync_adapter_contract.py
git commit -m "feat(connectors): add file sync adapter contract"
```

### Task 2: Extend connector storage into canonical sync state and bindings

**Files:**
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Modify: `tldw_Server_API/app/core/External_Sources/README.md`
- Test: `tldw_Server_API/tests/External_Sources/test_connectors_sync_storage.py`

**Step 1: Write the failing test**

```python
async def test_external_items_upgrade_preserves_legacy_row_and_adds_binding_fields(db_backend):
    source_id = await create_test_source(db_backend)
    await upsert_source_sync_state(db_backend, source_id=source_id, sync_mode="hybrid")
    binding = await upsert_external_item_binding(
        db_backend,
        source_id=source_id,
        provider="drive",
        external_id="file-1",
        media_id=99,
        sync_status="active",
    )
    state = await get_source_sync_state(db_backend, source_id=source_id)
    assert binding["external_id"] == "file-1"
    assert state["sync_mode"] == "hybrid"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_sync_storage.py
```

Expected: FAIL because the new binding fields and sync-state helpers do not exist.

**Step 3: Write minimal implementation**

Add SQLite and PostgreSQL DDL and forward migrations for:

- `external_source_sync_state`
- new binding columns on `external_items`
- `external_item_events`

Implement service helpers for:

- `get_source_sync_state`
- `upsert_source_sync_state`
- `upsert_external_item_binding`
- `get_external_item_binding`
- `list_external_items_for_source`
- `record_item_event`
- `mark_external_item_archived`

Also implement a legacy-row upgrade path:

- preserve existing `external_items` data
- backfill new nullable columns
- mark sources `needs_full_rescan` when a safe `media_id` binding cannot be inferred

Keep these helpers in `connectors_service.py` until there is a clear need to split the module.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_sync_storage.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/connectors_service.py \
        tldw_Server_API/app/core/External_Sources/README.md \
        tldw_Server_API/tests/External_Sources/test_connectors_sync_storage.py
git commit -m "feat(connectors): extend connector sync storage"
```

### Task 3: Extend Google Drive to support file-hosting sync primitives

**Files:**
- Modify: `tldw_Server_API/app/core/External_Sources/google_drive.py`
- Modify: `tldw_Server_API/app/core/External_Sources/__init__.py`
- Test: `tldw_Server_API/tests/External_Sources/test_google_drive_sync_adapter.py`

**Step 1: Write the failing test**

```python
import pytest


@pytest.mark.asyncio
async def test_drive_changes_list_returns_normalized_page_token(fake_drive_connector):
    changes, next_cursor, cursor_hint = await fake_drive_connector.list_changes(
        account={"tokens": {"access_token": "token"}},
        cursor="start-token",
    )
    assert changes[0]["remote_id"] == "file-1"
    assert next_cursor == "page-2"
    assert cursor_hint == "new-start-token"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_google_drive_sync_adapter.py
```

Expected: FAIL because `list_changes` and related helpers do not exist.

**Step 3: Write minimal implementation**

Add Drive-specific methods for:

- `get_start_page_token`
- `list_changes`
- `get_item_metadata`
- `resolve_shared_link`
- `download_or_export`

Normalize Google change records into the shared contract using stable IDs, revision hints, hash, parent IDs, and deletion markers.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_google_drive_sync_adapter.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/google_drive.py \
        tldw_Server_API/app/core/External_Sources/__init__.py \
        tldw_Server_API/tests/External_Sources/test_google_drive_sync_adapter.py
git commit -m "feat(connectors): add google drive sync primitives"
```

### Task 4: Add the OneDrive connector and Graph delta support

**Files:**
- Create: `tldw_Server_API/app/core/External_Sources/onedrive.py`
- Modify: `tldw_Server_API/app/core/External_Sources/__init__.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/connectors.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/connectors.py`
- Test: `tldw_Server_API/tests/External_Sources/test_onedrive_connector.py`

**Step 1: Write the failing test**

```python
import pytest


@pytest.mark.asyncio
async def test_onedrive_delta_returns_drive_and_item_identity(fake_onedrive_connector):
    changes, next_cursor, delta_link = await fake_onedrive_connector.list_changes(
        account={"tokens": {"access_token": "token"}},
        cursor=None,
    )
    first = changes[0]
    assert first["remote_id"] == "item-1"
    assert first["metadata"]["drive_id"] == "drive-123"
    assert delta_link == "https://graph.microsoft.com/delta-token"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_onedrive_connector.py
```

Expected: FAIL because the connector does not exist yet and the API/schema do not accept `onedrive` or `file` sources.

**Step 3: Write minimal implementation**

Implement:

- OAuth authorize and token exchange
- token refresh
- browsing source items
- Graph delta support
- file metadata retrieval
- file download
- webhook subscription create, renew, and revoke helpers
- provider registration in connector endpoints
- schema expansion so providers include `onedrive`
- source schema expansion so file-hosting sources can use `type="file"`

Register the provider name in the connector registry.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_onedrive_connector.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/onedrive.py \
        tldw_Server_API/app/core/External_Sources/__init__.py \
        tldw_Server_API/app/core/External_Sources/connectors_service.py \
        tldw_Server_API/app/api/v1/endpoints/connectors.py \
        tldw_Server_API/app/api/v1/schemas/connectors.py \
        tldw_Server_API/tests/External_Sources/test_onedrive_connector.py
git commit -m "feat(connectors): add onedrive connector"
```

### Task 5: Build the shared sync coordinator and reconciliation logic

**Files:**
- Create: `tldw_Server_API/app/core/External_Sources/sync_coordinator.py`
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/Media_Update_lib.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Test: `tldw_Server_API/tests/External_Sources/test_sync_coordinator.py`

**Step 1: Write the failing test**

```python
def test_content_update_creates_new_document_version_for_existing_media(fake_sync_context):
    result = reconcile_change(
        change={"event_type": "content_updated", "remote_id": "file-1", "remote_revision": "r2"},
        context=fake_sync_context,
    )
    assert result.action == "version_created"
    assert result.media_id == 42
    assert result.current_version_number == 2
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_sync_coordinator.py
```

Expected: FAIL because `sync_coordinator.py` and reconciliation helpers do not exist.

**Step 3: Write minimal implementation**

Implement a coordinator that can:

- bootstrap import
- incremental sync from a stored cursor
- normalize per-provider change records
- detect content change vs metadata-only change
- create a new `DocumentVersion` for content updates
- archive local media for upstream deletion or permission loss
- keep the last good local version active when ingestion fails
- record per-item events and update binding state

For content updates, add or wrap a helper that atomically:

- updates `Media.content`
- updates `Media.content_hash`
- updates `Media.last_modified`
- increments `Media.version`
- refreshes `media_fts`
- creates the new `DocumentVersion`

Do not use `process_media_update()` as-is for this path. Reuse the existing full-update semantics already present in `Media_DB_v2` rather than inventing a second versioning behavior.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_sync_coordinator.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/External_Sources/sync_coordinator.py \
        tldw_Server_API/app/core/Ingestion_Media_Processing/Media_Update_lib.py \
        tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
        tldw_Server_API/app/core/External_Sources/connectors_service.py \
        tldw_Server_API/tests/External_Sources/test_sync_coordinator.py
git commit -m "feat(connectors): add shared file sync coordinator"
```

### Task 6: Add source-scoped sync enqueueing and worker fencing

**Files:**
- Modify: `tldw_Server_API/app/services/connectors_worker.py`
- Modify: `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- Test: `tldw_Server_API/tests/External_Sources/test_connectors_worker_file_sync.py`

**Step 1: Write the failing test**

```python
def test_duplicate_incremental_sync_submissions_share_idempotent_job_id():
    job1 = enqueue_source_sync_job(source_id=11, user_id=3, provider="drive", sync_kind="incremental_sync", cursor_hint="abc")
    job2 = enqueue_source_sync_job(source_id=11, user_id=3, provider="drive", sync_kind="incremental_sync", cursor_hint="abc")
    assert job1["id"] == job2["id"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_worker_file_sync.py
```

Expected: FAIL because the connector layer does not yet submit idempotent source-scoped sync jobs.

**Step 3: Write minimal implementation**

Add enqueue helpers that:

- derive a Jobs `idempotency_key` from `source_id`, `sync_kind`, and cursor or event identity
- store `active_job_id`, `active_run_token`, and lease metadata in `external_source_sync_state`
- prevent overlapping active sync runs for a single source

Then update the worker to:

- route `bootstrap_scan`, `incremental_sync`, `manual_resync`, `subscription_renewal`, and `repair_rescan`
- continue supporting existing import and Gmail behaviors
- renew job leases during long sync runs
- report processed, skipped, failed, and degraded counts in job results
- no-op safely when a stale or duplicate job loses the source fence

Keep provider-specific logic out of the worker; it should call the shared coordinator.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_worker_file_sync.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/connectors_worker.py \
        tldw_Server_API/app/core/External_Sources/connectors_service.py \
        tldw_Server_API/tests/External_Sources/test_connectors_worker_file_sync.py
git commit -m "feat(connectors): add source-scoped sync fencing"
```

### Task 7: Expose sync-aware API fields and manual triggers

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/connectors.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/connectors.py`
- Test: `tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py`

**Step 1: Write the failing test**

```python
def test_list_sources_includes_sync_state(client, auth_headers):
    response = client.get("/api/v1/connectors/sources", headers=auth_headers)
    body = response.json()
    assert "sync" in body["items"][0]
    assert "state" in body["items"][0]["sync"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py
```

Expected: FAIL because source responses do not include sync metadata yet.

**Step 3: Write minimal implementation**

Extend schemas and endpoints to:

- return source-level sync status
- expose last sync timestamps, webhook status, and degraded counts where available
- allow a manual sync trigger for file-hosting sources
- keep existing endpoints backward compatible for current connector consumers

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/connectors.py \
        tldw_Server_API/app/api/v1/schemas/connectors.py \
        tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py
git commit -m "feat(connectors): expose sync status in connectors api"
```

### Task 8: Add webhook ingress and subscription renewal

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/connectors.py`
- Modify: `tldw_Server_API/app/services/connectors_worker.py`
- Modify: `tldw_Server_API/app/core/External_Sources/google_drive.py`
- Modify: `tldw_Server_API/app/core/External_Sources/onedrive.py`
- Test: `tldw_Server_API/tests/External_Sources/test_connectors_webhooks.py`

**Step 1: Write the failing test**

```python
def test_webhook_callback_enqueues_incremental_sync_and_returns_fast(client, signed_webhook_headers):
    response = client.post(
        "/api/v1/connectors/providers/onedrive/webhook",
        headers=signed_webhook_headers,
        json={"value": [{"subscriptionId": "sub-1"}]},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_webhooks.py
```

Expected: FAIL because webhook endpoints and renewal behavior are not implemented.

**Step 3: Write minimal implementation**

Implement:

- provider webhook callback endpoints
- signature or subscription validation
- dedupe receipt storage in connector service
- queueing of `incremental_sync`
- `subscription_renewal` worker behavior for expiring subscriptions

Do not do content fetch or ingest in the request path.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources/test_connectors_webhooks.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/connectors.py \
        tldw_Server_API/app/services/connectors_worker.py \
        tldw_Server_API/app/core/External_Sources/google_drive.py \
        tldw_Server_API/app/core/External_Sources/onedrive.py \
        tldw_Server_API/tests/External_Sources/test_connectors_webhooks.py
git commit -m "feat(connectors): add webhook-triggered file sync"
```

### Task 9: Add end-to-end bootstrap and versioning integration tests

**Files:**
- Create: `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py`
- Modify: `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_versions_integration.py`
- Modify: `tldw_Server_API/tests/External_Sources/fixtures/`

**Step 1: Write the failing test**

```python
def test_drive_file_update_creates_new_document_version_for_same_media_id(client_with_auth, fake_drive_sync):
    source_id = create_drive_source(client_with_auth)
    run_bootstrap_sync(client_with_auth, source_id)
    media_id = fetch_bound_media_id(source_id, external_id="file-1")
    run_incremental_sync(client_with_auth, source_id, revision="r2")
    versions = list_versions(client_with_auth, media_id)
    assert len(versions) == 2
    assert versions[-1]["version_number"] == 2
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py
```

Expected: FAIL because the full flow is not wired together yet.

**Step 3: Write minimal implementation**

Fill in any missing test fixtures, endpoint wiring, or worker integration needed to make:

- bootstrap import
- incremental content update
- metadata-only update
- upstream delete to archive
- last-good-version preservation on ingest failure

work end-to-end through the real service boundaries.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py \
        tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_versions_integration.py \
        tldw_Server_API/tests/External_Sources/fixtures
git commit -m "test(connectors): cover external file sync versioning flow"
```

### Task 10: Verify, document, and harden the touched scope

**Files:**
- Modify: `Docs/API-related/Media_Ingest_Jobs_API.md`
- Modify: `Docs/Code_Documentation/Jobs_Module.md`
- Modify: `tldw_Server_API/app/core/External_Sources/README.md`

**Step 1: Write the failing doc and security checklist**

Create a checklist in your working notes with:

- touched tests to run
- docs to update
- bandit scope to scan
- any feature flags or env vars introduced

**Step 2: Run verification commands before finalizing**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/External_Sources \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_external_file_sync_integration.py \
  tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_versions_integration.py
```

Expected: PASS

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/External_Sources \
  tldw_Server_API/app/services/connectors_worker.py \
  tldw_Server_API/app/api/v1/endpoints/connectors.py \
  -f json -o /tmp/bandit_external_file_sync.json
```

Expected: JSON report written with no new high-severity findings in touched code.

**Step 3: Write minimal documentation updates**

Document:

- new sync-capable providers
- new source sync fields and job types
- webhook trigger behavior
- key env vars or feature flags

**Step 4: Re-run targeted tests after doc-safe code changes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/External_Sources
```

Expected: PASS

**Step 5: Commit**

```bash
git add Docs/API-related/Media_Ingest_Jobs_API.md \
        Docs/Code_Documentation/Jobs_Module.md \
        tldw_Server_API/app/core/External_Sources/README.md
git commit -m "docs(connectors): document external file sync"
```
