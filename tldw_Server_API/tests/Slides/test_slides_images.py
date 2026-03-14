import pytest

from tldw_Server_API.app.core.Slides.slides_images import (
    MAX_IMAGES_PER_SLIDE,
    SlidesImageError,
    validate_images_payload,
)

_SAMPLE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAn8B9XgU1b0AAAAASUVORK5CYII="
)


def test_validate_images_payload_accepts_valid():
    images = [
        {
            "mime": "image/png",
            "data_b64": _SAMPLE_PNG_B64,
            "alt": "Logo",
            "width": 10,
            "height": 11,
        }
    ]
    normalized = validate_images_payload(images)
    assert normalized[0]["mime"] == "image/png"
    assert normalized[0]["alt"] == "Logo"


def test_validate_images_payload_accepts_output_asset_ref():
    images = [
        {
            "asset_ref": "output:123",
            "alt": "Cover",
            "width": 320,
        }
    ]
    normalized = validate_images_payload(images)
    assert normalized[0]["asset_ref"] == "output:123"
    assert normalized[0]["alt"] == "Cover"
    assert normalized[0]["width"] == 320


def test_validate_images_payload_rejects_invalid_mime():
    with pytest.raises(SlidesImageError) as exc:
        validate_images_payload([{"mime": "text/plain", "data_b64": _SAMPLE_PNG_B64}])
    assert exc.value.code == "image_mime_invalid"


def test_validate_images_payload_rejects_too_many_images():
    images = [{"mime": "image/png", "data_b64": _SAMPLE_PNG_B64}] * (MAX_IMAGES_PER_SLIDE + 1)
    with pytest.raises(SlidesImageError) as exc:
        validate_images_payload(images)
    assert exc.value.code == "images_too_many"
