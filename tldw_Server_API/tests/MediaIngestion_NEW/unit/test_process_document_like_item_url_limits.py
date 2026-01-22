from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import download_utils, persistence
from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import DEFAULT_MEDIA_TYPE_CONFIG


@pytest.mark.asyncio
async def test_process_document_like_item_url_oversize_rejected(tmp_path, monkeypatch):
    url = "http://example.com/file.pdf"

    body = b"x" * (1024 * 1024 + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method.upper() == "GET":
            return httpx.Response(
                200,
                headers={
                    "content-type": "application/pdf",
                    "content-length": str(len(body)),
                },
                content=body,
            )
        return httpx.Response(405)

    transport = httpx.MockTransport(handler)

    def _mk_async_client(**kwargs):
        timeout = kwargs.get("timeout", 10.0)
        return httpx.AsyncClient(timeout=timeout, transport=transport)

    monkeypatch.setattr(download_utils, "_create_async_client", _mk_async_client, raising=True)
    monkeypatch.setenv("EGRESS_ALLOWLIST", "example.com")
    monkeypatch.setitem(DEFAULT_MEDIA_TYPE_CONFIG["pdf"], "max_size_mb", 1)

    form_data = SimpleNamespace(
        title=None,
        author=None,
        keywords=None,
        perform_chunking=False,
        perform_analysis=False,
        api_name=None,
        custom_prompt=None,
        system_prompt=None,
        summarize_recursively=False,
        pdf_parsing_engine="pymupdf4llm",
    )

    result = await persistence.process_document_like_item(
        item_input_ref=url,
        processing_source=url,
        media_type="pdf",
        is_url=True,
        form_data=form_data,
        chunk_options=None,
        temp_dir=tmp_path,
        loop=asyncio.get_running_loop(),
        db_path=":memory:",
        client_id="test-client",
        user_id=None,
    )

    assert result.get("status") == "Error"
    assert "exceeds maximum allowed size" in str(result.get("error", "")).lower()
