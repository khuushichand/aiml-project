# Meeting Intelligence API v1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a dedicated `/api/v1/meetings/*` domain with sessions, templates, artifacts, live updates (WS + SSE), and Slack/generic webhook sharing using existing audio/auth/infrastructure primitives.

**Architecture:** Add a new meetings domain layer (`endpoints + schemas + core services + DB adapter`) and adapt existing audio streaming/transcription pipelines instead of duplicating STT logic. Persist additive meeting tables in the same per-user content DB backend used today, and enforce org/team governance using existing AuthPrincipal/policy patterns.

**Tech Stack:** FastAPI, Pydantic, existing AuthNZ claims/permissions, per-user content DB backend wrappers, existing audio streaming/transcription modules, Loguru, pytest, Bandit.

---

Use these skills during execution:
- `@superpowers:test-driven-development`
- `@superpowers:systematic-debugging`
- `@superpowers:verification-before-completion`

Root worktree for execution:
- `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/meeting-intelligence-api-v1`

Virtualenv requirement for all commands:
- `cd /Users/macbook-dev/Documents/GitHub/tldw_server2 && source .venv/bin/activate`

Known environment caveat:
- In Codex sandbox, heavy audio imports (`torch`/`faster_whisper`) can fail with `OMP Error #179 Can't open SHM2`.
- Run affected test commands outside sandbox (escalated) when this appears.

## Stage 1: API Surface Scaffold
**Goal**: Introduce the dedicated meetings router and contract skeleton without business logic.
**Success Criteria**: `/api/v1/meetings/*` routes are mounted and contract validation works.
**Tests**: Route smoke test and schema validation tests pass.
**Status**: Complete

### Task 1: Add Meetings Schemas + Router Mount
**Progress**: Complete (`e5a753956`)

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/meetings_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/meetings.py`
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/__init__.py` (if schema exports are centralized)
- Test: `tldw_Server_API/tests/Meetings/test_meetings_routes_smoke.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_schemas.py`

**Step 1: Write the failing route smoke test**

```python
def test_meetings_router_is_mounted(client_with_routes):
    resp = client_with_routes.get("/api/v1/meetings/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_routes_smoke.py::test_meetings_router_is_mounted`  
Expected: `404` or import failure (`meetings.py` missing).

**Step 3: Write minimal router + schema contract stubs**

```python
router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.get("/health")
async def meetings_health() -> dict[str, str]:
    return {"status": "ok"}
```

**Step 4: Mount router in `main.py` with route-gating key**

```python
_include_if_enabled("meetings", meetings_router, prefix=f"{API_V1_PREFIX}", tags=["meetings"], default_stable=False)
```

**Step 5: Re-run tests**

Run:
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_routes_smoke.py`
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_schemas.py`  
Expected: PASS.

**Step 6: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/meetings_schemas.py \
        tldw_Server_API/app/api/v1/endpoints/meetings.py \
        tldw_Server_API/app/main.py \
        tldw_Server_API/tests/Meetings/test_meetings_routes_smoke.py \
        tldw_Server_API/tests/Meetings/test_meetings_schemas.py
git commit -m "feat(meetings): add router and schema scaffold"
```

## Stage 2: Persistence + Core Services
**Goal**: Add additive meetings persistence and domain services for sessions/templates/artifacts.
**Success Criteria**: CRUD operations work through DB adapter and service layer.
**Tests**: DB unit tests + service unit tests pass.
**Status**: Complete

### Task 2: Implement Meetings DB Adapter
**Progress**: Complete (`704b96c82`)

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/Meetings_DB.py`
- Create: `tldw_Server_API/app/api/v1/API_Deps/Meetings_DB_Deps.py`
- Modify: `tldw_Server_API/app/core/DB_Management/__init__.py` (if exports are maintained)
- Test: `tldw_Server_API/tests/Meetings/test_meetings_db.py`

**Step 1: Write failing DB tests**

```python
def test_create_and_get_session(meetings_db):
    sid = meetings_db.create_session(user_id="1", title="Standup", meeting_type="standup")
    row = meetings_db.get_session(session_id=sid, user_id="1")
    assert row["title"] == "Standup"
    assert row["status"] == "scheduled"
```

**Step 2: Run DB test to fail**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_db.py::test_create_and_get_session`  
Expected: `ModuleNotFoundError` or missing method failure.

**Step 3: Add minimal schema + CRUD**

```python
CREATE TABLE IF NOT EXISTS meeting_sessions (...);
CREATE TABLE IF NOT EXISTS meeting_templates (...);
CREATE TABLE IF NOT EXISTS meeting_artifacts (...);
CREATE TABLE IF NOT EXISTS meeting_integration_dispatch (...);
CREATE TABLE IF NOT EXISTS meeting_event_log (...);
```

```python
def create_session(...): ...
def get_session(...): ...
def list_sessions(...): ...
def update_session_status(...): ...
```

**Step 4: Add dependency provider**

```python
async def get_meetings_db_for_user(current_user: User = Depends(get_request_user)) -> MeetingsDatabase:
    return MeetingsDatabase.for_user(user_id=current_user.id)
```

**Step 5: Re-run DB tests**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_db.py`  
Expected: PASS.

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Meetings_DB.py \
        tldw_Server_API/app/api/v1/API_Deps/Meetings_DB_Deps.py \
        tldw_Server_API/tests/Meetings/test_meetings_db.py
git commit -m "feat(meetings): add persistence adapter and dependency"
```

### Task 3: Add Domain Services (Session/Template/Artifact)
**Progress**: Complete (`3548e172e`)

**Files:**
- Create: `tldw_Server_API/app/core/Meetings/__init__.py`
- Create: `tldw_Server_API/app/core/Meetings/session_service.py`
- Create: `tldw_Server_API/app/core/Meetings/template_service.py`
- Create: `tldw_Server_API/app/core/Meetings/artifact_service.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_session_service.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_template_service.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_artifact_service.py`

**Step 1: Write failing service tests**

```python
def test_session_state_machine_blocks_invalid_transition(session_service):
    sid = session_service.create_session(...)
    with pytest.raises(ValueError):
        session_service.transition(sid, to_status="completed")
```

**Step 2: Run tests to fail**

Run:
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_session_service.py`
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_template_service.py`

Expected: missing service modules/methods.

**Step 3: Implement minimal services**

```python
ALLOWED = {
  "scheduled": {"live", "processing", "failed"},
  "live": {"processing", "completed", "failed"},
  "processing": {"completed", "failed"},
}
```

```python
def list_templates(...):
    # builtin/org/team/personal scope filtering + enabled checks
    ...
```

**Step 4: Re-run service tests**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_*service.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Meetings \
        tldw_Server_API/tests/Meetings/test_meetings_session_service.py \
        tldw_Server_API/tests/Meetings/test_meetings_template_service.py \
        tldw_Server_API/tests/Meetings/test_meetings_artifact_service.py
git commit -m "feat(meetings): add session template artifact services"
```

## Stage 3: API CRUD + Governance
**Goal**: Expose sessions/templates/artifacts APIs with auth-aware access controls.
**Success Criteria**: Endpoints enforce ownership/scope and return expected payloads.
**Tests**: Endpoint integration tests pass in single-user and claims-aware multi-user fixtures.
**Status**: Complete

### Task 4: Implement Session + Template + Artifact Endpoints
**Progress**: Complete (`b268af3f8`)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/meetings.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/meetings_schemas.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_sessions_api.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_templates_api.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_artifacts_api.py`

**Step 1: Write failing endpoint tests**

```python
def test_create_session_returns_scheduled(client):
    r = client.post("/api/v1/meetings/sessions", json={"title": "Weekly", "meeting_type": "standup"})
    assert r.status_code == 201
    assert r.json()["status"] == "scheduled"
```

**Step 2: Run tests to fail**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_sessions_api.py`  
Expected: `404` or `501`.

**Step 3: Implement endpoint handlers using services**

```python
@router.post("/sessions", response_model=MeetingSessionResponse, status_code=201)
async def create_session(payload: MeetingSessionCreate, ...):
    return session_service.create(...)
```

```python
@router.get("/templates")
async def list_templates(scope: str | None = None, ...):
    return template_service.list_templates(...)
```

**Step 4: Add governance checks**

Use claim-first patterns like connectors/workflows:
- admin/team-lead gates for org/team template mutation
- personal template creation behind policy flag
- built-ins immutable to non-admin roles

**Step 5: Re-run endpoint tests**

Run:
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_sessions_api.py`
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_templates_api.py`
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_artifacts_api.py`

Expected: PASS.

**Step 6: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/meetings.py \
        tldw_Server_API/app/api/v1/schemas/meetings_schemas.py \
        tldw_Server_API/tests/Meetings/test_meetings_sessions_api.py \
        tldw_Server_API/tests/Meetings/test_meetings_templates_api.py \
        tldw_Server_API/tests/Meetings/test_meetings_artifacts_api.py
git commit -m "feat(meetings): add sessions templates artifacts CRUD"
```

## Stage 4: Live Transport + Ingestion + Artifact Finalization
**Goal**: Support live WS and SSE updates plus offline ingest/finalize flow.
**Success Criteria**: Session stream emits standardized events and finalize generates artifacts.
**Tests**: Streaming contract tests + ingest/finalize integration tests pass.
**Status**: Complete

### Task 5: Add SSE and WS Meeting Event Transport
**Progress**: Complete (`602f28ef1`)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/meetings.py`
- Create: `tldw_Server_API/app/core/Meetings/events_service.py`
- Create: `tldw_Server_API/app/core/Meetings/stream_adapter.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_events_sse.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_stream_ws.py`

**Step 1: Write failing transport tests**

```python
def test_sse_events_streams_structured_frames(client):
    r = client.get(f"/api/v1/meetings/sessions/{sid}/events")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
```

**Step 2: Run tests to fail**

Run:
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_events_sse.py`
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_stream_ws.py`

Expected: missing endpoints/transport behavior.

**Step 3: Implement minimal transport adapters**

```python
event = {"type": "session.status", "session_id": sid, "timestamp": now_iso, "data": {...}}
```

```python
@router.websocket("/sessions/{session_id}/stream")
async def stream_session(...):
    # adapt existing audio ws pipeline for transcript.* and insight.* events
    ...
```

**Step 4: Re-run transport tests**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_events_sse.py tldw_Server_API/tests/Meetings/test_meetings_stream_ws.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/meetings.py \
        tldw_Server_API/app/core/Meetings/events_service.py \
        tldw_Server_API/app/core/Meetings/stream_adapter.py \
        tldw_Server_API/tests/Meetings/test_meetings_events_sse.py \
        tldw_Server_API/tests/Meetings/test_meetings_stream_ws.py
git commit -m "feat(meetings): add SSE and websocket event transport"
```

### Task 6: Implement Offline Ingest + Finalize Artifacts
**Progress**: Complete (`44e157880`)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/meetings.py`
- Modify: `tldw_Server_API/app/core/Meetings/artifact_service.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_ingest_finalize_api.py`

**Step 1: Write failing ingest/finalize test**

```python
def test_finalize_session_generates_summary_and_actions(client):
    ...
    r = client.post(f"/api/v1/meetings/sessions/{sid}/commit")
    assert r.status_code == 200
    assert "summary" in kinds and "action_items" in kinds
```

**Step 2: Run test to fail**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_ingest_finalize_api.py`  
Expected: artifacts missing.

**Step 3: Implement finalize pipeline**

```python
artifacts = artifact_service.generate_final_artifacts(
    transcript_text=..., template=..., include=["summary", "action_items", "decisions", "speaker_stats"]
)
```

**Step 4: Re-run test**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_ingest_finalize_api.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/meetings.py \
        tldw_Server_API/app/core/Meetings/artifact_service.py \
        tldw_Server_API/tests/Meetings/test_meetings_ingest_finalize_api.py
git commit -m "feat(meetings): add ingest and finalize artifact generation"
```

## Stage 5: Sharing Integrations + Hardening + Docs
**Goal**: Add Slack/webhook dispatch with retries and complete verification/docs.
**Success Criteria**: Sharing endpoints dispatch reliably and observability/security checks pass.
**Tests**: Integration + worker tests pass; touched-path Bandit scan clean of new issues.
**Status**: Complete (in working tree, pending commit)

### Task 7: Slack + Webhook Dispatch + DLQ Worker
**Progress**: Complete (`bdb0892f9`)

**Files:**
- Create: `tldw_Server_API/app/core/Meetings/integration_service.py`
- Create: `tldw_Server_API/app/services/meetings_webhook_dlq_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/meetings.py`
- Modify: `tldw_Server_API/app/main.py` (worker startup/shutdown wiring)
- Test: `tldw_Server_API/tests/Meetings/test_meetings_integrations_api.py`
- Test: `tldw_Server_API/tests/Meetings/test_meetings_webhook_dlq_worker.py`

**Step 1: Write failing sharing tests**

```python
def test_share_to_slack_enqueues_dispatch(client, monkeypatch):
    r = client.post(f"/api/v1/meetings/sessions/{sid}/share/slack", json={"webhook_url": "...", "artifact_ids": [aid]})
    assert r.status_code == 202
```

**Step 2: Run tests to fail**

Run:
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_integrations_api.py`
- `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_webhook_dlq_worker.py`

Expected: endpoint/worker missing.

**Step 3: Implement dispatch + retries**

```python
if not egress_allowed(url):
    raise HTTPException(status_code=403, detail="Webhook destination denied by policy")
```

```python
async def run_meetings_webhook_dlq_worker(stop_event: asyncio.Event) -> None:
    # fetch due items -> attempt -> backoff -> mark success/failure
    ...
```

**Step 4: Re-run tests**

Run: `python -m pytest -q tldw_Server_API/tests/Meetings/test_meetings_integrations_api.py tldw_Server_API/tests/Meetings/test_meetings_webhook_dlq_worker.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Meetings/integration_service.py \
        tldw_Server_API/app/services/meetings_webhook_dlq_service.py \
        tldw_Server_API/app/api/v1/endpoints/meetings.py \
        tldw_Server_API/app/main.py \
        tldw_Server_API/tests/Meetings/test_meetings_integrations_api.py \
        tldw_Server_API/tests/Meetings/test_meetings_webhook_dlq_worker.py
git commit -m "feat(meetings): add slack and webhook dispatch pipeline"
```

### Task 8: Final Verification, Security Scan, and Docs
**Progress**: Complete (in working tree, pending commit)

**Files:**
- Create: `Docs/API-related/Meeting_Intelligence_API.md`
- Modify: `Docs/Published/Overview/Feature_Status.md`
- Modify: `Docs/Product/Meeting-Transcripts-PRD.md` (implementation status notes / links)

**Step 1: Run targeted meetings test suite**

Run:
- `python -m pytest -q tldw_Server_API/tests/Meetings`
- `python -m pytest -q tldw_Server_API/tests/Audio/test_audio_streaming_truthiness_flags.py`

Expected: PASS.

**Step 2: Run focused regression tests**

Run:
- `python -m pytest -q tldw_Server_API/tests/Collections/test_outputs_templates_api.py`
- `python -m pytest -q tldw_Server_API/tests/External_Sources/test_connectors_endpoints_api.py`

Expected: PASS.

**Step 3: Run Bandit on touched scope**

Run:
- `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/meetings.py tldw_Server_API/app/core/Meetings tldw_Server_API/app/services/meetings_webhook_dlq_service.py tldw_Server_API/app/core/DB_Management/Meetings_DB.py -f json -o /tmp/bandit_meetings_v1.json`

Expected: no new High findings in touched lines.

**Step 4: Update docs**

Document:
- endpoint list and payload contracts
- event envelope schema (`transcript.partial`, `insight.update`, `artifact.ready`, etc.)
- known limitations (v1 integrations: Slack + generic webhook only)

**Step 5: Commit**

```bash
git add Docs/API-related/Meeting_Intelligence_API.md \
        Docs/Published/Overview/Feature_Status.md \
        Docs/Product/Meeting-Transcripts-PRD.md
git commit -m "docs(meetings): add API reference and feature status updates"
```

---

## Definition of Done (Execution Gate)

- All Stage 1-5 task tests pass.
- `/api/v1/meetings/*` contract works in single-user and multi-user fixtures.
- WS + SSE event transport emits stable schema-versioned payloads.
- Template governance controls enforce scope and role rules.
- Slack/webhook delivery retries are observable and policy-constrained.
- Bandit run on touched scope completed with no unresolved new high-severity issues.
- Documentation updated with exact endpoints and rollout limitations.
