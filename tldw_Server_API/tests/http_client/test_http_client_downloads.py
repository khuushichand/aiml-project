import pytest
from pathlib import Path


pytestmark = pytest.mark.unit


def _has_httpx():


     try:
        import httpx  # noqa: F401
        return True
    except Exception:
        return False


requires_httpx = pytest.mark.skipif(not _has_httpx(), reason="httpx not installed")


@requires_httpx
def test_download_checksum_mismatch(tmp_path: Path):
    import httpx
    from tldw_Server_API.app.core.http_client import download, create_client
    from tldw_Server_API.app.core.exceptions import DownloadError

    payload = b"abc" * 10

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=payload, headers={"Content-Length": str(len(payload))})

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        with pytest.raises(DownloadError):
            download(url="http://93.184.216.34/file", dest=tmp_path / "f.bin", client=client, checksum="deadbeef")
    finally:
        client.close()


@requires_httpx
def test_download_content_length_mismatch(tmp_path: Path):
    import httpx
    from tldw_Server_API.app.core.http_client import download, create_client
    from tldw_Server_API.app.core.exceptions import DownloadError

    payload = b"abcdef"

    def handler(request: httpx.Request) -> httpx.Response:
        # Lie about content-length
        return httpx.Response(200, request=request, content=payload, headers={"Content-Length": "999"})

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        with pytest.raises(DownloadError):
            download(url="http://93.184.216.34/file", dest=tmp_path / "f.bin", client=client)
    finally:
        client.close()


@requires_httpx
def test_download_resume_true_206(tmp_path: Path):
    import httpx
    from tldw_Server_API.app.core.http_client import download, create_client

    # First attempt: create a partial file, then resume with 206
    start = (tmp_path / "f.bin.part").write_bytes(b"hello ")

    def handler(request: httpx.Request) -> httpx.Response:
        # Expect Range header and return remainder only
        assert request.headers.get("Range") == "bytes=6-"
        return httpx.Response(206, request=request, content=b"world")

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        out = download(url="http://93.184.216.34/file", dest=tmp_path / "f.bin", client=client, resume=True)
        assert out.read_bytes() == b"hello world"
    finally:
        client.close()


@requires_httpx
def test_download_resume_range_ignored_returns_200(tmp_path: Path):
    import httpx
    from tldw_Server_API.app.core.http_client import download, create_client

    # Create a partial file, but server ignores Range and returns 200 with full body
    (tmp_path / "f.bin.part").write_bytes(b"hello ")

    observed = {"range": None}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["range"] = request.headers.get("Range")
        return httpx.Response(200, request=request, content=b"hello world")

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        out = download(url="http://93.184.216.34/file", dest=tmp_path / "f.bin", client=client, resume=True)
        # Server ignored Range; client should overwrite and produce full content
        assert out.read_bytes() == b"hello world"
        # Ensure Range header was sent
        assert observed["range"] == "bytes=6-"
    finally:
        client.close()


@requires_httpx
def test_download_strict_content_type(tmp_path: Path):
    import httpx
    from tldw_Server_API.app.core.http_client import download, create_client
    from tldw_Server_API.app.core.exceptions import DownloadError

    payload = b"%PDF-1.5..."

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=payload, headers={"Content-Type": "application/pdf"})

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        # Matching content-type succeeds
        out = download(url="http://93.184.216.34/file.pdf", dest=tmp_path / "a.pdf", client=client, require_content_type="application/pdf")
        assert out.exists()
        # Non-matching content-type fails
        with pytest.raises(DownloadError):
            download(url="http://93.184.216.34/file.pdf", dest=tmp_path / "b.pdf", client=client, require_content_type="text/plain")
    finally:
        client.close()


@requires_httpx
def test_download_disk_quota_guard(tmp_path: Path):
    import httpx
    from tldw_Server_API.app.core.http_client import download, create_client
    from tldw_Server_API.app.core.exceptions import DownloadError

    payload = b"x" * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=payload, headers={"Content-Length": str(len(payload))})

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        with pytest.raises(DownloadError):
            download(url="http://93.184.216.34/file.bin", dest=tmp_path / "q.bin", client=client, max_bytes_total=100)
    finally:
        client.close()
