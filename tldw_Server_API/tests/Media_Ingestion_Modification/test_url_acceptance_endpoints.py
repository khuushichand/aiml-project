import asyncio
from pathlib import Path
from typing import Dict, Tuple

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app_instance, app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, _single_user_instance
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user


class AsyncResponseStub:
    def __init__(self, final_url: str, headers: Dict[str, str], content: bytes):
        # Simulate httpx.URL on attribute access
        class _URL:
            def __init__(self, url: str):
                self._url = url
                self.path = Path(url).name if "/" in url else url

            def __str__(self):
                return self._url

        self.url = _URL(final_url)
        self.headers = headers or {}
        self._content = content or b""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def aiter_bytes(self, chunk_size: int = 8192):
        yield self._content


class AsyncClientFake:
    TABLE: Dict[str, Tuple[str, Dict[str, str], bytes]] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    # stream("GET", url, follow_redirects=True, timeout=...)
    def stream(self, method: str, url: str, **kwargs):
        if method != "GET":
            raise AssertionError("AsyncClientFake supports only GET in tests")
        if url not in self.TABLE:
            raise AssertionError(f"No stub configured for URL: {url}")
        final_url, headers, content = self.TABLE[url]
        return AsyncResponseStub(final_url, headers, content)


@pytest.fixture(autouse=True)
def patch_httpx_asyncclient(monkeypatch):
    # Patch the AsyncClient used by endpoints module only
    import tldw_Server_API.app.api.v1.endpoints.media as media_endpoints
    monkeypatch.setattr(media_endpoints.httpx, "AsyncClient", AsyncClientFake)
    yield
    AsyncClientFake.TABLE = {}


@pytest.fixture(scope="module")
def client():
    def _override_get_request_user_proc_test():
        _single_user_instance.id = 1
        return _single_user_instance

    async def _fake_get_media_db_for_user():
        class _FakeDB:
            def close_all_connections(self):
                return None
        yield _FakeDB()

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_request_user] = _override_get_request_user_proc_test
    app.dependency_overrides[get_media_db_for_user] = _fake_get_media_db_for_user

    with TestClient(fastapi_app_instance) as c:
        yield c

    app.dependency_overrides = original_overrides


@pytest.fixture
def dummy_headers():
    return {"token": "dummy"}


def _stub_url(url: str, *, final: str = None, headers: Dict[str, str] = None, body: bytes = None):
    AsyncClientFake.TABLE[url] = (final or url, headers or {}, body or b"TEST")


########################
# EBOOKS
########################

@pytest.mark.parametrize(
    "desc,url,final,headers,expect_status,expect_error",
    [
        ("suffix .epub", "http://t/x.epub", None, {}, 207, None),
        (
            "content-disposition .epub",
            "http://t/download",
            None,
            {"content-disposition": 'attachment; filename="book.epub"'},
            207,
            None,
        ),
        (
            "content-type epub+zip",
            "http://t/any",
            None,
            {"content-type": "application/epub+zip"},
            207,
            None,
        ),
        (
            "reject unknown",
            "http://t/bin",
            None,
            {"content-type": "application/octet-stream"},
            207,
            "allowed extension",
        ),
    ],
)
def test_ebooks_url_acceptance(desc, url, final, headers, expect_status, expect_error, client, dummy_headers, monkeypatch):
    # Stub HTTP
    _stub_url(url, final=final, headers=headers)

    # Stub processing to avoid heavy EPUB parsing
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib as books

    def fake_process_epub(**kwargs):
        return {
            "status": "Success",
            "input_ref": kwargs.get("file_path"),
            "processing_source": kwargs.get("file_path"),
            "media_type": "ebook",
            "content": "ok",
            "metadata": {"title": "t", "author": "a", "raw": {}},
            "chunks": [],
            "analysis": None,
            "keywords": [],
            "warnings": None,
            "error": None,
            "analysis_details": {},
        }

    monkeypatch.setattr(books, "process_epub", fake_process_epub)

    resp = client.post(
        "/api/v1/media/process-ebooks",
        data={"urls": [url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )

    # For suffix/content-disposition/content-type acceptance, downstream processing returns Success.
    # For reject, endpoint returns 207 with Error result.
    if expect_error:
        assert resp.status_code == 207
        data = resp.json()
        assert any("Error" == r.get("status") for r in data.get("results", []))
        # check the error message mentions allowed extension
        assert any(expect_error in (r.get("error") or "") for r in data["results"]) \
            or any(expect_error in e for e in data.get("errors", []))
    else:
        assert resp.status_code in (200, 207)
        data = resp.json()
        # Since we stubbed process_epub to succeed, expect one Success
        assert any("Success" == r.get("status") for r in data.get("results", []))


########################
# PDFs
########################

@pytest.mark.parametrize(
    "desc,url,final,headers,expect_error",
    [
        ("suffix .pdf", "http://t/x.pdf", None, {}, None),
        ("content-disposition .pdf", "http://t/dl", None, {"content-disposition": 'attachment; filename="p.pdf"'}, None),
        ("content-type application/pdf", "http://t/any", None, {"content-type": "application/pdf"}, None),
        ("reject unknown", "http://t/bin", None, {"content-type": "application/octet-stream"}, "allowed extension"),
    ],
)
def test_pdfs_url_acceptance(desc, url, final, headers, expect_error, client, dummy_headers, monkeypatch):
    _stub_url(url, final=final, headers=headers, body=b"%PDF-1.4\n...")

    # Stub processor
    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_lib

    async def fake_process_pdf_task(**kwargs):
        return {
            "status": "Success",
            "input_ref": kwargs.get("filename"),
            "processing_source": kwargs.get("filename"),
            "media_type": "pdf",
            "parser_used": "pymupdf4llm",
            "content": "ok",
            "metadata": {},
            "chunks": [],
            "analysis": None,
            "keywords": [],
            "warnings": None,
            "error": None,
            "analysis_details": {},
        }

    monkeypatch.setattr(pdf_lib, "process_pdf_task", fake_process_pdf_task)

    resp = client.post(
        "/api/v1/media/process-pdfs",
        data={"urls": [url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )

    if expect_error:
        assert resp.status_code == 207
        data = resp.json()
        assert any("Error" == r.get("status") for r in data.get("results", []))
        assert any("allowed extension" in (r.get("error") or "") for r in data["results"]) \
            or any("allowed extension" in e for e in data.get("errors", []))
    else:
        assert resp.status_code in (200, 207)
        data = resp.json()
        assert any("Success" == r.get("status") for r in data.get("results", []))


########################
# Documents
########################

@pytest.mark.parametrize(
    "desc,url,final,headers,expect_error",
    [
        ("suffix .txt", "http://t/x.txt", None, {"content-type": "text/plain"}, None),
        ("content-disposition .md", "http://t/dl", None, {"content-disposition": 'attachment; filename="d.md"'}, None),
        ("content-type text/html", "http://t/any", None, {"content-type": "text/html"}, None),
        ("content-type application/xhtml+xml", "http://t/xhtml", None, {"content-type": "application/xhtml+xml"}, None),
        ("content-type text/xml", "http://t/xml", None, {"content-type": "text/xml"}, None),
        ("content-type application/rtf", "http://t/rtf", None, {"content-type": "application/rtf"}, None),
        ("content-type application/vnd.openxmlformats-officedocument.wordprocessingml.document", "http://t/docx", None, {"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, None),
        ("reject unknown", "http://t/bin", None, {"content-type": "application/octet-stream"}, "allowed extension"),
    ],
)
def test_documents_url_acceptance(desc, url, final, headers, expect_error, client, dummy_headers, monkeypatch):
    _stub_url(url, final=final, headers=headers, body=b"DATA")

    # Stub processor
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs

    def fake_process_document_content(**kwargs):
        return {
            "status": "Success",
            "input_ref": str(kwargs.get("doc_path")),
            "processing_source": str(kwargs.get("doc_path")),
            "media_type": "document",
            "source_format": Path(str(kwargs.get("doc_path"))).suffix.lstrip("."),
            "content": "ok",
            "metadata": {},
            "chunks": [],
            "analysis": None,
            "analysis_details": {},
            "keywords": [],
            "error": None,
            "warnings": None,
        }

    monkeypatch.setattr(docs, "process_document_content", fake_process_document_content)

    resp = client.post(
        "/api/v1/media/process-documents",
        data={"urls": [url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )

    if expect_error:
        assert resp.status_code == 207
        data = resp.json()
        assert any("Error" == r.get("status") for r in data.get("results", []))
        assert any("allowed extension" in (r.get("error") or "") for r in data["results"]) \
            or any("allowed extension" in e for e in data.get("errors", []))
    else:
        assert resp.status_code in (200, 207)
        data = resp.json()
        assert any("Success" == r.get("status") for r in data.get("results", []))


########################
# Code
########################

@pytest.mark.parametrize(
    "desc,url,final,headers,expect_error",
    [
        ("suffix .py", "http://t/x.py", None, {}, None),
        ("content-disposition .ts", "http://t/dl", None, {"content-disposition": 'attachment; filename="f.ts"'}, None),
        ("reject unknown", "http://t/bin", None, {"content-type": "application/octet-stream"}, "allowed extension"),
    ],
)
def test_code_url_acceptance(desc, url, final, headers, expect_error, client, dummy_headers):
    _stub_url(url, final=final, headers=headers, body=b"print('hi')\n")

    resp = client.post(
        "/api/v1/media/process-code",
        data={"urls": [url], "perform_chunking": "false"},
        headers=dummy_headers,
    )

    if expect_error:
        assert resp.status_code == 207
        data = resp.json()
        assert any("Error" == r.get("status") for r in data.get("results", []))
        assert any("allowed extension" in (r.get("error") or "") for r in data["results"]) \
            or any("allowed extension" in e for e in data.get("errors", []))
    else:
        assert resp.status_code in (200, 207)
        data = resp.json()
        assert any("Success" == r.get("status") for r in data.get("results", []))


def test_code_url_acceptance_redirect_final_suffix(client, dummy_headers):
    url = "http://t/dl"
    final = "http://t/file.rs"
    _stub_url(url, final=final, headers={}, body=b"fn main() {}\n")

    resp = client.post(
        "/api/v1/media/process-code",
        data={"urls": [url], "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code in (200, 207)
    assert any(r.get("status") == "Success" for r in resp.json().get("results", []))


def test_code_mixed_urls_multi_status(client, dummy_headers):
    ok_url = "http://t/good.py"
    bad_url = "http://t/unknown"
    _stub_url(ok_url, headers={}, body=b"def x():\n    return 1\n")
    _stub_url(bad_url, headers={"content-type": "application/octet-stream"})

    resp = client.post(
        "/api/v1/media/process-code",
        data={"urls": [ok_url, bad_url], "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code == 207
    data = resp.json()
    assert any(r.get("status") == "Success" for r in data.get("results", []))
    assert any(r.get("status") == "Error" for r in data.get("results", []))


########################
# Redirect final suffix acceptance
########################

def test_ebooks_url_acceptance_redirect_final_suffix(client, dummy_headers, monkeypatch):
    url = "http://t/dl"
    final = "http://t/file.epub"
    _stub_url(url, final=final, headers={})

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib as books

    def fake_process_epub(**kwargs):
        return {"status": "Success", "input_ref": kwargs.get("file_path"), "processing_source": kwargs.get("file_path"), "media_type": "ebook", "content": "ok", "metadata": {}, "chunks": [], "analysis": None, "keywords": [], "warnings": None, "error": None, "analysis_details": {}}

    monkeypatch.setattr(books, "process_epub", fake_process_epub)

    resp = client.post(
        "/api/v1/media/process-ebooks",
        data={"urls": [url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code in (200, 207)
    assert any(r.get("status") == "Success" for r in resp.json().get("results", []))


def test_pdfs_url_acceptance_redirect_final_suffix(client, dummy_headers, monkeypatch):
    url = "http://t/dl"
    final = "http://t/file.pdf"
    _stub_url(url, final=final, headers={}, body=b"%PDF-1.4\n...")

    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_lib

    async def fake_process_pdf_task(**kwargs):
        return {"status": "Success", "input_ref": kwargs.get("filename"), "processing_source": kwargs.get("filename"), "media_type": "pdf", "parser_used": "pymupdf4llm", "content": "ok", "metadata": {}, "chunks": [], "analysis": None, "keywords": [], "warnings": None, "error": None, "analysis_details": {}}

    monkeypatch.setattr(pdf_lib, "process_pdf_task", fake_process_pdf_task)

    resp = client.post(
        "/api/v1/media/process-pdfs",
        data={"urls": [url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code in (200, 207)
    assert any(r.get("status") == "Success" for r in resp.json().get("results", []))


def test_documents_url_acceptance_redirect_final_suffix(client, dummy_headers, monkeypatch):
    url = "http://t/dl"
    final = "http://t/file.html"
    _stub_url(url, final=final, headers={}, body=b"<html>ok</html>")

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs

    def fake_process_document_content(**kwargs):
        p = str(kwargs.get("doc_path"))
        return {"status": "Success", "input_ref": p, "processing_source": p, "media_type": "document", "source_format": Path(p).suffix.lstrip("."), "content": "ok", "metadata": {}, "chunks": [], "analysis": None, "analysis_details": {}, "keywords": [], "error": None, "warnings": None}

    monkeypatch.setattr(docs, "process_document_content", fake_process_document_content)

    resp = client.post(
        "/api/v1/media/process-documents",
        data={"urls": [url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code in (200, 207)
    assert any(r.get("status") == "Success" for r in resp.json().get("results", []))


########################
# Mixed batches (expect 207)
########################

def test_ebooks_mixed_urls_multi_status(client, dummy_headers, monkeypatch):
    ok_url = "http://t/book"
    bad_url = "http://t/unknown"
    _stub_url(ok_url, headers={"content-disposition": 'attachment; filename="a.epub"'})
    _stub_url(bad_url, headers={"content-type": "application/octet-stream"})

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib as books

    def fake_process_epub(**kwargs):
        return {"status": "Success", "input_ref": kwargs.get("file_path"), "processing_source": kwargs.get("file_path"), "media_type": "ebook", "content": "ok", "metadata": {}, "chunks": [], "analysis": None, "keywords": [], "warnings": None, "error": None, "analysis_details": {}}

    monkeypatch.setattr(books, "process_epub", fake_process_epub)

    resp = client.post(
        "/api/v1/media/process-ebooks",
        data={"urls": [ok_url, bad_url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code == 207
    data = resp.json()
    assert any(r.get("status") == "Success" for r in data.get("results", []))
    assert any(r.get("status") == "Error" for r in data.get("results", []))


def test_pdfs_mixed_urls_multi_status(client, dummy_headers, monkeypatch):
    ok_url = "http://t/x.pdf"
    bad_url = "http://t/unknown"
    _stub_url(ok_url, headers={"content-type": "application/pdf"}, body=b"%PDF-1.4\n...")
    _stub_url(bad_url, headers={"content-type": "application/octet-stream"})

    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_lib

    async def fake_process_pdf_task(**kwargs):
        return {"status": "Success", "input_ref": kwargs.get("filename"), "processing_source": kwargs.get("filename"), "media_type": "pdf", "parser_used": "pymupdf4llm", "content": "ok", "metadata": {}, "chunks": [], "analysis": None, "keywords": [], "warnings": None, "error": None, "analysis_details": {}}

    monkeypatch.setattr(pdf_lib, "process_pdf_task", fake_process_pdf_task)

    resp = client.post(
        "/api/v1/media/process-pdfs",
        data={"urls": [ok_url, bad_url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code == 207
    data = resp.json()
    assert any(r.get("status") == "Success" for r in data.get("results", []))
    assert any(r.get("status") == "Error" for r in data.get("results", []))


def test_documents_mixed_urls_multi_status(client, dummy_headers, monkeypatch):
    ok_url = "http://t/page"
    bad_url = "http://t/unknown"
    _stub_url(ok_url, headers={"content-type": "text/html"}, body=b"<html>ok</html>")
    _stub_url(bad_url, headers={"content-type": "application/octet-stream"})

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs

    def fake_process_document_content(**kwargs):
        p = str(kwargs.get("doc_path"))
        return {"status": "Success", "input_ref": p, "processing_source": p, "media_type": "document", "source_format": Path(p).suffix.lstrip("."), "content": "ok", "metadata": {}, "chunks": [], "analysis": None, "analysis_details": {}, "keywords": [], "error": None, "warnings": None}

    monkeypatch.setattr(docs, "process_document_content", fake_process_document_content)

    resp = client.post(
        "/api/v1/media/process-documents",
        data={"urls": [ok_url, bad_url], "perform_analysis": "false", "perform_chunking": "false"},
        headers=dummy_headers,
    )
    assert resp.status_code == 207
    data = resp.json()
    assert any(r.get("status") == "Success" for r in data.get("results", []))
    assert any(r.get("status") == "Error" for r in data.get("results", []))


########################
# Negative content types (application/msword)
########################

@pytest.mark.parametrize("endpoint", [
    "/api/v1/media/process-ebooks",
    "/api/v1/media/process-pdfs",
    "/api/v1/media/process-documents",
])
def test_reject_msword_content_type(endpoint, client, dummy_headers):
    url = "http://t/msword"
    # application/msword should be rejected by all three endpoints
    _stub_url(url, headers={"content-type": "application/msword"}, body=b"...")

    resp = client.post(endpoint, data={"urls": [url], "perform_analysis": "false", "perform_chunking": "false"}, headers=dummy_headers)
    # Multi-status with an error result
    assert resp.status_code == 207
    data = resp.json()
    assert any(r.get("status") == "Error" for r in data.get("results", []))
    # Error message must mention allowed extension or content-type unsupported
    msg_pool = [r.get("error") or "" for r in data.get("results", [])] + data.get("errors", [])
    assert any("allowed extension" in m or "unsupported" in m for m in msg_pool)
