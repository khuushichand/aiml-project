"""Alibaba Model Studio image-generation backend adapter."""

from __future__ import annotations

import os
from typing import Any

from tldw_Server_API.app.core.http_client import fetch_json
from tldw_Server_API.app.core.Image_Generation.adapters.base import ImageGenRequest, ImageGenResult
from tldw_Server_API.app.core.Image_Generation.adapters.image_format_utils import (
    decode_base64_image,
    decode_data_url,
    fetch_image_bytes,
    format_from_bytes,
    format_from_content_type,
    maybe_convert_format,
    maybe_decode_base64_image,
)
from tldw_Server_API.app.core.Image_Generation.config import (
    DEFAULT_MODELSTUDIO_IMAGE_BASE_URL,
    DEFAULT_MODELSTUDIO_IMAGE_MODEL,
    DEFAULT_MODELSTUDIO_IMAGE_TIMEOUT_SECONDS,
    get_image_generation_config,
)
from tldw_Server_API.app.core.Image_Generation.exceptions import ImageBackendUnavailableError, ImageGenerationError


class ModelStudioImageAdapter:
    name = "modelstudio"
    supported_formats = {"png", "jpg", "webp"}

    def __init__(self) -> None:
        self._config = get_image_generation_config()

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        output_format = request.format.lower()
        if output_format not in self.supported_formats:
            raise ImageGenerationError(f"unsupported output format: {output_format}")

        mode = self._resolve_mode(request)
        if mode == "async":
            raise ImageGenerationError("Model Studio async mode not yet implemented")
        content, content_type = self._generate_sync(request)
        actual_format = format_from_content_type(content_type) or format_from_bytes(content)
        content, content_type = maybe_convert_format(content, content_type, actual_format, output_format)
        return ImageGenResult(content=content, content_type=content_type, bytes_len=len(content))

    def _generate_sync(self, request: ImageGenRequest) -> tuple[bytes, str]:
        api_key = self._resolve_api_key()
        base_url = self._resolve_base_url()
        url = self._sync_generation_url(base_url)
        payload = self._build_sync_payload(request)

        try:
            data = fetch_json(
                method="POST",
                url=url,
                headers=self._headers(api_key),
                json=payload,
                timeout=self._config.modelstudio_image_timeout_seconds or DEFAULT_MODELSTUDIO_IMAGE_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise ImageGenerationError(f"Model Studio sync request failed: {exc}") from exc
        return self._extract_image_content(data)

    def _resolve_mode(self, request: ImageGenRequest) -> str:
        extra_mode = (request.extra_params or {}).get("mode") if isinstance(request.extra_params, dict) else None
        raw = str(extra_mode or self._config.modelstudio_image_mode or "auto").strip().lower()
        if raw not in {"sync", "async", "auto"}:
            return "auto"
        return raw

    def _resolve_api_key(self) -> str:
        api_key = (self._config.modelstudio_image_api_key or "").strip()
        if not api_key:
            api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
        if not api_key:
            api_key = (os.getenv("QWEN_API_KEY") or "").strip()
        if not api_key:
            raise ImageBackendUnavailableError("modelstudio image api key is not configured")
        return api_key

    def _resolve_base_url(self) -> str:
        raw = (
            os.getenv("MODELSTUDIO_IMAGE_BASE_URL")
            or os.getenv("DASHSCOPE_BASE_URL")
            or self._config.modelstudio_image_base_url
            or DEFAULT_MODELSTUDIO_IMAGE_BASE_URL
        )
        cleaned = str(raw).strip()
        if not cleaned:
            raise ImageBackendUnavailableError("modelstudio image base URL is not configured")
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            cleaned = f"https://{cleaned}"
        return cleaned.rstrip("/")

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _sync_generation_url(base_url: str) -> str:
        suffix = "/services/aigc/multimodal-generation/generation"
        if base_url.endswith(suffix):
            return base_url
        return f"{base_url}{suffix}"

    def _build_sync_payload(self, request: ImageGenRequest) -> dict[str, Any]:
        prompt = request.prompt.strip()
        if request.negative_prompt:
            prompt = f"{prompt}\n\nNegative prompt: {request.negative_prompt.strip()}"

        payload: dict[str, Any] = {
            "model": (
                request.model
                or os.getenv("MODELSTUDIO_IMAGE_MODEL")
                or self._config.modelstudio_image_default_model
                or DEFAULT_MODELSTUDIO_IMAGE_MODEL
            ),
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            },
        }
        parameters: dict[str, Any] = {}
        if request.width and request.height:
            parameters["size"] = f"{request.width}*{request.height}"
        if request.seed is not None:
            parameters["seed"] = request.seed
        if request.steps is not None:
            parameters["steps"] = request.steps
        if request.cfg_scale is not None:
            parameters["guidance_scale"] = request.cfg_scale
        if request.sampler:
            parameters["sampler"] = request.sampler
        if parameters:
            payload["parameters"] = parameters

        extra_params = request.extra_params or {}
        if isinstance(extra_params, dict):
            for key, value in extra_params.items():
                if key in {"prompt", "negative_prompt", "mode"}:
                    continue
                payload[key] = value
        return payload

    def _extract_image_content(self, data: Any) -> tuple[bytes, str]:
        candidate = self._extract_from_node(data)
        if candidate:
            return candidate
        raise ImageGenerationError("Model Studio did not return image content")

    def _extract_from_node(self, node: Any) -> tuple[bytes, str] | None:
        if isinstance(node, dict):
            for key in ("b64_json", "image_base64", "base64", "image_b64"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    return decode_base64_image(value.strip()), "image/png"

            for key in ("image_url", "url", "image"):
                if key in node:
                    extracted = self._extract_from_link_value(node.get(key))
                    if extracted:
                        return extracted

            for key in ("images", "data", "choices", "message", "content", "output", "result", "results"):
                if key not in node:
                    continue
                extracted = self._extract_from_node(node.get(key))
                if extracted:
                    return extracted
            return None

        if isinstance(node, list):
            for item in node:
                extracted = self._extract_from_node(item)
                if extracted:
                    return extracted
            return None

        return self._extract_from_link_value(node)

    def _extract_from_link_value(self, value: Any) -> tuple[bytes, str] | None:
        if isinstance(value, dict):
            for key in ("url", "image_url", "b64_json", "base64", "image"):
                if key in value:
                    extracted = self._extract_from_link_value(value.get(key))
                    if extracted:
                        return extracted
            return None

        if not isinstance(value, str):
            return None
        raw = value.strip()
        if not raw:
            return None
        if raw.startswith("data:"):
            return decode_data_url(raw)
        if raw.startswith("http://") or raw.startswith("https://"):
            return fetch_image_bytes(
                raw,
                timeout=self._config.modelstudio_image_timeout_seconds or DEFAULT_MODELSTUDIO_IMAGE_TIMEOUT_SECONDS,
            )
        decoded = maybe_decode_base64_image(raw)
        if decoded is not None:
            return decoded, "image/png"
        return None
