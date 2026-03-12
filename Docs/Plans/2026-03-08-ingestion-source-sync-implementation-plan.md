# Ingestion Source Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a generic ingestion-source sync system for local directories and archive snapshots, with selectable `media` and `notes` sinks, safe local-path handling, archive refresh diffing, and Jobs-based execution.

**Architecture:** Add a new `Ingestion_Sources` core package that owns source definitions, snapshot building, diffing, sink routing, and source-state persistence. Reuse the repo's established Jobs and scheduler patterns for execution, keep source identity immutable after first successful sync, and treat the Notes sink as latest-state sync with `sync_managed` / `detached` semantics instead of promising historical note revisions.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL via existing DB abstractions, APScheduler enqueue patterns, core Jobs manager, existing Media ingestion/document extraction code, existing Notes DB layer, pytest, Bandit.

---

### Task 1: Create the Ingestion Sources Core Package and Persistence Contract

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/__init__.py`
- Create: `tldw_Server_API/app/core/Ingestion_Sources/models.py`
- Create: `tldw_Server_API/app/core/Ingestion_Sources/service.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_models_and_service_contract.py`
- Modify: `tldw_Server_API/app/core/exceptions.py`

**Step 1: Write the failing test**

```python
def test_create_source_normalizes_enums_and_defaults():
    from tldw_Server_API.app.core.Ingestion_Sources.service import normalize_source_payload

    payload = normalize_source_payload(
        {
            "source_type": "local_directory",
            "sink_type": "media",
            "policy": "canonical",
            "enabled": None,
        }
    )

    assert payload["source_type"] == "local_directory"
    assert payload["sink_type"] == "media"
    assert payload["policy"] == "canonical"
    assert payload["enabled"] is True
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_models_and_service_contract.py::test_create_source_normalizes_enums_and_defaults -v
```

Expected: FAIL with import error because `Ingestion_Sources` does not exist yet.

**Step 3: Write minimal implementation**

```python
SOURCE_TYPES = {"local_directory", "archive_snapshot"}
SINK_TYPES = {"media", "notes"}
SOURCE_POLICIES = {"canonical", "import_only"}

def normalize_source_payload(data: dict[str, object]) -> dict[str, object]:
    source_type = str(data.get("source_type") or "").strip().lower()
    sink_type = str(data.get("sink_type") or "").strip().lower()
    policy = str(data.get("policy") or "canonical").strip().lower()
    if source_type not in SOURCE_TYPES:
        raise ValueError("unsupported source_type")
    if sink_type not in SINK_TYPES:
        raise ValueError("unsupported sink_type")
    if policy not in SOURCE_POLICIES:
        raise ValueError("unsupported policy")
    return {
        "source_type": source_type,
        "sink_type": sink_type,
        "policy": policy,
        "enabled": True if data.get("enabled") is None else bool(data.get("enabled")),
    }
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_models_and_service_contract.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/__init__.py \
        tldw_Server_API/app/core/Ingestion_Sources/models.py \
        tldw_Server_API/app/core/Ingestion_Sources/service.py \
        tldw_Server_API/tests/Ingestion_Sources/test_models_and_service_contract.py \
        tldw_Server_API/app/core/exceptions.py
git commit -m "feat: scaffold ingestion source models and service contract"
```

### Task 2: Add Source-State Tables and Source-Scoped Persistence Helpers

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Sources/service.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_service_sqlite_state.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/database.py` only if a new DB-pool helper is required

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_create_source_persists_state_row(sqlite_db):
    from tldw_Server_API.app.core.Ingestion_Sources.service import ensure_ingestion_sources_schema, create_source

    await ensure_ingestion_sources_schema(sqlite_db)
    row = await create_source(
        sqlite_db,
        user_id=7,
        payload={
            "source_type": "local_directory",
            "sink_type": "media",
            "policy": "canonical",
            "config": {"path": "/allowed/project/docs"},
        },
    )

    assert row["user_id"] == 7
    assert row["source_type"] == "local_directory"
    assert row["sink_type"] == "media"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_service_sqlite_state.py::test_create_source_persists_state_row -v
```

Expected: FAIL because schema helpers and insert helpers do not exist.

**Step 3: Write minimal implementation**

```python
async def ensure_ingestion_sources_schema(db) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS ingestion_sources (...);
        CREATE TABLE IF NOT EXISTS ingestion_source_state (...);
        CREATE TABLE IF NOT EXISTS ingestion_source_snapshots (...);
        CREATE TABLE IF NOT EXISTS ingestion_source_items (...);
        CREATE TABLE IF NOT EXISTS ingestion_item_events (...);
        CREATE TABLE IF NOT EXISTS ingestion_source_artifacts (...);
        """
    )

async def create_source(db, *, user_id: int, payload: dict[str, object]) -> dict[str, object]:
    normalized = normalize_source_payload(payload)
    ...
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_service_sqlite_state.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/service.py \
        tldw_Server_API/tests/Ingestion_Sources/test_service_sqlite_state.py
git commit -m "feat: add ingestion source persistence helpers"
```

### Task 3: Implement Snapshot Diffing with Archive-Root Normalization

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/diffing.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_diffing.py`

**Step 1: Write the failing test**

```python
def test_diff_snapshots_strips_single_archive_root_and_detects_change():
    from tldw_Server_API.app.core.Ingestion_Sources.diffing import normalize_archive_members, diff_snapshots

    old_items = normalize_archive_members(["export_1/notes/a.md"], {"export_1/notes/a.md": "hash-1"})
    new_items = normalize_archive_members(["export_2/notes/a.md"], {"export_2/notes/a.md": "hash-2"})

    diff = diff_snapshots(previous=old_items, current=new_items)

    assert [item["relative_path"] for item in diff["changed"]] == ["notes/a.md"]
    assert diff["created"] == []
    assert diff["deleted"] == []
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_diffing.py::test_diff_snapshots_strips_single_archive_root_and_detects_change -v
```

Expected: FAIL because the diffing module does not exist.

**Step 3: Write minimal implementation**

```python
def normalize_archive_members(member_names: list[str], hashes: dict[str, str]) -> dict[str, dict[str, str]]:
    common_root = _single_common_root(member_names)
    result = {}
    for name in member_names:
        relative = _strip_root(name, common_root)
        result[relative] = {"relative_path": relative, "content_hash": hashes[name]}
    return result

def diff_snapshots(*, previous: dict[str, dict[str, str]], current: dict[str, dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    ...
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_diffing.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/diffing.py \
        tldw_Server_API/tests/Ingestion_Sources/test_diffing.py
git commit -m "feat: add ingestion source snapshot diffing"
```

### Task 4: Implement the Local Directory Source Adapter with Allowed-Root Enforcement

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/local_directory.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_local_directory_adapter.py`
- Modify: `tldw_Server_API/app/core/config.py`
- Modify: `tldw_Server_API/app/core/Setup/setup_manager.py`

**Step 1: Write the failing test**

```python
def test_local_directory_adapter_rejects_path_outside_allowed_roots(tmp_path, monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Sources.local_directory import validate_local_directory_source

    monkeypatch.setenv("INGESTION_SOURCE_ALLOWED_ROOTS", str(tmp_path / "allowed"))

    with pytest.raises(ValueError):
        validate_local_directory_source({"path": str(tmp_path / "outside")})
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_local_directory_adapter.py::test_local_directory_adapter_rejects_path_outside_allowed_roots -v
```

Expected: FAIL because the adapter and config support do not exist.

**Step 3: Write minimal implementation**

```python
def get_ingestion_source_allowed_roots() -> list[Path]:
    raw = os.getenv("INGESTION_SOURCE_ALLOWED_ROOTS", "")
    return [Path(entry).resolve() for entry in raw.split(os.pathsep) if entry.strip()]

def validate_local_directory_source(config: dict[str, object]) -> Path:
    raw_path = str(config.get("path") or "").strip()
    candidate = Path(raw_path).resolve(strict=False)
    roots = get_ingestion_source_allowed_roots()
    if not any(candidate.is_relative_to(root) for root in roots):
        raise ValueError("local source path outside allowed roots")
    return candidate
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_local_directory_adapter.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/local_directory.py \
        tldw_Server_API/tests/Ingestion_Sources/test_local_directory_adapter.py \
        tldw_Server_API/app/core/config.py \
        tldw_Server_API/app/core/Setup/setup_manager.py
git commit -m "feat: add local directory ingestion adapter"
```

### Task 5: Implement Archive Snapshot Staging, Validation, and Transactional Cutover

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/archive_snapshot.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_archive_snapshot_adapter.py`
- Reuse references from: `tldw_Server_API/app/core/Ingestion_Media_Processing/Upload_Sink.py`
- Reuse references from: `tldw_Server_API/app/core/Chatbooks/chatbook_service.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_archive_refresh_keeps_previous_snapshot_when_candidate_fails(tmp_path):
    from tldw_Server_API.app.core.Ingestion_Sources.archive_snapshot import apply_archive_candidate

    current_snapshot = {"id": 3, "status": "active"}

    with pytest.raises(ValueError):
        await apply_archive_candidate(
            source_id=11,
            archive_bytes=b"not-a-zip",
            filename="broken.zip",
            current_snapshot=current_snapshot,
        )
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_archive_snapshot_adapter.py::test_archive_refresh_keeps_previous_snapshot_when_candidate_fails -v
```

Expected: FAIL because archive staging code does not exist.

**Step 3: Write minimal implementation**

```python
async def apply_archive_candidate(...):
    candidate = await stage_archive_candidate(...)
    try:
        members = validate_archive_members(candidate)
        items = build_archive_snapshot(members)
    except Exception:
        await mark_snapshot_failed(candidate["id"])
        raise
    return {"candidate_snapshot": candidate, "items": items}
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_archive_snapshot_adapter.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/archive_snapshot.py \
        tldw_Server_API/tests/Ingestion_Sources/test_archive_snapshot_adapter.py
git commit -m "feat: add archive snapshot ingestion staging"
```

### Task 6: Implement the Media Sink and Sync Reconciliation Loop

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/sinks/__init__.py`
- Create: `tldw_Server_API/app/core/Ingestion_Sources/sinks/media_sink.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_media_sink.py`
- Reuse references from: `tldw_Server_API/app/core/External_Sources/sync_coordinator.py`
- Reuse references from: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

**Step 1: Write the failing test**

```python
def test_media_sink_updates_existing_binding_as_new_version(fake_media_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.media_sink import apply_media_change

    result = apply_media_change(
        fake_media_db,
        binding={"media_id": 42, "current_version_number": 1},
        change={"event_type": "changed", "relative_path": "docs/a.md", "text": "updated"},
        policy="canonical",
    )

    assert result["action"] == "version_created"
    assert result["media_id"] == 42
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_media_sink.py::test_media_sink_updates_existing_binding_as_new_version -v
```

Expected: FAIL because the sink does not exist.

**Step 3: Write minimal implementation**

```python
def apply_media_change(media_db, *, binding, change, policy):
    if change["event_type"] == "deleted" and policy == "canonical":
        ...
    if binding:
        version_number = media_db.apply_synced_document_content_update(...)
        return {"action": "version_created", "media_id": binding["media_id"], "version_number": version_number}
    media_id = media_db.add_media_with_keywords(...)
    return {"action": "created", "media_id": media_id}
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_media_sink.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/sinks/__init__.py \
        tldw_Server_API/app/core/Ingestion_Sources/sinks/media_sink.py \
        tldw_Server_API/tests/Ingestion_Sources/test_media_sink.py
git commit -m "feat: add ingestion source media sink"
```

### Task 7: Implement the Notes Sink with `sync_managed` and `detached` Semantics

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/sinks/notes_sink.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_notes_sink.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py` only if metadata helpers are needed
- Reuse references from: `tldw_Server_API/app/api/v1/endpoints/notes.py`

**Step 1: Write the failing test**

```python
def test_notes_sink_does_not_overwrite_detached_note(fake_notes_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.notes_sink import apply_notes_change

    result = apply_notes_change(
        fake_notes_db,
        binding={"note_id": "n-1", "sync_status": "conflict_detached"},
        change={"event_type": "changed", "relative_path": "notes/a.md", "text": "# A\n\nNew body"},
        policy="canonical",
    )

    assert result["action"] == "skipped_detached"
    assert result["sync_status"] == "conflict_detached"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_notes_sink.py::test_notes_sink_does_not_overwrite_detached_note -v
```

Expected: FAIL because the Notes sink does not exist.

**Step 3: Write minimal implementation**

```python
def apply_notes_change(notes_db, *, binding, change, policy):
    if binding and binding.get("sync_status") == "conflict_detached":
        return {"action": "skipped_detached", "sync_status": "conflict_detached"}
    if binding:
        notes_db.update_note(binding["note_id"], {"title": title, "content": body}, expected_version=current_version)
        return {"action": "updated", "note_id": binding["note_id"]}
    note_id = notes_db.add_note(title=title, content=body)
    return {"action": "created", "note_id": note_id}
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_notes_sink.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/sinks/notes_sink.py \
        tldw_Server_API/tests/Ingestion_Sources/test_notes_sink.py \
        tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py
git commit -m "feat: add ingestion source notes sink"
```

### Task 8: Add Jobs Worker, Scheduler Enqueue, and Source APIs

**Files:**
- Create: `tldw_Server_API/app/core/Ingestion_Sources/jobs.py`
- Create: `tldw_Server_API/app/services/ingestion_sources_worker.py`
- Create: `tldw_Server_API/app/services/ingestion_sources_scheduler.py`
- Create: `tldw_Server_API/app/api/v1/schemas/ingestion_sources.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/ingestion_sources.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_ingestion_sources_api.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/test_ingestion_sources_worker.py`
- Modify: `tldw_Server_API/app/main.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_manual_sync_endpoint_enqueues_job(client, auth_headers):
    response = client.post(
        "/api/v1/ingestion-sources/17/sync",
        headers=auth_headers,
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["source_id"] == 17
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_ingestion_sources_api.py::test_manual_sync_endpoint_enqueues_job -v
```

Expected: FAIL because the schema, endpoint, and worker are not registered.

**Step 3: Write minimal implementation**

```python
@router.post("/ingestion-sources/{source_id}/sync", status_code=202)
async def enqueue_source_sync(source_id: int, current_user=Depends(get_request_user)):
    job = await create_ingestion_source_job(user_id=int(current_user.id), source_id=source_id, job_type="sync")
    return {"status": "queued", "source_id": source_id, "job_id": job["id"]}
```

Also wire:
- router include in `tldw_Server_API/app/main.py`
- worker startup in `tldw_Server_API/app/main.py`
- scheduler startup in `tldw_Server_API/app/main.py`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/test_ingestion_sources_api.py \
                 tldw_Server_API/tests/Ingestion_Sources/test_ingestion_sources_worker.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Sources/jobs.py \
        tldw_Server_API/app/services/ingestion_sources_worker.py \
        tldw_Server_API/app/services/ingestion_sources_scheduler.py \
        tldw_Server_API/app/api/v1/schemas/ingestion_sources.py \
        tldw_Server_API/app/api/v1/endpoints/ingestion_sources.py \
        tldw_Server_API/tests/Ingestion_Sources/test_ingestion_sources_api.py \
        tldw_Server_API/tests/Ingestion_Sources/test_ingestion_sources_worker.py \
        tldw_Server_API/app/main.py
git commit -m "feat: add ingestion source jobs and api"
```

### Task 9: Add End-to-End Integration Coverage, Security Validation, and Completion Checks

**Files:**
- Create: `tldw_Server_API/tests/Ingestion_Sources/integration/test_local_directory_sync_integration.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/integration/test_archive_refresh_integration.py`
- Create: `tldw_Server_API/tests/Ingestion_Sources/integration/test_notes_detached_integration.py`
- Modify: `Docs/Plans/2026-03-08-ingestion-source-sync-design.md` only if implementation discoveries require a design delta

**Step 1: Write the failing integration tests**

```python
@pytest.mark.integration
def test_archive_refresh_failure_preserves_previous_snapshot(...):
    ...

@pytest.mark.integration
def test_notes_detached_note_is_not_overwritten(...):
    ...
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources/integration -v
```

Expected: FAIL until the integration plumbing is complete.

**Step 3: Implement only the missing glue exposed by those failures**

```python
# Examples:
# - fix worker state transitions
# - fix scheduler enqueue
# - fix item binding persistence
# - fix detached-note state propagation
```

**Step 4: Run verification**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Ingestion_Sources -v
python -m bandit -r tldw_Server_API/app/core/Ingestion_Sources \
                    tldw_Server_API/app/services/ingestion_sources_worker.py \
                    tldw_Server_API/app/services/ingestion_sources_scheduler.py \
                    tldw_Server_API/app/api/v1/endpoints/ingestion_sources.py \
                    -f json -o /tmp/bandit_ingestion_source_sync.json
```

Expected:
- pytest PASS
- Bandit reports no new unresolved findings in the touched scope

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Ingestion_Sources/integration \
        Docs/Plans/2026-03-08-ingestion-source-sync-design.md
git commit -m "test: add ingestion source integration coverage"
```

## Execution Notes

- Execute this plan in an isolated worktree, not in the current dirty workspace.
- Prefer reusing patterns from:
  - `tldw_Server_API/app/core/External_Sources/connectors_service.py`
  - `tldw_Server_API/app/services/connectors_worker.py`
  - `tldw_Server_API/app/services/connectors_sync_scheduler.py`
  - `tldw_Server_API/app/core/External_Sources/sync_coordinator.py`
- Do not promise historical note revisions unless a separate note-history feature is implemented first.
- Do not allow `sink_type` mutation after the first successful sync.
- Keep the Notes sink limited to text-first formats in v1.
