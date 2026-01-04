import io
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger


class _StubUsageLogger:
    def log_event(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@pytest.fixture
def media_processing_client(client_user_only):
    async def _override_get_media_db_for_user():
        class _FakeDB:
            def close_all_connections(self):
                return None
        yield _FakeDB()

    original_db_override = app.dependency_overrides.get(get_media_db_for_user)
    original_usage_override = app.dependency_overrides.get(get_usage_event_logger)
    app.dependency_overrides[get_media_db_for_user] = _override_get_media_db_for_user
    app.dependency_overrides[get_usage_event_logger] = lambda: _StubUsageLogger()

    try:
        yield client_user_only
    finally:
        if original_db_override is None:
            app.dependency_overrides.pop(get_media_db_for_user, None)
        else:
            app.dependency_overrides[get_media_db_for_user] = original_db_override
        if original_usage_override is None:
            app.dependency_overrides.pop(get_usage_event_logger, None)
        else:
            app.dependency_overrides[get_usage_event_logger] = original_usage_override


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
