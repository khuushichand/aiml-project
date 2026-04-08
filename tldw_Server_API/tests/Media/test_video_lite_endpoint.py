from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.endpoints.media.video_lite import get_optional_request_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


pytestmark = pytest.mark.unit


class _BillingRepoStub:
    def __init__(self, subscriptions_by_org: dict[int, dict[str, object] | None] | None = None) -> None:
        self.subscriptions_by_org = subscriptions_by_org or {}

    async def get_org_subscription(self, org_id: int) -> dict[str, object] | None:
        return self.subscriptions_by_org.get(org_id)


class _WorkspaceDbState:
    def __init__(
        self,
        *,
        source_url: str = "https://www.youtube.com/watch?v=abc123",
        source_key: str = "youtube:abc123",
        transcript: str | None = "Speaker 1: Welcome back to the transcript.",
        analysis_content: str | None = None,
    ) -> None:
        self.media_id = 41
        self.source_url = source_url
        self.source_key = source_key
        self.transcript = transcript
        self.analysis_content = analysis_content
        self.process_update_summaries: list[str | None] = []
        self.generated_summaries: list[str] = []

    def lookup_media(self, url: str) -> dict[str, object] | None:
        if url in {
            self.source_url,
            self.source_key,
            "https://www.youtube.com/watch?v=abc123",
        }:
            return {
                "id": self.media_id,
                "url": self.source_url,
                "title": "Demo video",
            }
        return None

    def latest_document_version(self) -> dict[str, object]:
        return {
            "media_id": self.media_id,
            "version_number": 1,
            "analysis_content": self.analysis_content,
            "content": self.transcript or "",
        }


class _VideoLiteJobManagerStub:
    def __init__(self, *, jobs: list[dict[str, object]] | None = None) -> None:
        self.jobs = [dict(job) for job in (jobs or [])]
        self.create_job_calls: list[dict[str, object]] = []
        self.next_job_id = 1000

    def create_job(self, **kwargs):
        self.create_job_calls.append(dict(kwargs))

        idempotency_key = kwargs.get("idempotency_key")
        domain = kwargs.get("domain")
        queue = kwargs.get("queue")
        job_type = kwargs.get("job_type")
        for job in self.jobs:
            if (
                job.get("idempotency_key") == idempotency_key
                and job.get("domain") == domain
                and job.get("queue") == queue
                and job.get("job_type") == job_type
            ):
                return dict(job)

        row = {
            "id": self.next_job_id,
            "uuid": f"video-lite-job-{self.next_job_id}",
            "status": "queued",
            "domain": domain,
            "queue": queue,
            "job_type": job_type,
            "owner_user_id": kwargs.get("owner_user_id"),
            "batch_group": kwargs.get("batch_group"),
            "idempotency_key": idempotency_key,
            "payload": kwargs.get("payload"),
        }
        self.next_job_id += 1
        self.jobs.append(dict(row))
        return row

    def list_jobs(self, **kwargs):
        matched = list(self.jobs)
        for key in ("domain", "queue", "status", "owner_user_id", "job_type", "batch_group"):
            value = kwargs.get(key)
            if value is not None:
                matched = [job for job in matched if job.get(key) == value]
        limit = int(kwargs.get("limit", len(matched) or 0))
        return [dict(job) for job in matched[:limit]]


@pytest.fixture()
def video_lite_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod
    from tldw_Server_API.app.api.v1.endpoints import media as media_mod
    from tldw_Server_API.app.api.v1.endpoints.media.ingest_jobs import get_job_manager

    async def _get_billing_repo_stub(db_pool=None) -> _BillingRepoStub:
        _ = db_pool
        return _BillingRepoStub()

    app = FastAPI()
    app.include_router(media_mod.router, prefix="/api/v1/media", tags=["media"])
    monkeypatch.setattr(
        video_lite_service_mod,
        "get_video_lite_billing_repo",
        _get_billing_repo_stub,
        raising=False,
    )
    app.dependency_overrides[get_job_manager] = lambda: _VideoLiteJobManagerStub()

    return app


@pytest.fixture()
def video_lite_client(video_lite_app: FastAPI) -> TestClient:
    with TestClient(video_lite_app) as client:
        yield client


def _make_user() -> User:
    return User(
        id=7,
        username="tester",
        email="tester@example.com",
        role="user",
        is_active=True,
        is_verified=True,
    )


def _patch_request_user(
    monkeypatch: pytest.MonkeyPatch,
    *,
    active_org_id: int | None,
    org_ids: list[int] | None = None,
    user: User | None = None,
) -> None:
    from tldw_Server_API.app.api.v1.endpoints.media import video_lite as video_lite_mod

    async def _return_user(request: Request, api_key=None, token=None) -> User:
        _ = api_key, token
        request.state.active_org_id = active_org_id
        request.state.org_ids = list(org_ids or ([] if active_org_id is None else [active_org_id]))
        return user or _make_user()

    monkeypatch.setattr(video_lite_mod, "get_request_user", _return_user)


def _patch_billing_repo(
    monkeypatch: pytest.MonkeyPatch,
    *,
    subscriptions_by_org: dict[int, dict[str, object] | None],
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    async def _get_billing_repo_stub(db_pool=None) -> _BillingRepoStub:
        _ = db_pool
        return _BillingRepoStub(subscriptions_by_org=subscriptions_by_org)

    monkeypatch.setattr(
        video_lite_service_mod,
        "get_video_lite_billing_repo",
        _get_billing_repo_stub,
        raising=False,
    )


def _patch_workspace_db(
    monkeypatch: pytest.MonkeyPatch,
    *,
    state: _WorkspaceDbState,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    @contextmanager
    def _fake_managed_media_database(*args, **kwargs):
        _ = args, kwargs
        yield object()

    def _get_media_by_url(db, url, **kwargs):
        _ = db, kwargs
        return state.lookup_media(url)

    def _get_latest_transcription(db, media_id):
        _ = db
        return state.transcript if media_id == state.media_id else None

    def _get_document_version(db, media_id, version_number=None, include_content=False):
        _ = db, version_number, include_content
        if media_id != state.media_id:
            return None
        return state.latest_document_version()

    def _process_media_update(db, *, media_id, summary=None, **kwargs):
        _ = db, kwargs
        if media_id != state.media_id:
            return {"status": "Error", "error": "Media not found", "media_id": media_id}
        state.process_update_summaries.append(summary)
        state.analysis_content = summary
        return {
            "status": "Success",
            "media_id": media_id,
            "latest_version": {
                "analysis_content": summary,
            },
        }

    monkeypatch.setattr(video_lite_service_mod, "get_user_media_db_path", lambda user_id: "/tmp/video-lite-test.db", raising=False)
    monkeypatch.setattr(video_lite_service_mod, "managed_media_database", _fake_managed_media_database, raising=False)
    monkeypatch.setattr(video_lite_service_mod, "get_media_by_url", _get_media_by_url, raising=False)
    monkeypatch.setattr(video_lite_service_mod, "get_latest_transcription", _get_latest_transcription, raising=False)
    monkeypatch.setattr(video_lite_service_mod, "get_document_version", _get_document_version, raising=False)
    monkeypatch.setattr(video_lite_service_mod, "process_media_update", _process_media_update, raising=False)


def _patch_video_lite_job_manager(
    video_lite_app: FastAPI,
    *,
    job_manager: _VideoLiteJobManagerStub,
) -> None:
    from tldw_Server_API.app.api.v1.endpoints.media.ingest_jobs import get_job_manager

    video_lite_app.dependency_overrides[get_job_manager] = lambda: job_manager


def test_video_lite_source_requires_login_when_signed_out(video_lite_client: TestClient) -> None:
    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "target_tab": "transcript",
        },
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["source_key"] == "youtube:abc123"  # nosec B101
    assert payload["state"] == "not_ingested"  # nosec B101
    assert payload["launcher_access"] == "login_required"  # nosec B101
    assert payload["entitlement"] == "signed_out"  # nosec B101


def test_video_lite_source_requires_subscription_for_signed_in_unsubscribed_user(
    video_lite_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_user(monkeypatch, active_org_id=12)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={12: None})

    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "source_state": "ready",
            "target_tab": "chat",
        },
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["launcher_access"] == "subscription_required"  # nosec B101
    assert payload["entitlement"] == "signed_in_unsubscribed"  # nosec B101
    assert payload["state"] == "not_ingested"  # nosec B101


def test_video_lite_source_allows_signed_in_subscribed_user(
    video_lite_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_user(monkeypatch, active_org_id=22)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={22: {"status": "active", "plan_name": "pro"}})

    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "source_state": "ready",
            "target_tab": "chat",
        },
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["source_key"] == "youtube:abc123"  # nosec B101
    assert payload["launcher_access"] == "allowed"  # nosec B101
    assert payload["entitlement"] == "signed_in_subscribed"  # nosec B101
    assert payload["state"] == "processing"  # nosec B101


def test_video_lite_source_kicks_off_ingest_for_paid_user_when_media_is_missing(
    video_lite_client: TestClient,
    video_lite_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_user(monkeypatch, active_org_id=22)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={22: {"status": "active", "plan_name": "pro"}})
    job_manager = _VideoLiteJobManagerStub()
    _patch_video_lite_job_manager(video_lite_app, job_manager=job_manager)

    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "target_tab": "chat",
        },
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["state"] == "processing"  # nosec B101
    assert payload["launcher_access"] == "allowed"  # nosec B101
    assert payload["entitlement"] == "signed_in_subscribed"  # nosec B101
    assert len(job_manager.create_job_calls) == 1  # nosec B101
    created_job = job_manager.create_job_calls[0]
    assert created_job["domain"] == "media_ingest"  # nosec B101
    assert created_job["job_type"] == "media_ingest_item"  # nosec B101
    assert created_job["owner_user_id"] == "7"  # nosec B101
    assert created_job["payload"] == {  # nosec B101
        "batch_id": "video-lite:7:youtube:abc123",
        "media_type": "video",
        "source": "https://www.youtube.com/watch?v=abc123",
        "source_kind": "url",
        "input_ref": "https://www.youtube.com/watch?v=abc123",
        "options": {"perform_analysis": True},
    }


def test_video_lite_source_does_not_create_job_when_user_is_signed_out(
    video_lite_client: TestClient,
    video_lite_app: FastAPI,
) -> None:
    job_manager = _VideoLiteJobManagerStub()
    _patch_video_lite_job_manager(video_lite_app, job_manager=job_manager)

    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "target_tab": "transcript",
        },
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["launcher_access"] == "login_required"  # nosec B101
    assert payload["state"] == "not_ingested"  # nosec B101
    assert job_manager.create_job_calls == []  # nosec B101


def test_video_lite_source_reuses_pending_ingest_job_for_repeat_requests(
    video_lite_client: TestClient,
    video_lite_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_user(monkeypatch, active_org_id=22)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={22: {"status": "active", "plan_name": "pro"}})
    job_manager = _VideoLiteJobManagerStub()
    _patch_video_lite_job_manager(video_lite_app, job_manager=job_manager)

    first_response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "target_tab": "transcript",
        },
        headers={"X-API-KEY": "test-api-key"},
    )
    second_response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "target_tab": "chat",
        },
        headers={"X-API-KEY": "test-api-key"},
    )

    assert first_response.status_code == 200, first_response.text  # nosec B101
    assert second_response.status_code == 200, second_response.text  # nosec B101
    assert first_response.json()["state"] == "processing"  # nosec B101
    assert second_response.json()["state"] == "processing"  # nosec B101
    assert len(job_manager.create_job_calls) == 1  # nosec B101


def test_video_lite_source_resolve_does_not_trigger_summary_generation(
    video_lite_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    _patch_request_user(monkeypatch, active_org_id=22)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={22: {"status": "active", "plan_name": "pro"}})

    async def _unexpected_prepare_summary(**kwargs) -> bool:
        raise AssertionError(f"source resolve should not prepare summary generation: {kwargs}")

    async def _unexpected_run_summary(**kwargs) -> bool:
        raise AssertionError(f"source resolve should not run summary generation: {kwargs}")

    monkeypatch.setattr(
        video_lite_service_mod,
        "prepare_video_lite_summary_generation",
        _unexpected_prepare_summary,
        raising=True,
    )
    monkeypatch.setattr(
        video_lite_service_mod,
        "run_video_lite_summary_generation",
        _unexpected_run_summary,
        raising=True,
    )

    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "source_state": "ready",
            "target_tab": "chat",
        },
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 200, response.text  # nosec B101


@pytest.mark.parametrize(
    ("source_url", "expected_source_key"),
    [
        ("https://m.youtube.com/watch?v=abc123", "youtube:abc123"),
        ("https://youtu.be/abc123", "youtube:abc123"),
        ("youtube:abc123", "youtube:abc123"),
        ("https://notyoutube.com/watch?v=abc123", "https://notyoutube.com/watch?v=abc123"),
        ("https://www.youtube.com:443/watch?v=abc123", "youtube:abc123"),
    ],
)
def test_video_lite_source_endpoint_normalization_cases(
    video_lite_client: TestClient,
    source_url: str,
    expected_source_key: str,
) -> None:
    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={"source_url": source_url, "target_tab": "transcript"},
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["source_key"] == expected_source_key  # nosec B101
    assert payload["launcher_access"] == "login_required"  # nosec B101


def test_video_lite_source_endpoint_rejects_whitespace_only_source_url(video_lite_client: TestClient) -> None:
    response = video_lite_client.post(
        "/api/v1/media/video-lite/source",
        json={"source_url": "   ", "target_tab": "transcript"},
    )

    assert response.status_code == 422, response.text  # nosec B101


def test_video_lite_workspace_returns_signed_out_entitlement(video_lite_client: TestClient) -> None:
    response = video_lite_client.get(
        "/api/v1/media/video-lite/workspace/youtube:abc123",
        params={"source_url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["source_key"] == "youtube:abc123"  # nosec B101
    assert payload["entitlement"] == "signed_out"  # nosec B101
    assert payload["summary_state"] == "not_requested"  # nosec B101


def test_video_lite_workspace_returns_signed_in_subscribed_entitlement(
    video_lite_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_user(monkeypatch, active_org_id=22)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={22: {"status": "active", "plan_name": "pro"}})

    response = video_lite_client.get(
        "/api/v1/media/video-lite/workspace/youtube:abc123",
        params={"source_url": "https://www.youtube.com/watch?v=abc123"},
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["source_key"] == "youtube:abc123"  # nosec B101
    assert payload["entitlement"] == "signed_in_subscribed"  # nosec B101
    assert payload["state"] == "not_ingested"  # nosec B101
    assert payload["summary_state"] == "not_requested"  # nosec B101


def test_video_lite_workspace_reports_processing_when_ingest_job_is_pending(
    video_lite_client: TestClient,
    video_lite_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_user(monkeypatch, active_org_id=22)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={22: {"status": "active", "plan_name": "pro"}})
    job_manager = _VideoLiteJobManagerStub(
        jobs=[
            {
                "id": 1000,
                "uuid": "video-lite-job-1000",
                "status": "queued",
                "domain": "media_ingest",
                "queue": "low",
                "job_type": "media_ingest_item",
                "owner_user_id": "7",
                "batch_group": "video-lite:7:youtube:abc123",
                "idempotency_key": "video-lite:7:youtube:abc123:attempt:1",
                "payload": {
                    "batch_id": "video-lite:7:youtube:abc123",
                    "media_type": "video",
                    "source": "https://www.youtube.com/watch?v=abc123",
                    "source_kind": "url",
                    "input_ref": "https://www.youtube.com/watch?v=abc123",
                    "options": {"perform_analysis": True},
                },
            }
        ]
    )
    _patch_video_lite_job_manager(video_lite_app, job_manager=job_manager)

    response = video_lite_client.get(
        "/api/v1/media/video-lite/workspace/youtube:abc123",
        params={"source_url": "https://www.youtube.com/watch?v=abc123"},
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 200, response.text  # nosec B101
    payload = response.json()
    assert payload["source_key"] == "youtube:abc123"  # nosec B101
    assert payload["entitlement"] == "signed_in_subscribed"  # nosec B101
    assert payload["state"] == "processing"  # nosec B101
    assert payload["summary_state"] == "not_requested"  # nosec B101


@pytest.mark.asyncio
async def test_get_optional_request_user_returns_none_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints.media import video_lite as video_lite_mod

    async def _raise_unauthorized(request: Request, api_key=None, token=None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing credentials")

    monkeypatch.setattr(video_lite_mod, "get_request_user", _raise_unauthorized)
    request = Request({"type": "http", "headers": []})

    result = await get_optional_request_user(request, api_key=None, token=None)

    assert result is None


@pytest.mark.asyncio
async def test_get_optional_request_user_preserves_invalid_credential_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.api.v1.endpoints.media import video_lite as video_lite_mod

    async def _raise_unauthorized(request: Request, api_key=None, token=None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")

    monkeypatch.setattr(video_lite_mod, "get_request_user", _raise_unauthorized)
    request = Request({"type": "http", "headers": []})

    with pytest.raises(HTTPException) as exc_info:
        await get_optional_request_user(request, api_key=None, token="bad-token")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_resolve_video_lite_workspace_returns_transcript_and_ready_summary_from_media_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    state = _WorkspaceDbState(analysis_content="A concise summary of the transcript.")
    _patch_workspace_db(monkeypatch, state=state)

    workspace = await video_lite_service_mod.resolve_video_lite_workspace(
        "youtube:abc123",
        source_url=state.source_url,
        current_user=_make_user(),
        active_org_id=22,
        billing_repo=_BillingRepoStub({22: {"status": "active"}}),
    )

    assert workspace.state == "ready"
    assert workspace.transcript == state.transcript
    assert workspace.summary_state == "ready"
    assert workspace.summary == "A concise summary of the transcript."


@pytest.mark.asyncio
async def test_prepare_video_lite_summary_generation_marks_processing_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    state = _WorkspaceDbState(analysis_content=None)
    _patch_workspace_db(monkeypatch, state=state)

    first_result = await video_lite_service_mod.prepare_video_lite_summary_generation(
        source_key=state.source_key,
        source_url=state.source_url,
        current_user=_make_user(),
    )
    second_result = await video_lite_service_mod.prepare_video_lite_summary_generation(
        source_key=state.source_key,
        source_url=state.source_url,
        current_user=_make_user(),
    )

    assert first_result is True
    assert second_result is False
    assert state.process_update_summaries == [video_lite_service_mod.VIDEO_LITE_SUMMARY_PROCESSING_MARKER]


@pytest.mark.asyncio
async def test_prepare_video_lite_summary_refresh_replaces_existing_summary_with_processing_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    state = _WorkspaceDbState(analysis_content="Existing ready summary.")
    _patch_workspace_db(monkeypatch, state=state)

    refreshed = await video_lite_service_mod.prepare_video_lite_summary_refresh(
        source_key=state.source_key,
        source_url=state.source_url,
        current_user=_make_user(),
    )

    assert refreshed is True
    assert state.process_update_summaries == [video_lite_service_mod.VIDEO_LITE_SUMMARY_PROCESSING_MARKER]


@pytest.mark.asyncio
async def test_prepare_video_lite_summary_generation_marks_processing_before_transcript_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    state = _WorkspaceDbState(transcript=None, analysis_content=None)
    _patch_workspace_db(monkeypatch, state=state)

    result = await video_lite_service_mod.prepare_video_lite_summary_generation(
        source_key=state.source_key,
        source_url=state.source_url,
        current_user=_make_user(),
    )

    assert result is False
    assert state.process_update_summaries == []


@pytest.mark.asyncio
async def test_prepare_video_lite_summary_generation_does_not_retry_ready_or_failed_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    ready_state = _WorkspaceDbState(analysis_content="Existing ready summary.")
    _patch_workspace_db(monkeypatch, state=ready_state)

    ready_result = await video_lite_service_mod.prepare_video_lite_summary_generation(
        source_key=ready_state.source_key,
        source_url=ready_state.source_url,
        current_user=_make_user(),
    )

    assert ready_result is False
    assert ready_state.process_update_summaries == []

    failed_state = _WorkspaceDbState(
        analysis_content=f"{video_lite_service_mod.VIDEO_LITE_SUMMARY_FAILED_PREFIX}provider unavailable"
    )
    _patch_workspace_db(monkeypatch, state=failed_state)

    failed_result = await video_lite_service_mod.prepare_video_lite_summary_generation(
        source_key=failed_state.source_key,
        source_url=failed_state.source_url,
        current_user=_make_user(),
    )

    assert failed_result is False
    assert failed_state.process_update_summaries == []


def test_video_lite_summary_refresh_endpoint_marks_processing_and_schedules_background_generation(
    video_lite_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    _patch_request_user(monkeypatch, active_org_id=22)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={22: {"status": "active", "plan_name": "pro"}})
    state = _WorkspaceDbState(analysis_content="Existing ready summary.")
    _patch_workspace_db(monkeypatch, state=state)
    scheduled_calls: list[dict[str, object]] = []

    async def _run_summary(**kwargs) -> bool:
        scheduled_calls.append(dict(kwargs))
        return True

    monkeypatch.setattr(
        video_lite_service_mod,
        "run_video_lite_summary_generation",
        _run_summary,
        raising=True,
    )

    response = video_lite_client.post(
        f"/api/v1/media/video-lite/workspace/{state.source_key}/summary-refresh",
        params={"source_url": state.source_url},
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 202, response.text  # nosec B101
    payload = response.json()
    assert payload["state"] == "ready"  # nosec B101
    assert payload["summary_state"] == "processing"  # nosec B101
    assert state.process_update_summaries == [video_lite_service_mod.VIDEO_LITE_SUMMARY_PROCESSING_MARKER]
    assert len(scheduled_calls) == 1  # nosec B101
    assert scheduled_calls[0]["source_key"] == state.source_key  # nosec B101
    assert scheduled_calls[0]["source_url"] == state.source_url  # nosec B101
    assert getattr(scheduled_calls[0]["current_user"], "id", None) == 7  # nosec B101


def test_video_lite_summary_refresh_endpoint_rejects_unsubscribed_user(
    video_lite_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_user(monkeypatch, active_org_id=12)
    _patch_billing_repo(monkeypatch, subscriptions_by_org={12: None})

    response = video_lite_client.post(
        "/api/v1/media/video-lite/workspace/youtube:abc123/summary-refresh",
        params={"source_url": "https://www.youtube.com/watch?v=abc123"},
        headers={"X-API-KEY": "test-api-key"},
    )

    assert response.status_code == 403, response.text  # nosec B101
    assert response.json()["detail"] == "Active subscription required."  # nosec B101


@pytest.mark.asyncio
async def test_run_video_lite_summary_generation_persists_generated_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    state = _WorkspaceDbState()
    _patch_workspace_db(monkeypatch, state=state)
    state.analysis_content = video_lite_service_mod.VIDEO_LITE_SUMMARY_PROCESSING_MARKER

    async def _generate_summary(transcript: str, *, source_key: str) -> str:
        state.generated_summaries.append(f"{source_key}:{transcript}")
        return "A generated eager summary."

    monkeypatch.setattr(
        video_lite_service_mod,
        "generate_video_lite_summary_text",
        _generate_summary,
        raising=False,
    )

    await video_lite_service_mod.run_video_lite_summary_generation(
        source_key=state.source_key,
        source_url=state.source_url,
        current_user=_make_user(),
    )

    assert state.generated_summaries == [f"{state.source_key}:{state.transcript}"]
    assert state.analysis_content == "A generated eager summary."


@pytest.mark.asyncio
async def test_resolve_video_lite_workspace_reports_failed_summary_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.services import video_lite_service as video_lite_service_mod

    state = _WorkspaceDbState(
        analysis_content=f"{video_lite_service_mod.VIDEO_LITE_SUMMARY_FAILED_PREFIX}provider unavailable"
    )
    _patch_workspace_db(monkeypatch, state=state)

    workspace = await video_lite_service_mod.resolve_video_lite_workspace(
        state.source_key,
        source_url=state.source_url,
        current_user=_make_user(),
        active_org_id=22,
        billing_repo=_BillingRepoStub({22: {"status": "active"}}),
    )

    assert workspace.state == "ready"
    assert workspace.transcript == state.transcript
    assert workspace.summary_state == "failed"
    assert workspace.summary is None
