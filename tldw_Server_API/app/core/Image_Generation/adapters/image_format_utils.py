"""Shared image parsing/format conversion helpers for image-generation adapters."""

from __future__ import annotations

import base64
import binascii
import contextlib
import io
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.http_client import fetch
from tldw_Server_API.app.core.Image_Generation.capabilities import ResolvedReferenceImage
from tldw_Server_API.app.core.Image_Generation.exceptions import ImageGenerationError

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency guard
    Image = None  # type: ignore


def decode_data_url(data_url: str) -> tuple[bytes, str]:
    header, _, encoded = data_url.partition(",")
    if not header.startswith("data:"):
        raise ImageGenerationError("invalid data URL")
    meta = header[5:]
    content_type = "application/octet-stream"
    content_type = meta.split(";", 1)[0] or content_type if ";" in meta else meta or content_type
    if ";base64" not in header:
        raise ImageGenerationError("unsupported data URL encoding")
    try:
        content = base64.b64decode(encoded)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise ImageGenerationError("invalid base64 data") from exc
    return content, content_type


def decode_base64_image(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise ImageGenerationError("invalid base64 image data") from exc


def maybe_decode_base64_image(encoded: str | None) -> bytes | None:
    if not isinstance(encoded, str):
        return None
    raw = encoded.strip()
    if not raw:
        return None
    if raw.startswith("data:"):
        try:
            content, _content_type = decode_data_url(raw)
            return content
        except ImageGenerationError:
            return None
    if any(ch.isspace() for ch in raw):
        return None
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, TypeError, ValueError):
        return None


def reference_image_data_url(reference_image: ResolvedReferenceImage) -> str:
    """Encode a normalized reference image into a Model Studio-compatible data URL."""

    content = reference_image.content
    if content is None:
        if not reference_image.temp_path:
            raise ImageGenerationError("invalid reference image data")
        try:
            content = Path(reference_image.temp_path).read_bytes()
        except Exception as exc:
            raise ImageGenerationError("invalid reference image data") from exc
    if not content:
        raise ImageGenerationError("invalid reference image data")

    mime_type = (reference_image.mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if not mime_type:
        mime_type = "application/octet-stream"
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def format_from_content_type(content_type: str) -> str | None:
    if not content_type:
        return None
    ctype = content_type.split(";", 1)[0].strip().lower()
    if ctype == "image/png":
        return "png"
    if ctype == "image/jpeg":
        return "jpg"
    if ctype == "image/webp":
        return "webp"
    return None


def format_from_bytes(content: bytes) -> str | None:
    if not content:
        return None
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "webp"
    return None


def content_type_for_format(fmt: str) -> str:
    if fmt == "png":
        return "image/png"
    if fmt == "jpg":
        return "image/jpeg"
    if fmt == "webp":
        return "image/webp"
    return "application/octet-stream"


def maybe_convert_format(
    content: bytes,
    content_type: str,
    actual_format: str | None,
    requested_format: str,
) -> tuple[bytes, str]:
    if requested_format == actual_format:
        return content, content_type
    if requested_format not in {"png", "jpg", "webp"}:
        raise ImageGenerationError(f"unsupported output format: {requested_format}")
    if actual_format is None and requested_format == "png":
        return content, content_type or "image/png"
    if Image is None:
        raise ImageGenerationError("Pillow is required for image format conversion")
    try:
        with Image.open(io.BytesIO(content)) as img:
            if requested_format == "jpg" and img.mode not in {"RGB"}:
                img = img.convert("RGB")
            if requested_format == "png" and img.mode in {"P"}:
                img = img.convert("RGBA")
            buf = io.BytesIO()
            save_format = {
                "jpg": "JPEG",
                "png": "PNG",
                "webp": "WEBP",
            }[requested_format]
            img.save(buf, format=save_format)
            converted = buf.getvalue()
    except Exception as exc:
        raise ImageGenerationError(f"failed to convert image: {exc}") from exc
    return converted, content_type_for_format(requested_format)


def fetch_image_bytes(
    url: str,
    *,
    timeout: int | float,
    headers: dict[str, Any] | None = None,
) -> tuple[bytes, str]:
    try:
        response = fetch(
            method="GET",
            url=url,
            headers=headers,
            timeout=timeout,
        )
    except Exception as exc:
        raise ImageGenerationError(f"image fetch failed: {exc}") from exc

    try:
        status = getattr(response, "status_code", None) or response.status_code
    except Exception:
        status = None
    if status and int(status) >= 400:
        with contextlib.suppress(Exception):
            response.close()
        raise ImageGenerationError(f"image fetch failed with status {status}")

    try:
        content = response.content
    except Exception as exc:
        with contextlib.suppress(Exception):
            response.close()
        raise ImageGenerationError(f"image fetch failed: {exc}") from exc

    content_type = response.headers.get("content-type", "application/octet-stream")
    with contextlib.suppress(Exception):
        response.close()
    return content, content_type.split(";", 1)[0].strip().lower()
