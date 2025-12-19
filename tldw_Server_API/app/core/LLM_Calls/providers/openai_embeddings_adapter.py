from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from .base import EmbeddingsProvider


class OpenAIEmbeddingsAdapter(EmbeddingsProvider):
    name = "openai-embeddings"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "dimensions_default": None,
            "max_batch_size": 2048,
            "default_timeout_seconds": 60,
        }

    def _use_native_http(self) -> bool:
        import os
        v = os.getenv("LLM_EMBEDDINGS_NATIVE_HTTP_OPENAI")
        # Default to False to preserve current behavior; can be flipped in CI later
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

    def _base_url(self) -> str:
        import os
        return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    def _normalize_response(self, raw: Dict[str, Any], *, multi: bool) -> Dict[str, Any]:
        # Pass-through OpenAI shape if present; otherwise synthesize a basic structure
        if isinstance(raw, dict) and "data" in raw:
            return raw
        if not multi:
            vec = raw if isinstance(raw, list) else []
            return {"data": [{"index": 0, "embedding": vec}], "model": None, "object": "list"}
        # multi
        if isinstance(raw, list):
            data = [{"index": i, "embedding": e} for i, e in enumerate(raw)]
            return {"data": data, "model": None, "object": "list"}
        return {"data": [], "model": None, "object": "list"}

    def embed(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        inputs = request.get("input")
        model = request.get("model")
        api_key = request.get("api_key")
        dimensions = request.get("dimensions")
        if inputs is None:
            raise ValueError("Embeddings: 'input' is required")

        # Native HTTP path (opt-in)
        if self._use_native_http():
            from tldw_Server_API.app.core.http_client import fetch as _fetch
            url = f"{self._base_url().rstrip('/')}/embeddings"
            payload = {"input": inputs, "model": model}
            if dimensions is not None:
                try:
                    dim = int(dimensions)
                except Exception:
                    dim = None
                if dim and dim > 0:
                    payload["dimensions"] = dim
            headers = self._headers(api_key)
            try:
                resp = _fetch(method="POST", url=url, headers=headers, json=payload, timeout=timeout or 60.0)
                if resp.status_code >= 400:
                    resp.raise_for_status()
                return resp.json()
            except Exception as e:
                from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
                raise ChatProviderError(provider=self.name, message=str(e))

        # Delegate-first fallback using legacy helper(s)
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as legacy
        if isinstance(inputs, list):
            embeddings: List[List[float]] = []
            for text in inputs:
                embeddings.append(legacy.get_openai_embeddings(text, model, dimensions=dimensions))
            return self._normalize_response(embeddings, multi=True)
        else:
            vec = legacy.get_openai_embeddings(inputs, model, dimensions=dimensions)
            return self._normalize_response(vec, multi=False)
