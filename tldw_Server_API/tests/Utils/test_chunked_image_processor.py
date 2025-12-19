import base64

import pytest

from tldw_Server_API.app.core.Utils import chunked_image_processor as cip


@pytest.mark.asyncio
async def test_decode_base64_image_chunked_handles_boundary():
    data = b"abcdefghijklmnopqrstuvwxyz0123456789"
    b64 = base64.b64encode(data).decode("ascii")

    parts = []
    async for chunk in cip.decode_base64_image_chunked(b64, chunk_size=7):
        parts.append(chunk)

    assert b"".join(parts) == data


@pytest.mark.asyncio
async def test_streaming_image_processor_preserves_bytes_without_pil(monkeypatch):
    monkeypatch.setattr(cip, "PIL_AVAILABLE", False)

    data = b"not-really-an-image"
    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    processor = cip.StreamingImageProcessor(max_memory_mb=1)
    ok, image_data, mime_type, error = await processor.process_image_url(
        data_url,
        max_size_bytes=len(data) + 10,
    )

    assert ok is True
    assert image_data == data
    assert mime_type == "image/png"
    assert error == ""
