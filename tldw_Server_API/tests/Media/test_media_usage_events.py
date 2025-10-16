import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger


pytestmark = pytest.mark.unit


class _DummyLogger:
    def __init__(self):
        self.events = []

    def log_event(self, name, resource_id=None, tags=None, metadata=None):
        self.events.append((name, resource_id, tags, metadata))


class _StubQuotaService:
    async def check_quota(self, user_id, size_bytes, raise_on_exceed=False):
        # Always allow in tests
        return True, {
            "current_usage_mb": 0,
            "new_size_mb": float(size_bytes) / (1024 * 1024),
            "quota_mb": 999999,
            "available_mb": 999999,
        }


@pytest.fixture()
def client_with_overrides(monkeypatch):
    dummy = _DummyLogger()

    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def override_logger():
        return dummy

    # Patch quota service to avoid DB access in tests
    import tldw_Server_API.app.services.storage_quota_service as quota_mod

    monkeypatch.setattr(quota_mod, "get_storage_quota_service", lambda: _StubQuotaService())

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_usage_event_logger] = override_logger

    with TestClient(fastapi_app) as client:
        yield client, dummy

    fastapi_app.dependency_overrides.clear()


def test_ebooks_process_usage_event_logged(client_with_overrides, monkeypatch):
    client, dummy = client_with_overrides

    # Stub heavy processing to return immediately
    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    def _stub_process_epub(**kwargs):
        return {
            "status": "Success",
            "content": "",
            "metadata": {"title": "stub-ebook"},
        }

    monkeypatch.setattr(media_mod.books, "process_epub", _stub_process_epub)

    files = [
        ("files", ("sample.epub", b"fake", "application/epub+zip")),
    ]

    r = client.post("/api/v1/media/process-ebooks", files=files)
    assert r.status_code == 200, r.text
    assert any(e[0] == "media.process.ebook" for e in dummy.events)


def test_documents_process_usage_event_logged(client_with_overrides, monkeypatch):
    client, dummy = client_with_overrides

    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    def _stub_process_document_content(**kwargs):
        return {
            "status": "Success",
            "content": "Hello",
            "metadata": {"title": "stub-doc"},
        }

    monkeypatch.setattr(media_mod.docs, "process_document_content", _stub_process_document_content)

    files = [
        ("files", ("note.txt", b"hi", "text/plain")),
    ]

    r = client.post("/api/v1/media/process-documents", files=files)
    assert r.status_code == 200, r.text
    assert any(e[0] == "media.process.document" for e in dummy.events)


def test_pdfs_process_usage_event_logged(client_with_overrides, monkeypatch):
    client, dummy = client_with_overrides

    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    async def _stub_process_pdf_task(**kwargs):
        return {
            "status": "Success",
            "content": "",
            "metadata": {"title": "stub-pdf"},
        }

    monkeypatch.setattr(media_mod.pdf_lib, "process_pdf_task", _stub_process_pdf_task)

    files = [
        ("files", ("paper.pdf", b"%PDF-1.4\n", "application/pdf")),
    ]

    r = client.post("/api/v1/media/process-pdfs", files=files)
    assert r.status_code == 200, r.text
    assert any(e[0] == "media.process.pdf" for e in dummy.events)

