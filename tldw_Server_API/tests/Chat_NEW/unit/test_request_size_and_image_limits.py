"""
Unit tests for request size validator with data:image payloads and image size limits.

Validates that:
- Large data:image payloads are accepted by the request size validator due to redaction.
- Image validation still rejects oversized images based on configured byte limits.
"""

import json
import os
import pytest

from tldw_Server_API.app.api.v1.schemas.chat_validators import validate_request_size
from tldw_Server_API.app.core.Utils.image_validation import validate_image_url, get_max_base64_bytes


@pytest.mark.unit
def test_validator_allows_large_data_image_when_redacted(monkeypatch):
    """Ensure validate_request_size does not penalize large data:image payloads.

    We lower the overall JSON size cap to a small number to keep the test fast,
    then include a relatively large base64 image. The validator should redact
    the base64 body and accept the request size.
    """
    # Keep cap small to avoid generating huge strings
    monkeypatch.setenv("CHAT_REQUEST_MAX_SIZE", "1000")

    # Construct a request-like object with a data:image payload that would exceed 1k chars
    large_b64 = "A" * 5000
    req_obj = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{large_b64}"}},
                ],
            }
        ],
    }

    # As dict (object) - validator will sanitize recursively
    assert validate_request_size(req_obj) is True

    # As a JSON string - validator will redact in-string data:image as well
    req_json = json.dumps(req_obj)
    assert validate_request_size(req_json) is True


@pytest.mark.unit
def test_image_limit_rejects_oversized_data_image(monkeypatch):
    """Ensure validate_image_url rejects too-large base64 images by size.

    We set the max image size to 1 MB and craft a data URI whose base64 length
    exceeds the allowed string length threshold. The validator should return False.
    """
    monkeypatch.setenv("CHAT_IMAGE_MAX_MB", "1")

    # Resolve the configured max, then exceed the base64 string threshold
    max_bytes = get_max_base64_bytes()
    # Base64 length for N bytes is roughly ceil(4/3 * N); exceed it by some margin
    too_long_b64_len = int(max_bytes * 4 / 3) + 200
    oversized_b64 = "A" * too_long_b64_len

    url = f"data:image/png;base64,{oversized_b64}"
    is_valid, mime, decoded = validate_image_url(url)
    assert is_valid is False
    # MIME should still reflect the declared type
    assert mime == "image/png"
    assert decoded is None
