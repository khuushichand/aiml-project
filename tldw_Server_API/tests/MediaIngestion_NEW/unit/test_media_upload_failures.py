import io
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app_instance, app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    get_request_user,
    get_single_user_instance,
)
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger


class _StubUsageLogger:
    def log_event(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@pytest.fixture
def media_processing_client():
    # Ensure the singleton user object is primed before overrides touch it.
    singleton_user = get_single_user_instance()

    def _override_get_request_user():
        singleton_user.id = 1  # Guarantee deterministic id for tests
        return singleton_user

    async def _override_get_media_db_for_user():
        class _FakeDB:
            def close_all_connections(self):
                return None
        yield _FakeDB()

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_request_user] = _override_get_request_user
    app.dependency_overrides[get_media_db_for_user] = _override_get_media_db_for_user
    app.dependency_overrides[get_usage_event_logger] = lambda: _StubUsageLogger()

    try:
        with TestClient(fastapi_app_instance) as client:
            yield client
    finally:
        app.dependency_overrides = original_overrides


def test_process_videos_reports_rejected_upload(media_processing_client: TestClient):
    malicious_file = ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")

    response = media_processing_client.post(
        "/api/v1/media/process-videos",
        files={"files": malicious_file},
    )

    assert response.status_code == status.HTTP_207_MULTI_STATUS
    payload = response.json()
    assert payload["errors_count"] == 1
    assert payload["results"], "Expected results array with error entries"
    error_entry = payload["results"][0]
    assert error_entry["status"] == "Error"
    assert error_entry["input_ref"] == "malware.exe"
    assert any(".exe" in err for err in payload["errors"])


def test_process_audios_reports_rejected_upload(media_processing_client: TestClient):
    malicious_file = ("dangerous.exe", io.BytesIO(b"MZ"), "application/octet-stream")

    response = media_processing_client.post(
        "/api/v1/media/process-audios",
        files={"files": malicious_file},
    )

    assert response.status_code == status.HTTP_207_MULTI_STATUS
    payload = response.json()
    assert payload["errors_count"] == 1
    assert payload["results"], "Expected results array with error entries"
    error_entry = payload["results"][0]
    assert error_entry["status"] == "Error"
    assert error_entry["input_ref"] == "dangerous.exe"
    assert any(".exe" in err for err in payload["errors"])
