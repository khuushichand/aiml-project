"""Unit tests for PNG character card export encoding."""

import base64
import json

import pytest


@pytest.mark.unit
def test_encode_png_with_chara_metadata_no_image():
    """Encoding with no source image produces a valid PNG with chara tEXt."""
    from tldw_Server_API.app.api.v1.endpoints.characters_endpoint import (
        _encode_png_with_chara_metadata,
    )

    card = {"spec": "chara_card_v2", "data": {"name": "Alice"}}
    card_json = json.dumps(card)
    png_bytes = _encode_png_with_chara_metadata(None, card_json)

    # Should start with PNG signature
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    # Should contain the chara tEXt chunk
    assert b"chara" in png_bytes

    # Roundtrip: extract the base64 payload from the tEXt chunk
    idx = png_bytes.find(b"tEXtchara\x00")
    assert idx > 0, "tEXt chunk with 'chara' keyword not found"
    # After "tEXt" (4) + "chara" (5) + NUL (1) = 10 bytes from chunk type
    text_start = idx + len(b"tEXtchara\x00")
    # Read until chunk CRC (find next known chunk type or end)
    # The text data ends 4 bytes before the next chunk length field
    # Simpler: just decode from text_start to find valid base64
    remaining = png_bytes[text_start:]
    # b64 data is followed by CRC (4 bytes) then next chunk
    # Extract until we hit non-base64 characters
    b64_chars = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    b64_end = 0
    for i, byte in enumerate(remaining):
        if byte in b64_chars:
            b64_end = i + 1
        else:
            break

    b64_payload = remaining[:b64_end].decode("ascii")
    decoded = base64.b64decode(b64_payload).decode("utf-8")
    roundtripped = json.loads(decoded)
    assert roundtripped["data"]["name"] == "Alice"


@pytest.mark.unit
def test_encode_png_with_chara_metadata_with_source_image():
    """Encoding with a source PNG injects metadata before IEND."""
    import struct
    import zlib

    from tldw_Server_API.app.api.v1.endpoints.characters_endpoint import (
        _encode_png_with_chara_metadata,
    )

    # Build a minimal valid PNG
    png_header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr_type = b"IHDR"
    ihdr = (
        struct.pack(">I", len(ihdr_data))
        + ihdr_type
        + ihdr_data
        + struct.pack(">I", zlib.crc32(ihdr_type + ihdr_data) & 0xFFFFFFFF)
    )
    raw_data = zlib.compress(b"\x00\x00\x00\x00\x00")
    idat_type = b"IDAT"
    idat = (
        struct.pack(">I", len(raw_data))
        + idat_type
        + raw_data
        + struct.pack(">I", zlib.crc32(idat_type + raw_data) & 0xFFFFFFFF)
    )
    iend_type = b"IEND"
    iend = struct.pack(">I", 0) + iend_type + struct.pack(">I", zlib.crc32(iend_type) & 0xFFFFFFFF)
    source_png = png_header + ihdr + idat + iend

    card = {"spec": "chara_card_v2", "data": {"name": "Bob"}}
    card_json = json.dumps(card)
    result = _encode_png_with_chara_metadata(source_png, card_json)

    assert result[:8] == b"\x89PNG\r\n\x1a\n"
    assert b"chara" in result
    # IEND should still be present at the end
    assert result[-8:-4] == b"IEND"
    # Result should be larger than source (metadata added)
    assert len(result) > len(source_png)
