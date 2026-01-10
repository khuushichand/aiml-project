from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List

from .base import ChatProvider

import os
from loguru import logger
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
)
from tldw_Server_API.app.core.LLM_Calls.sse import (
    normalize_provider_line,
    is_done_line,
    sse_done,
    finalize_stream,
)
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload

# Expose a patchable factory for tests; production uses centralized client
http_client_factory = _hc_create_client


def _stream_debug_enabled(provider: str) -> bool:
    value = (os.getenv("LLM_ADAPTERS_STREAM_DEBUG") or "").strip().lower()
    if not value:
        return False
    if value in {"1", "true", "yes", "on", "all"}:
        return True
    providers = {p.strip() for p in value.split(",") if p.strip()}
    return provider.lower() in providers


class MistralAdapter(ChatProvider):
    name = "mistral"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 60,
            "max_output_tokens_default": 8192,
        }

    def _to_handler_args(self, request: Dict[str, Any]) -> Dict[str, Any]:
        streaming_raw = request.get("stream")
        if streaming_raw is None:
            streaming_raw = request.get("streaming")
        return {
            "input_data": request.get("messages") or [],
            "model": request.get("model"),
            "api_key": request.get("api_key"),
            "system_message": request.get("system_message"),
            "temp": request.get("temperature"),
            "streaming": streaming_raw,
            "topp": request.get("top_p"),
            "max_tokens": request.get("max_tokens"),
            "random_seed": request.get("seed"),
            "top_k": request.get("top_k"),
            "safe_prompt": request.get("safe_prompt"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "response_format": request.get("response_format"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }

    def _apply_config_defaults(self, request: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(request)
        cfg = (merged.get("app_config") or {}).get("mistral_api", {})
        if merged.get("api_key") is None and cfg.get("api_key") is not None:
            merged["api_key"] = cfg.get("api_key")
        if merged.get("model") is None:
            merged["model"] = cfg.get("model") or "mistral-large-latest"
        if merged.get("temperature") is None and cfg.get("temperature") is not None:
            merged["temperature"] = cfg.get("temperature")
        if merged.get("top_p") is None and cfg.get("top_p") is not None:
            merged["top_p"] = cfg.get("top_p")
        if merged.get("max_tokens") is None and cfg.get("max_tokens") is not None:
            merged["max_tokens"] = cfg.get("max_tokens")
        if merged.get("seed") is None and cfg.get("random_seed") is not None:
            merged["seed"] = cfg.get("random_seed")
        if merged.get("top_k") is None and cfg.get("top_k") is not None:
            merged["top_k"] = cfg.get("top_k")
        if merged.get("safe_prompt") is None and cfg.get("safe_prompt") is not None:
            merged["safe_prompt"] = cfg.get("safe_prompt")
        if merged.get("tools") is None and cfg.get("tools") is not None:
            merged["tools"] = cfg.get("tools")
        if merged.get("tool_choice") is None and cfg.get("tool_choice") is not None:
            merged["tool_choice"] = cfg.get("tool_choice")
        if merged.get("response_format") is None and cfg.get("response_format") is not None:
            merged["response_format"] = cfg.get("response_format")
        return merged

    def _base_url(self) -> str:
        return os.getenv("MISTRAL_API_BASE", "https://api.mistral.ai/v1").rstrip("/")

    def _resolve_base_url(self, request: Dict[str, Any]) -> str:
        try:
            cfg = (request or {}).get("app_config") or {}
            mcfg = cfg.get("mistral_api") or {}
            base = mcfg.get("api_base_url")
            if isinstance(base, str) and base.strip():
                return base.strip().rstrip("/")
        except Exception:
            pass
        return self._base_url()

    def _resolve_timeout(self, request: Dict[str, Any], fallback: Optional[float]) -> float:
        try:
            cfg = (request or {}).get("app_config") or {}
            mcfg = cfg.get("mistral_api") or {}
            t = mcfg.get("api_timeout")
            if t is not None:
                try:
                    return float(t)
                except Exception:
                    pass
        except Exception:
            pass
        if fallback is not None:
            return float(fallback)
        return float(self.capabilities().get("default_timeout_seconds", 60))

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = request.get("messages") or []
        system_message = request.get("system_message")
        payload_messages: List[Dict[str, Any]] = []
        if system_message:
            payload_messages.append({"role": "system", "content": system_message})
        payload_messages.extend(messages)
        payload: Dict[str, Any] = {
            "model": request.get("model"),
            "messages": payload_messages,
        }
        if request.get("temperature") is not None:
            payload["temperature"] = request.get("temperature")
        if request.get("top_p") is not None:
            payload["top_p"] = request.get("top_p")
        if request.get("max_tokens") is not None:
            payload["max_tokens"] = request.get("max_tokens")
        if request.get("stop") is not None:
            payload["stop"] = request.get("stop")
        if request.get("tools") is not None:
            payload["tools"] = request.get("tools")
        if request.get("tool_choice") is not None:
            payload["tool_choice"] = request.get("tool_choice")
        if request.get("response_format") is not None:
            payload["response_format"] = request.get("response_format")
        if request.get("seed") is not None:
            payload["seed"] = request.get("seed")
        if request.get("top_k") is not None:
            payload["top_k"] = request.get("top_k")
        if request.get("safe_prompt") is not None:
            payload["safe_prompt"] = request.get("safe_prompt")
        return payload

    @staticmethod
    def _normalize_to_openai_shape(data: Dict[str, Any]) -> Dict[str, Any]:
        # Mistral speaks OpenAI-compatible shapes for chat/completions; passthrough
        return data

    def normalize_error(self, exc: Exception):  # type: ignore[override]
        from tldw_Server_API.app.core.LLM_Calls.error_utils import (
            get_http_status_from_exception,
            get_http_error_text,
            is_http_status_error,
        )
        if is_http_status_error(exc):
            from tldw_Server_API.app.core.Chat.Chat_Deps import (
                ChatBadRequestError,
                ChatAuthenticationError,
                ChatRateLimitError,
                ChatProviderError,
                ChatAPIError,
            )
            resp = getattr(exc, "response", None)
            status = get_http_status_from_exception(exc)
            body = None
            try:
                body = resp.json()
            except Exception:
                body = None
            detail = None
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                eobj = body["error"]
                msg = (eobj.get("message") or "").strip()
                typ = (eobj.get("type") or "").strip()
                detail = (f"{typ} {msg}" if typ else msg) or str(exc)
            else:
                detail = get_http_error_text(exc)
            if status in (400, 404, 422):
                return ChatBadRequestError(provider=self.name, message=str(detail))
            if status in (401, 403):
                return ChatAuthenticationError(provider=self.name, message=str(detail))
            if status == 429:
                return ChatRateLimitError(provider=self.name, message=str(detail))
            if status and 500 <= status < 600:
                return ChatProviderError(provider=self.name, message=str(detail), status_code=status)
            return ChatAPIError(provider=self.name, message=str(detail), status_code=status or 500)
        return super().normalize_error(exc)

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        request = self._apply_config_defaults(request)
        api_key = request.get("api_key")
        if not api_key:
            from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
            raise ChatConfigurationError(provider=self.name, message="Mistral API Key required.")
        url = f"{self._resolve_base_url(request)}/chat/completions"
        headers = self._headers(api_key)
        payload = self._build_payload(request)
        payload["stream"] = False
        try:
            resolved_timeout = self._resolve_timeout(request, timeout)
            with http_client_factory(timeout=resolved_timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return self._normalize_to_openai_shape(data)
        except Exception as e:
            raise self.normalize_error(e)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        request = self._apply_config_defaults(request)
        api_key = request.get("api_key")
        if not api_key:
            from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
            raise ChatConfigurationError(provider=self.name, message="Mistral API Key required.")
        url = f"{self._resolve_base_url(request)}/chat/completions"
        headers = self._headers(api_key)
        payload = self._build_payload(request)
        payload["stream"] = True
        try:
            resolved_timeout = self._resolve_timeout(request, timeout)
            with http_client_factory(timeout=resolved_timeout) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    debug_stream = _stream_debug_enabled(self.name)
                    seen_done = False
                    for raw in resp.iter_lines():
                        if not raw:
                            continue
                        if debug_stream:
                            logger.debug(f"{self.name} stream raw: {raw!r}")
                        try:
                            line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                        except Exception:
                            line = str(raw)
                        if is_done_line(line):
                            if not seen_done:
                                seen_done = True
                                yield sse_done()
                            continue
                        normalized = normalize_provider_line(line)
                        if normalized is not None:
                            yield normalized
                    for tail in finalize_stream(response=resp, done_already=seen_done):
                        yield tail
            return
        except Exception as e:
            raise self.normalize_error(e)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
