from __future__ import annotations

from typing import Any

from loguru import logger

from tldw_Server_API.app.core.http_client import create_client

from .base import EmbeddingsProvider


class GoogleEmbeddingsAdapter(EmbeddingsProvider):
    name = "google-embeddings"

    def capabilities(self) -> dict[str, Any]:
        return {
            "dimensions_default": None,
            "max_batch_size": 128,
            "default_timeout_seconds": 60,
        }

    def _use_native_http(self) -> bool:
        import os
        v = os.getenv("LLM_EMBEDDINGS_NATIVE_HTTP_GOOGLE")
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

    def _base_url(self) -> str:
        import os
        return os.getenv("GOOGLE_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1").rstrip("/")

    def _normalize(self, raw: dict[str, Any], *, multi: bool) -> dict[str, Any]:
        # Google embedContent returns {embedding: {values: [...]}}
        # batchEmbedContents returns {embeddings: [{values: [...]}, ...]}
        if not multi:
            vec = []
            try:
                vec = raw.get("embedding", {}).get("values", [])
            except Exception:
                vec = []
            return {"data": [{"index": 0, "embedding": vec}], "object": "list", "model": None}
        data: list[dict[str, Any]] = []
        try:
            items = raw.get("embeddings", [])
            for i, it in enumerate(items):
                data.append({"index": i, "embedding": (it.get("values") or [])})
        except Exception:
            pass
        return {"data": data, "object": "list", "model": None}

    def embed(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        inputs = request.get("input")
        model = request.get("model")
        api_key = request.get("api_key")
        if inputs is None or not model:
            raise ValueError("Embeddings: 'input' and 'model' are required")

        if self._use_native_http():
            # Use single embedContent for 1 input; loop for multiple
            base = self._base_url()
            try:
                with create_client(timeout=timeout or 60.0) as client:
                    if isinstance(inputs, list):
                        out: list[dict[str, Any]] = []
                        for idx, text in enumerate(inputs):
                            url = f"{base}/models/{model}:embedContent"
                            params = {"key": api_key} if api_key else None
                            payload = {"content": {"parts": [{"text": text}]}}
                            resp = client.post(url, params=params, json=payload)
                            if hasattr(resp, "raise_for_status"):
                                resp.raise_for_status()
                            data = resp.json()
                            out.append({"index": idx, "embedding": data.get("embedding", {}).get("values", [])})
                        return {"data": out, "object": "list", "model": model}
                    else:
                        url = f"{base}/models/{model}:embedContent"
                        params = {"key": api_key} if api_key else None
                        payload = {"content": {"parts": [{"text": inputs}]}}
                        resp = client.post(url, params=params, json=payload)
                        if hasattr(resp, "raise_for_status"):
                            resp.raise_for_status()
                        data = resp.json()
                        return self._normalize(data, multi=False)
            except Exception as e:
                from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
                raise ChatProviderError(provider=self.name, message=str(e))

        msg = (
            "GoogleEmbeddingsAdapter: native HTTP disabled "
            "(set LLM_EMBEDDINGS_NATIVE_HTTP_GOOGLE=1 to enable)"
        )
        logger.debug(msg)
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider=self.name, message=msg)
