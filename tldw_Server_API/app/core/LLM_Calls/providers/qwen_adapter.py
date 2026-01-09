from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List
import os

from .base import ChatProvider
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

# Expose a patchable factory for tests; production uses the centralized client
http_client_factory = _hc_create_client


class QwenAdapter(ChatProvider):
    name = "qwen"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 90,
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
            # Qwen uses 'maxp' in legacy; map from top_p
            "maxp": request.get("top_p"),
            "streaming": streaming_raw,
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "user": request.get("user"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }

    def _use_native_http(self) -> bool:
        # Under pytest:
        # - If the http client factory is monkeypatched at this module alias, prefer adapter path
        # - Otherwise, if legacy callable is monkeypatched, prefer legacy path
        if os.getenv("PYTEST_CURRENT_TEST"):
            try:
                # If our exposed factory differs from the module's default, tests patched it
                from tldw_Server_API.app.core import http_client as _hc_mod
                _default_factory = getattr(_hc_mod, "create_client", None)
                if _default_factory is not None and http_client_factory is not _default_factory:
                    return True
                # Otherwise, if legacy callable is monkeypatched, allow legacy path
                from tldw_Server_API.app.core.LLM_Calls import legacy_chat_calls as _legacy
                fn = getattr(_legacy, "chat_with_qwen", None)
                if callable(fn):
                    mod = getattr(fn, "__module__", "") or ""
                    fname = getattr(fn, "__name__", "") or ""
                    if (mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                        return False
            except Exception:
                pass
        enabled = (os.getenv("LLM_ADAPTERS_ENABLED") or "").strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            return False
        if enabled in {"1", "true", "yes", "on"}:
            return True
        v = (os.getenv("LLM_ADAPTERS_NATIVE_HTTP_QWEN") or "").strip().lower()
        if v in {"0", "false", "no", "off"}:
            return False
        if v in {"1", "true", "yes", "on"}:
            return True
        return True

    def _base_url(self, cfg: Optional[Dict[str, Any]]) -> str:
        # DashScope OpenAI-compatible endpoint
        default_base = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        api_base = None
        if cfg:
            api_base = ((cfg.get("qwen_api") or {}).get("api_base_url"))
        return (os.getenv("QWEN_BASE_URL") or api_base or default_base).rstrip("/")

    def _resolve_timeout(self, request: Dict[str, Any], fallback: Optional[float]) -> float:
        try:
            cfg = request.get("app_config") or {}
            qcfg = cfg.get("qwen_api") or {}
            t = qcfg.get("api_timeout")
            if t is not None:
                try:
                    return float(t)
                except Exception:
                    pass
        except Exception:
            pass
        if fallback is not None:
            return float(fallback)
        return float(self.capabilities().get("default_timeout_seconds", 90))

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = request.get("messages") or []
        system_message = request.get("system_message")
        payload_messages: List[Dict[str, Any]] = []
        if system_message and not any((m.get("role") == "system") for m in messages):
            payload_messages.append({"role": "system", "content": system_message})
        payload_messages.extend(messages)
        payload: Dict[str, Any] = {
            "model": request.get("model"),
            "messages": payload_messages,
        }
        # Common OpenAI-compatible fields
        for k in (
            "temperature",
            "top_p",
            "max_tokens",
            "seed",
            "stop",
            "n",
            "user",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "logprobs",
            "top_logprobs",
        ):
            if request.get(k) is not None:
                payload[k] = request.get(k)
        if request.get("tools") is not None:
            payload["tools"] = request.get("tools")
        if request.get("tool_choice") is not None:
            payload["tool_choice"] = request.get("tool_choice")
        if request.get("response_format") is not None:
            payload["response_format"] = request.get("response_format")
        return payload

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        # Native httpx path
        if self._use_native_http():
            api_key = request.get("api_key")
            cfg = request.get("app_config") or {}
            url = f"{self._base_url(cfg)}/chat/completions"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                resolved_timeout = self._resolve_timeout(request, timeout)
                with http_client_factory(timeout=resolved_timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                raise self.normalize_error(e)

        # Legacy delegate for parity
        kwargs = self._to_handler_args(request)
        if "stream" not in request and "streaming" not in request:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import legacy_chat_calls as _legacy
        fn = getattr(_legacy, "chat_with_qwen", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            fname = getattr(fn, "__name__", "") or ""
            if (os.getenv("PYTEST_CURRENT_TEST") or mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_qwen(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        if self._use_native_http():
            api_key = request.get("api_key")
            cfg = request.get("app_config") or {}
            url = f"{self._base_url(cfg)}/chat/completions"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            payload["stream"] = True
            try:
                resolved_timeout = self._resolve_timeout(request, timeout)
                with http_client_factory(timeout=resolved_timeout) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as resp:
                        resp.raise_for_status()
                        seen_done = False
                        for raw in resp.iter_lines():
                            if not raw:
                                continue
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

        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import legacy_chat_calls as _legacy
        fn = getattr(_legacy, "chat_with_qwen", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            fname = getattr(fn, "__name__", "") or ""
            if (os.getenv("PYTEST_CURRENT_TEST") or mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_qwen(**kwargs)

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

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
