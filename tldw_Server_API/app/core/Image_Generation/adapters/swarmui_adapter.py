"""SwarmUI backend adapter."""

from __future__ import annotations

import base64
import io
from typing import Any, Dict, Optional
from urllib.parse import urlparse, quote

from loguru import logger

from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenRequest, ImageGenResult
from tldw_Server_API.app.core.Image_Generation.config import (
    DEFAULT_SWARMUI_TIMEOUT_SECONDS,
    get_image_generation_config,
)
from tldw_Server_API.app.core.Image_Generation.exceptions import ImageBackendUnavailableError, ImageGenerationError
from tldw_Server_API.app.core.http_client import fetch, fetch_json

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency guard
    Image = None  # type: ignore


class SwarmUIAdapter:
    name = "swarmui"
    supported_formats = {"png", "jpg"}

    def __init__(self) -> None:
        self._config = get_image_generation_config()
        self._session_id: Optional[str] = None

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        output_format = request.format.lower()
        if output_format not in self.supported_formats:
            raise ImageGenerationError(f"unsupported output format: {output_format}")

        base_url = self._resolve_base_url()
        session_id = self._ensure_session(base_url)

        payload = self._build_payload(request, session_id)
        generate_url = f"{base_url}/API/GenerateText2Image"
        data = self._post_generate(generate_url, payload)

        image_ref = self._extract_first_image_ref(data)
        if not image_ref:
            raise ImageGenerationError("SwarmUI did not return any images")

        if image_ref.startswith("data:"):
            content, content_type = _decode_data_url(image_ref)
            fmt = _format_from_content_type(content_type)
            content, content_type = _maybe_convert_format(content, content_type, fmt, output_format)
            return ImageGenResult(content=content, content_type=content_type, bytes_len=len(content))

        image_url = self._resolve_image_url(base_url, image_ref)
        content, content_type = self._fetch_image_bytes(image_url)
        fmt = _format_from_content_type(content_type) or _format_from_url(image_ref)
        content, content_type = _maybe_convert_format(content, content_type, fmt, output_format)
        return ImageGenResult(content=content, content_type=content_type, bytes_len=len(content))

    def _resolve_base_url(self) -> str:
        raw = (self._config.swarmui_base_url or "").strip()
        if not raw:
            raise ImageBackendUnavailableError("swarmui_base_url is not configured")
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = f"http://{raw}"
        return raw.rstrip("/")

    def _cookies(self) -> Optional[Dict[str, str]]:
        token = (self._config.swarmui_swarm_token or "").strip()
        if not token:
            return None
        return {"swarm_token": token}

    def _ensure_session(self, base_url: str) -> str:
        if self._session_id:
            return self._session_id
        self._session_id = self._request_session_id(base_url)
        return self._session_id

    def _request_session_id(self, base_url: str) -> str:
        url = f"{base_url}/API/GetNewSession"
        data = self._post_json(url, {})
        session_id = None
        if isinstance(data, dict):
            session_id = data.get("session_id")
        if not session_id:
            raise ImageGenerationError("SwarmUI did not return a session_id")
        return str(session_id)

    def _build_payload(self, request: ImageGenRequest, session_id: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "session_id": session_id,
            "images": 1,
            "prompt": request.prompt,
        }
        if request.negative_prompt:
            payload["negativeprompt"] = request.negative_prompt
        if request.width is not None:
            payload["width"] = request.width
        if request.height is not None:
            payload["height"] = request.height
        if request.steps is not None:
            payload["steps"] = request.steps
        if request.cfg_scale is not None:
            payload["cfgscale"] = request.cfg_scale
        if request.seed is not None:
            payload["seed"] = request.seed
        if request.sampler:
            payload["sampler"] = request.sampler

        model = request.model or (self._config.swarmui_default_model or None)
        if model:
            payload["model"] = model

        extra_params = request.extra_params or {}
        if isinstance(extra_params, dict):
            for key, value in extra_params.items():
                if key in {"session_id", "images"}:
                    continue
                payload[key] = value
        return payload

    def _post_generate(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._post_json(url, payload)
        error_id = data.get("error_id") if isinstance(data, dict) else None
        if error_id == "invalid_session_id":
            logger.info("SwarmUI session invalid; refreshing session_id")
            self._session_id = self._request_session_id(self._resolve_base_url())
            retry_payload = dict(payload)
            retry_payload["session_id"] = self._session_id
            data = self._post_json(url, retry_payload)
            error_id = data.get("error_id") if isinstance(data, dict) else None

        if isinstance(data, dict):
            if error_id:
                raise ImageGenerationError(f"SwarmUI error_id: {error_id}")
            if data.get("error"):
                raise ImageGenerationError(str(data.get("error")))
        return data if isinstance(data, dict) else {}

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = fetch_json(
                method="POST",
                url=url,
                json=payload,
                cookies=self._cookies(),
                timeout=self._config.swarmui_timeout_seconds or DEFAULT_SWARMUI_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise ImageGenerationError(f"SwarmUI request failed: {exc}") from exc
        if not isinstance(data, dict):
            raise ImageGenerationError("SwarmUI response was not JSON")
        return data

    @staticmethod
    def _extract_first_image_ref(data: Dict[str, Any]) -> Optional[str]:
        if not isinstance(data, dict):
            return None
        images = data.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict):
                image_ref = first.get("image")
                return str(image_ref) if image_ref else None
            if isinstance(first, str):
                return first
        return None

    @staticmethod
    def _resolve_image_url(base_url: str, image_ref: str) -> str:
        if image_ref.startswith("http://") or image_ref.startswith("https://"):
            return image_ref
        parsed = urlparse(image_ref)
        if parsed.scheme in {"http", "https"}:
            return image_ref
        path = image_ref.lstrip("/")
        encoded_path = "/".join(quote(part) for part in path.split("/"))
        return f"{base_url.rstrip('/')}/{encoded_path}"

    def _fetch_image_bytes(self, url: str) -> tuple[bytes, str]:
        try:
            response = fetch(
                method="GET",
                url=url,
                cookies=self._cookies(),
                timeout=self._config.swarmui_timeout_seconds or DEFAULT_SWARMUI_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise ImageGenerationError(f"SwarmUI image fetch failed: {exc}") from exc
        try:
            status = getattr(response, "status_code", None) or response.status_code
        except Exception:
            status = None
        if status and int(status) >= 400:
            try:
                response.close()
            except Exception:
                pass
            raise ImageGenerationError(f"SwarmUI image fetch failed with status {status}")
        try:
            content = response.content
        except Exception as exc:
            try:
                response.close()
            except Exception:
                pass
            raise ImageGenerationError(f"SwarmUI image fetch failed: {exc}") from exc
        content_type = response.headers.get("content-type", "application/octet-stream")
        try:
            response.close()
        except Exception:
            pass
        return content, content_type.split(";")[0].strip().lower()


def _decode_data_url(data_url: str) -> tuple[bytes, str]:
    header, _, encoded = data_url.partition(",")
    if not header.startswith("data:"):
        raise ImageGenerationError("invalid data URL")
    meta = header[5:]
    content_type = "application/octet-stream"
    if ";" in meta:
        content_type = meta.split(";", 1)[0] or content_type
    else:
        content_type = meta or content_type
    if ";base64" not in header:
        raise ImageGenerationError("unsupported data URL encoding")
    try:
        content = base64.b64decode(encoded)
    except Exception as exc:
        raise ImageGenerationError("invalid base64 data") from exc
    return content, content_type


def _format_from_content_type(content_type: str) -> Optional[str]:
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


def _format_from_url(url: str) -> Optional[str]:
    lowered = url.lower()
    if lowered.endswith(".png"):
        return "png"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return "jpg"
    if lowered.endswith(".webp"):
        return "webp"
    return None


def _maybe_convert_format(
    content: bytes,
    content_type: str,
    actual_format: Optional[str],
    requested_format: str,
) -> tuple[bytes, str]:
    if requested_format == actual_format:
        return content, content_type
    if requested_format not in {"png", "jpg"}:
        raise ImageGenerationError(f"unsupported output format: {requested_format}")
    # If we don't know the actual format and PNG was requested, keep as-is.
    if actual_format is None and requested_format == "png":
        return content, content_type
    converted = _convert_image_bytes(content, requested_format)
    return converted, _content_type_for_format(requested_format)


def _convert_image_bytes(content: bytes, target_format: str) -> bytes:
    if Image is None:
        raise ImageGenerationError("Pillow is required for image format conversion")
    try:
        with Image.open(io.BytesIO(content)) as img:
            if target_format == "jpg" and img.mode not in {"RGB"}:
                img = img.convert("RGB")
            buf = io.BytesIO()
            save_format = "JPEG" if target_format == "jpg" else "PNG"
            img.save(buf, format=save_format)
            return buf.getvalue()
    except Exception as exc:
        raise ImageGenerationError(f"failed to convert image: {exc}") from exc


def _content_type_for_format(fmt: str) -> str:
    if fmt == "png":
        return "image/png"
    if fmt == "jpg":
        return "image/jpeg"
    if fmt == "webp":
        return "image/webp"
    return "application/octet-stream"
