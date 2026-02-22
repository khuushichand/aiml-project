from __future__ import annotations

from typing import Any

from loguru import logger

from tldw_Server_API.app.core.http_client import create_client
from tldw_Server_API.app.core.testing import is_truthy

from .base import EmbeddingsProvider


class HuggingFaceEmbeddingsAdapter(EmbeddingsProvider):
    name = "huggingface-embeddings"

    def capabilities(self) -> dict[str, Any]:
        return {
            "dimensions_default": None,
            "max_batch_size": 128,
            "default_timeout_seconds": 60,
        }

    def _use_native_http(self) -> bool:
        import os
        v = os.getenv("LLM_EMBEDDINGS_NATIVE_HTTP_HUGGINGFACE")
        # Off by default; opt-in in CI/tests
        return is_truthy(v)

    def _base_url(self) -> str:
        import os
        return os.getenv("HUGGINGFACE_INFERENCE_BASE_URL", "https://api-inference.huggingface.co/models").rstrip("/")

    def _headers(self, api_key: str | None) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    def _normalize(self, raw: list[Any] | dict[str, Any], *, multi: bool) -> dict[str, Any]:
        # HF returns list[list[float]] or sometimes dict containing embeddings
        if isinstance(raw, dict) and "data" in raw:
            return raw  # already normalized by caller
        if not multi:
            vec: list[float] = []
            if isinstance(raw, list):
                # Some models return [[...]] for single input
                vec = raw[0] if raw and isinstance(raw[0], list) else raw  # type: ignore[assignment]
            elif isinstance(raw, dict) and "embeddings" in raw:
                vec = raw.get("embeddings") or []
            return {"data": [{"index": 0, "embedding": vec}], "object": "list", "model": None}
        # multi
        data: list[dict[str, Any]] = []
        if isinstance(raw, list):
            # Could be [vec1, vec2, ...] or [[...],[...]]
            arr = raw
            if arr and isinstance(arr[0], list) and arr and not any(isinstance(x, dict) for x in arr):
                # already list of vectors
                for i, vec in enumerate(arr):
                    data.append({"index": i, "embedding": vec})
            else:
                for i, vec in enumerate(arr):
                    data.append({"index": i, "embedding": vec})
        elif isinstance(raw, dict) and "embeddings" in raw:
            embs = raw.get("embeddings") or []
            for i, vec in enumerate(embs):
                data.append({"index": i, "embedding": vec})
        return {"data": data, "object": "list", "model": None}

    def embed(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        inputs = request.get("input")
        model = request.get("model")
        api_key = request.get("api_key")
        if inputs is None or not model:
            raise ValueError("Embeddings: 'input' and 'model' are required")

        # Native HTTP path via centralized client (mock-friendly)
        if self._use_native_http():
            url = f"{self._base_url()}/{model}"
            headers = self._headers(api_key)
            payload: dict[str, Any]
            if isinstance(inputs, list):
                payload = {"inputs": inputs, "options": {"wait_for_model": True}}
                multi = True
            else:
                payload = {"inputs": inputs, "options": {"wait_for_model": True}}
                multi = False
            try:
                with create_client(timeout=timeout or 60.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if hasattr(resp, "raise_for_status"):
                        resp.raise_for_status()
                    data = resp.json()
                return self._normalize(data, multi=multi)
            except Exception as e:
                from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
                raise ChatProviderError(provider=self.name, message=str(e)) from e

        # Fallback: do not attempt legacy path; endpoint will fall back
        msg = (
            "HuggingFaceEmbeddingsAdapter: native HTTP disabled "
            "(set LLM_EMBEDDINGS_NATIVE_HTTP_HUGGINGFACE=1 to enable)"
        )
        logger.debug(msg)
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider=self.name, message=msg)
