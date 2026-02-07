from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints import chatbooks as chatbooks_endpoints
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.Chatbooks.chatbook_models import ExportJob, ExportStatus


class _DummyAuditService:
    async def log_event(self, *args, **kwargs) -> None:
        return None


async def _override_user() -> User:
    return User(id=1, username="tester", email=None, is_active=True)


class _RejectingChatbookService:
    db = None

    async def import_chatbook(self, **kwargs):
        raise AssertionError("import_chatbook should not be called for invalid filenames")

    def preview_chatbook(self, *args, **kwargs):
        raise AssertionError("preview_chatbook should not be called for invalid filenames")


class _DownloadChatbookService:
    def __init__(self, export_dir: Path, job: ExportJob):
        self.export_dir = export_dir
        self._job = job
        self._jobs_backend = "core"

    def get_export_job(self, job_id: str):
        return self._job


def _make_app(service) -> FastAPI:
    app = FastAPI()
    app.include_router(chatbooks_endpoints.router, prefix="/api/v1")
    app.dependency_overrides[chatbooks_endpoints.get_chatbook_service] = lambda: service
    app.dependency_overrides[chatbooks_endpoints.get_request_user] = _override_user
    app.dependency_overrides[chatbooks_endpoints.get_audit_service_for_user] = lambda: _DummyAuditService()
    return app


def test_import_rejects_path_traversal_filename(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_db"))

    app = _make_app(_RejectingChatbookService())

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/chatbooks/import",
            files={"file": ("../evil.zip", b"notzip", "application/zip")},
            data={
                "conflict_resolution": "skip",
                "prefix_imported": "false",
                "import_media": "false",
                "import_embeddings": "false",
                "async_mode": "false",
            },
        )
    assert resp.status_code == 400, resp.text
    assert "filename" in resp.json().get("detail", "").lower()


def test_preview_rejects_path_traversal_filename(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_db"))

    app = _make_app(_RejectingChatbookService())

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/chatbooks/preview",
            files={"file": ("..\\evil.zip", b"notzip", "application/zip")},
        )
    assert resp.status_code == 400, resp.text
    assert "filename" in resp.json().get("detail", "").lower()


def test_download_rejects_output_path_outside_export_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_db"))

    export_dir = tmp_path / "exports"
    job_id = "11111111-1111-1111-1111-111111111111"
    job = ExportJob(
        job_id=job_id,
        user_id="1",
        status=ExportStatus.COMPLETED,
        chatbook_name="test",
        output_path=str(tmp_path / "outside.zip"),
    )
    service = _DownloadChatbookService(export_dir=export_dir, job=job)
    app = _make_app(service)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/chatbooks/download/{job_id}")
    assert resp.status_code == 403, resp.text
