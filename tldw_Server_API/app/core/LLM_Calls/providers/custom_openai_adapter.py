from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List
import os

from .base import ChatProvider
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
)
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload


class CustomOpenAIAdapter(ChatProvider):
    name = "custom-openai-api"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 120,
            "max_output_tokens_default": 4096,
        }

    def _to_handler_args(self, request: Dict[str, Any]) -> Dict[str, Any]:
        streaming_raw = request.get("stream")
        if streaming_raw is None:
            streaming_raw = request.get("streaming")
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_message": request.get("system_message"),
            "streaming": streaming_raw,
            "model": request.get("model"),
            # Compatibility knobs
            "maxp": request.get("top_p"),
            "topp": request.get("top_p"),
            "minp": request.get("min_p"),
            "topk": request.get("top_k"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "user_identifier": request.get("user"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "app_config": request.get("app_config"),
        }

    def _use_native_http(self) -> bool:
        import os
        if os.getenv("PYTEST_CURRENT_TEST"):
            return True
        if (os.getenv("LLM_ADAPTERS_ENABLED") or "").lower() in {"1", "true", "yes", "on"}:
            return True
        v = os.getenv("LLM_ADAPTERS_NATIVE_HTTP_CUSTOM_OPENAI")
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    def _resolve_base(self, request: Dict[str, Any], cfg_section: str) -> str:
        cfg = request.get("app_config") or {}
        section = cfg.get(cfg_section) or {}
        base = section.get("api_ip") or os.getenv("CUSTOM_OPENAI_API_IP_1")
        if cfg_section.endswith("_2"):
            base = section.get("api_ip") or os.getenv("CUSTOM_OPENAI_API_IP_2") or base
        if not base:
            # default to local typical value
            base = "http://127.0.0.1:11434/v1"
        return str(base).rstrip("/")

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = request.get("messages") or []
        system_message = request.get("system_message")
        payload_messages: List[Dict[str, Any]] = []
        if system_message:
            payload_messages.append({"role": "system", "content": system_message})
        payload_messages.extend(messages)
        payload: Dict[str, Any] = {"messages": payload_messages, "stream": False}
        if request.get("model") is not None:
            payload["model"] = request.get("model")
        # OpenAI-compatible
        for k in (
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "max_tokens",
            "n",
            "stop",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "seed",
            "response_format",
        ):
            if request.get(k) is not None:
                payload[k] = request.get(k)
        if request.get("tools") is not None:
            payload["tools"] = request.get("tools")
        if request.get("tool_choice") is not None:
            payload["tool_choice"] = request.get("tool_choice")
        if request.get("logprobs") is not None:
            payload["logprobs"] = request.get("logprobs")
        if request.get("top_logprobs") is not None and request.get("logprobs"):
            payload["top_logprobs"] = request.get("top_logprobs")
        if request.get("user") is not None:
            payload["user"] = request.get("user")
        return payload

    def _normalize_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Assume OpenAI-compatible; passthrough
        return data

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        # If tests monkeypatched legacy callable, honor it and avoid native HTTP
        try:
            from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
            fn = getattr(_legacy_local, "chat_with_custom_openai", None)
            if callable(fn):
                mod = getattr(fn, "__module__", "") or ""
                name = getattr(fn, "__name__", "") or ""
                if (os.getenv("PYTEST_CURRENT_TEST") or "tests" in mod or name.startswith("_Fake") or name.startswith("_fake")):
                    kwargs = self._to_handler_args(request)
                    if "stream" in request or "streaming" in request:
                        streaming_raw = request.get("stream")
                        if streaming_raw is None:
                            streaming_raw = request.get("streaming")
                        kwargs["streaming"] = streaming_raw
                    else:
                        kwargs["streaming"] = None
                    return fn(**kwargs)  # type: ignore[misc]
        except Exception:
            pass

        if self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            base = self._resolve_base(request, "custom_openai_api")
            # Respect servers that already include /chat/completions
            lower = base.lower()
            if lower.endswith("/v1"):
                url = f"{base}/chat/completions"
            elif lower.endswith("/chat/completions"):
                url = base
            else:
                url = f"{base}/v1/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                with _hc_create_client(timeout=timeout or 120.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return self._normalize_response(resp.json())
            except Exception as e:
                raise self.normalize_error(e)
        # Legacy
        kwargs = self._to_handler_args(request)
        if "stream" not in request and "streaming" not in request:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        # If tests monkeypatched legacy callable, honor it and avoid native HTTP
        try:
            from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
            fn = getattr(_legacy_local, "chat_with_custom_openai", None)
            if callable(fn):
                mod = getattr(fn, "__module__", "") or ""
                name = getattr(fn, "__name__", "") or ""
                if (os.getenv("PYTEST_CURRENT_TEST") or "tests" in mod or name.startswith("_Fake") or name.startswith("_fake")):
                    kwargs = self._to_handler_args(request)
                    kwargs["streaming"] = True
                    return fn(**kwargs)  # type: ignore[misc]
        except Exception:
            pass

        if self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            base = self._resolve_base(request, "custom_openai_api")
            lower = base.lower()
            if lower.endswith("/v1"):
                url = f"{base}/chat/completions"
            elif lower.endswith("/chat/completions"):
                url = base
            else:
                url = f"{base}/v1/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = True
            try:
                with _hc_create_client(timeout=timeout or 120.0) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as resp:
                        resp.raise_for_status()
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            yield line
                return
            except Exception as e:
                raise self.normalize_error(e)
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item

    def normalize_error(self, exc: Exception):  # type: ignore[override]
        try:
            import httpx  # type: ignore
        except Exception:  # pragma: no cover
            httpx = None  # type: ignore
        if httpx is not None and isinstance(exc, getattr(httpx, "HTTPStatusError", ( ))):
            from tldw_Server_API.app.core.Chat.Chat_Deps import (
                ChatBadRequestError,
                ChatAuthenticationError,
                ChatRateLimitError,
                ChatProviderError,
                ChatAPIError,
            )
            resp = getattr(exc, "response", None)
            status = getattr(resp, "status_code", None)
            detail = None
            try:
                body = resp.json() if resp is not None else None
            except Exception:
                body = None
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    msg = (err.get("message") or "").strip()
                    typ = (err.get("type") or "").strip()
                    detail = (f"{typ} {msg}" if typ else msg) or None
            if not detail:
                try:
                    detail = resp.text if resp is not None else str(exc)
                except Exception:
                    detail = str(exc)
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


class CustomOpenAIAdapter2(CustomOpenAIAdapter):
    name = "custom-openai-api-2"

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        # If tests monkeypatched legacy callable, honor it and avoid native HTTP
        try:
            from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
            fn = getattr(_legacy_local, "chat_with_custom_openai_2", None)
            if callable(fn):
                mod = getattr(fn, "__module__", "") or ""
                name = getattr(fn, "__name__", "") or ""
                if (os.getenv("PYTEST_CURRENT_TEST") or "tests" in mod or name.startswith("_Fake") or name.startswith("_fake")):
                    kwargs = self._to_handler_args(request)
                    if "stream" in request or "streaming" in request:
                        streaming_raw = request.get("stream")
                        if streaming_raw is None:
                            streaming_raw = request.get("streaming")
                        kwargs["streaming"] = streaming_raw
                    else:
                        kwargs["streaming"] = None
                    return fn(**kwargs)  # type: ignore[misc]
        except Exception:
            pass

        if self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            base = self._resolve_base(request, "custom_openai_api_2")
            lower = base.lower()
            if lower.endswith("/v1"):
                url = f"{base}/chat/completions"
            elif lower.endswith("/chat/completions"):
                url = base
            else:
                url = f"{base}/v1/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                with _hc_create_client(timeout=timeout or 120.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return self._normalize_response(resp.json())
            except Exception as e:
                raise self.normalize_error(e)
        kwargs = self._to_handler_args(request)
        if "stream" not in request and "streaming" not in request:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai_2(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        # If tests monkeypatched legacy callable, honor it and avoid native HTTP
        try:
            from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
            fn = getattr(_legacy_local, "chat_with_custom_openai_2", None)
            if callable(fn):
                mod = getattr(fn, "__module__", "") or ""
                name = getattr(fn, "__name__", "") or ""
                if (os.getenv("PYTEST_CURRENT_TEST") or "tests" in mod or name.startswith("_Fake") or name.startswith("_fake")):
                    kwargs = self._to_handler_args(request)
                    kwargs["streaming"] = True
                    return fn(**kwargs)  # type: ignore[misc]
        except Exception:
            pass

        if self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            base = self._resolve_base(request, "custom_openai_api_2")
            lower = base.lower()
            if lower.endswith("/v1"):
                url = f"{base}/chat/completions"
            elif lower.endswith("/chat/completions"):
                url = base
            else:
                url = f"{base}/v1/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = True
            try:
                with _hc_create_client(timeout=timeout or 120.0) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as resp:
                        resp.raise_for_status()
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            yield line
                return
            except Exception as e:
                raise self.normalize_error(e)
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai_2(**kwargs)
