import pytest


pytestmark = pytest.mark.unit


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
def quota_service_stub(monkeypatch):
    # Patch quota service globally to avoid DB access in tests
    import tldw_Server_API.app.services.storage_quota_service as quota_mod
    monkeypatch.setattr(quota_mod, "get_storage_quota_service", lambda: _StubQuotaService())
    yield


def test_ebooks_process_usage_event_logged(client_with_single_user, quota_service_stub, monkeypatch):
    client, usage_logger = client_with_single_user

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
    assert any(e[0] == "media.process.ebook" for e in usage_logger.events)


def test_documents_process_usage_event_logged(client_with_single_user, quota_service_stub, monkeypatch):
    client, usage_logger = client_with_single_user

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
    assert any(e[0] == "media.process.document" for e in usage_logger.events)


def test_pdfs_process_usage_event_logged(client_with_single_user, quota_service_stub, monkeypatch):
    client, usage_logger = client_with_single_user

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
    assert any(e[0] == "media.process.pdf" for e in usage_logger.events)
