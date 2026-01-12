from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import EmbeddingsProvider
from tldw_Server_API.app.core.LLM_Calls.adapter_utils import ensure_app_config


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

    def _base_url(self, openai_cfg: Optional[Dict[str, Any]] = None) -> str:
        from tldw_Server_API.app.core.LLM_Calls.chat_calls import _resolve_openai_api_base
        return _resolve_openai_api_base(openai_cfg or {})

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
        dimensions = request.get("dimensions")
        if inputs is None:
            raise ValueError("Embeddings: 'input' is required")

        raw_config = request.get("app_config")
        app_config = raw_config if isinstance(raw_config, dict) else None
        app_config = ensure_app_config(app_config)
        openai_cfg = dict((app_config.get("openai_api") or {}) if app_config else {})
        api_key = request.get("api_key") or openai_cfg.get("api_key")
        if not api_key and app_config:
            try:
                emb_cfg = app_config.get("embedding_config") or {}
                models = emb_cfg.get("models") or {}
                model_spec = models.get(model)
                if model_spec is not None:
                    api_key = getattr(model_spec, "api_key", None) or (
                        model_spec.get("api_key") if isinstance(model_spec, dict) else None
                    )
            except Exception:
                api_key = None
        if api_key:
            openai_cfg["api_key"] = api_key
            app_config = dict(app_config or {})
            app_config["openai_api"] = openai_cfg

        # Native HTTP path (opt-in)
        if self._use_native_http():
            from tldw_Server_API.app.core.http_client import fetch as _fetch
            url = f"{self._base_url(openai_cfg).rstrip('/')}/embeddings"
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
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as legacy
        if isinstance(inputs, list):
            embeddings = legacy.get_openai_embeddings_batch(
                inputs,
                model,
                app_config=app_config,
                dimensions=dimensions,
            )
            return self._normalize_response(embeddings, multi=True)
        vec = legacy.get_openai_embeddings(
            inputs,
            model,
            app_config=app_config,
            dimensions=dimensions,
        )
        return self._normalize_response(vec, multi=False)
