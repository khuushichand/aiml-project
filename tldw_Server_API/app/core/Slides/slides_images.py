"""Image validation helpers for Slides metadata."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from tldw_Server_API.app.core.Slides.slides_assets import SlidesAssetError, parse_slide_asset_ref

MAX_IMAGES_PER_SLIDE = 10
MAX_IMAGE_BYTES = 5 * 1024 * 1024

_ALLOWED_IMAGE_MIME = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}


class SlidesImageError(ValueError):
    """Raised when slide image metadata is invalid."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalize_image_mime(mime: str) -> str:
    value = (mime or "").strip().lower()
    if not value:
        raise SlidesImageError("image_mime_required")
    if value not in _ALLOWED_IMAGE_MIME:
        raise SlidesImageError("image_mime_invalid")
    if value == "image/jpg":
        return "image/jpeg"
    return value


def validate_images_payload(
    images: Any,
    *,
    max_images: int = MAX_IMAGES_PER_SLIDE,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> list[dict[str, Any]]:
    if images is None:
        return []
    if not isinstance(images, list):
        raise SlidesImageError("images_invalid")
    if len(images) > max_images:
        raise SlidesImageError("images_too_many")

    normalized: list[dict[str, Any]] = []
    for image in images:
        if not isinstance(image, dict):
            raise SlidesImageError("image_entry_invalid")
        asset_ref = image.get("asset_ref")
        if asset_ref is not None:
            try:
                parse_slide_asset_ref(asset_ref)
            except SlidesAssetError as exc:
                raise SlidesImageError("image_asset_ref_invalid") from exc
            data_b64 = image.get("data_b64")
            if isinstance(data_b64, str) and data_b64.strip():
                raise SlidesImageError("image_entry_conflicting_sources")
            mime = image.get("mime")
            normalized_mime = normalize_image_mime(str(mime or "")) if mime is not None else None
            image_id = image.get("id")
            if image_id is not None and not isinstance(image_id, str):
                raise SlidesImageError("image_id_invalid")
            alt = image.get("alt")
            if alt is not None and not isinstance(alt, str):
                raise SlidesImageError("image_alt_invalid")
            width = image.get("width")
            if width is not None and (not isinstance(width, int) or width <= 0):
                raise SlidesImageError("image_width_invalid")
            height = image.get("height")
            if height is not None and (not isinstance(height, int) or height <= 0):
                raise SlidesImageError("image_height_invalid")
            normalized.append(
                {
                    "id": image_id,
                    "asset_ref": str(asset_ref).strip(),
                    "mime": normalized_mime,
                    "alt": alt,
                    "width": width,
                    "height": height,
                }
            )
            continue
        data_b64 = image.get("data_b64")
        if not isinstance(data_b64, str) or not data_b64.strip():
            raise SlidesImageError("image_data_b64_required")
        mime = normalize_image_mime(str(image.get("mime") or ""))
        try:
            raw = base64.b64decode(data_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SlidesImageError("image_data_b64_invalid") from exc
        if len(raw) > max_bytes:
            raise SlidesImageError("image_data_too_large")

        image_id = image.get("id")
        if image_id is not None and not isinstance(image_id, str):
            raise SlidesImageError("image_id_invalid")
        alt = image.get("alt")
        if alt is not None and not isinstance(alt, str):
            raise SlidesImageError("image_alt_invalid")
        width = image.get("width")
        if width is not None and (not isinstance(width, int) or width <= 0):
            raise SlidesImageError("image_width_invalid")
        height = image.get("height")
        if height is not None and (not isinstance(height, int) or height <= 0):
            raise SlidesImageError("image_height_invalid")

        normalized.append(
            {
                "id": image_id,
                "mime": mime,
                "data_b64": data_b64,
                "alt": alt,
                "width": width,
                "height": height,
            }
        )
    return normalized


def collect_image_alt_text(images: list[dict[str, Any]] | None) -> list[str]:
    if not images:
        return []
    alt_texts: list[str] = []
    for image in images:
        alt = image.get("alt") if isinstance(image, dict) else None
        if isinstance(alt, str) and alt.strip():
            alt_texts.append(alt.strip())
    return alt_texts
