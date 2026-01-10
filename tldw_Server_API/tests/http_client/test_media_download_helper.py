import asyncio
from pathlib import Path

import httpx
import pytest

from tldw_Server_API.app.api.v1.endpoints.media import _download_url_async


class _MockTransport(httpx.MockTransport):
    pass


@pytest.mark.asyncio
async def test_download_url_async_pdf_success(tmp_path, monkeypatch):
    url = "http://example.com/file.pdf"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method.upper() == "HEAD":
            return httpx.Response(200, headers={"content-type": "application/pdf", "content-length": "12"})
        if request.method.upper() == "GET":
            body = b"%PDF-1.4test"
            return httpx.Response(200, headers={"content-type": "application/pdf", "content-length": str(len(body))}, content=body)
        return httpx.Response(405)

    transport = _MockTransport(handler)

    # Patch central factories to use MockTransport
    import tldw_Server_API.app.core.http_client as hc

    def _mk_client(**kwargs):

             to = kwargs.get("timeout", 10.0)
        return httpx.Client(timeout=to, transport=transport)

    def _mk_async_client(**kwargs):

             to = kwargs.get("timeout", 10.0)
        return httpx.AsyncClient(timeout=to, transport=transport)

    monkeypatch.setattr(hc, "create_client", _mk_client, raising=True)
    monkeypatch.setattr(hc, "create_async_client", _mk_async_client, raising=True)

    # Ensure the adownload used by media module does not bypass our transport
    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    async def _fake_adownload(**kwargs):
        dest = Path(kwargs.get("dest"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF-1.4test")
        return dest

    monkeypatch.setattr(media_mod, "_m_adownload", _fake_adownload, raising=True)

    monkeypatch.setenv("EGRESS_ALLOWLIST", "example.com")
    async with httpx.AsyncClient(transport=transport) as client:
        out_path = await _download_url_async(
            client=client,
            url=url,
            target_dir=Path(tmp_path),
            allowed_extensions={".pdf"},
            check_extension=True,
        )
    assert out_path.exists()
    assert out_path.suffix == ".pdf"
    data = out_path.read_bytes()
    assert data.startswith(b"%PDF-1.4")


@pytest.mark.asyncio
async def test_download_url_async_reject_non_pdf(tmp_path, monkeypatch):
    url = "http://example.com/page"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method.upper() == "HEAD":
            return httpx.Response(200, headers={"content-type": "text/html", "content-length": "20"})
        if request.method.upper() == "GET":
            body = b"<html>not a pdf</html>"
            return httpx.Response(200, headers={"content-type": "text/html", "content-length": str(len(body))}, content=body)
        return httpx.Response(405)

    transport = _MockTransport(handler)

    import tldw_Server_API.app.core.http_client as hc

    def _mk_client(**kwargs):

             to = kwargs.get("timeout", 10.0)
        return httpx.Client(timeout=to, transport=transport)

    def _mk_async_client(**kwargs):

             to = kwargs.get("timeout", 10.0)
        return httpx.AsyncClient(timeout=to, transport=transport)

    monkeypatch.setattr(hc, "create_client", _mk_client, raising=True)
    monkeypatch.setattr(hc, "create_async_client", _mk_async_client, raising=True)

    monkeypatch.setenv("EGRESS_ALLOWLIST", "example.com")
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError):
            await _download_url_async(
                client=client,
                url=url,
                target_dir=Path(tmp_path),
                allowed_extensions={".pdf"},
                check_extension=True,
            )
