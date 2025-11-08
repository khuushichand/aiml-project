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

# Patchable client factory for tests
http_client_factory = _hc_create_client


class HuggingFaceAdapter(ChatProvider):
    name = "huggingface"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 120,
            "max_output_tokens_default": 2048,
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
            "top_p": request.get("top_p"),
            "top_k": request.get("top_k"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "num_return_sequences": request.get("n"),
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
        if os.getenv("PYTEST_CURRENT_TEST"):
            try:
                from tldw_Server_API.app.core.http_client import create_client as _default_factory
                if http_client_factory is not _default_factory:
                    return True
                from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
                fn = getattr(_legacy, "chat_with_huggingface", None)
                if callable(fn):
                    mod = getattr(fn, "__module__", "") or ""
                    fname = getattr(fn, "__name__", "") or ""
                    if (mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                        return False
            except Exception:
                pass
        if (os.getenv("LLM_ADAPTERS_ENABLED") or "").lower() in {"1", "true", "yes", "on"}:
            return True
        v = os.getenv("LLM_ADAPTERS_NATIVE_HTTP_HUGGINGFACE")
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

    def _resolve_url_and_headers(self, request: Dict[str, Any]) -> Dict[str, Any]:
        cfg = (request.get("app_config") or {}).get("huggingface_api", {})
        api_base = cfg.get("api_base_url")  # may be None
        use_router = str(cfg.get("use_router_url_format", "false")).lower() == "true"
        chat_path = (cfg.get("api_chat_path") or ("chat/completions" if (api_base and "api-inference.huggingface.co/v1" in api_base) else "v1/chat/completions"))
        model = request.get("model") or cfg.get("model_id") or cfg.get("model")
        if not model:
            model = "unspecified"
        if use_router:
            base = (cfg.get("router_base_url") or "https://router.huggingface.co/hf-inference").rstrip("/")
            url = f"{base}/models/{model.strip('/')}/{chat_path.lstrip('/')}"
        else:
            base = (api_base or "https://api-inference.huggingface.co/v1").rstrip("/")
            url = f"{base}/{chat_path.lstrip('/')}"
        headers = {"Content-Type": "application/json"}
        api_key = request.get("api_key") or cfg.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return {"url": url, "headers": headers}

    def _resolve_timeout(self, request: Dict[str, Any], fallback: Optional[float]) -> float:
        try:
            cfg = (request.get("app_config") or {}).get("huggingface_api", {})
            t = cfg.get("api_timeout")
            if t is not None:
                try:
                    return float(t)
                except Exception:
                    pass
        except Exception:
            pass
        if fallback is not None:
            return float(fallback)
        return float(self.capabilities().get("default_timeout_seconds", 120))

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = request.get("messages") or []
        system_message = request.get("system_message")
        payload_messages: List[Dict[str, Any]] = []
        if system_message:
            payload_messages.append({"role": "system", "content": system_message})
        payload_messages.extend(messages)
        payload: Dict[str, Any] = {"messages": payload_messages}
        if request.get("model") is not None:
            payload["model"] = request.get("model")
        # Common OpenAI-like knobs (HF may ignore unsupported ones)
        for k in (
            "temperature",
            "top_p",
            "top_k",
            "max_tokens",
            "seed",
            "stop",
            "n",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
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

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        kwargs = self._to_handler_args(request)
        if "stream" in request or "streaming" in request:
            pass
        else:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        fn = getattr(_legacy, "chat_with_huggingface", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            fname = getattr(fn, "__name__", "") or ""
            if (
                mod.startswith("tldw_Server_API.tests")
                or mod.startswith("tests")
                or ".tests." in mod
                or fname.startswith("_fake")
            ):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_huggingface(**kwargs)

    def normalize_error(self, exc: Exception):  # type: ignore[override]
        try:
            import httpx  # type: ignore
        except Exception:  # pragma: no cover
            httpx = None  # type: ignore
        if httpx is not None and isinstance(exc, getattr(httpx, "HTTPStatusError", ())):
            from tldw_Server_API.app.core.Chat.Chat_Deps import (
                ChatBadRequestError,
                ChatAuthenticationError,
                ChatRateLimitError,
                ChatProviderError,
                ChatAPIError,
            )
            resp = getattr(exc, "response", None)
            status = getattr(resp, "status_code", None)
            # Try parsing HF error wrapper {"error": {"message": "...", "type": "..."}}
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

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        if self._use_native_http():
            info = self._resolve_url_and_headers(request)
            url = info["url"]
            headers = info["headers"]
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
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        fn = getattr(_legacy, "chat_with_huggingface", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            fname = getattr(fn, "__name__", "") or ""
            if (os.getenv("PYTEST_CURRENT_TEST") or mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_huggingface(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        if self._use_native_http():
            info = self._resolve_url_and_headers(request)
            url = info["url"]
            headers = info["headers"]
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                resolved_timeout = self._resolve_timeout(request, timeout)
                with _hc_create_client(timeout=resolved_timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                raise self.normalize_error(e)

        # Legacy delegate
        kwargs = self._to_handler_args(request)
        if "stream" not in request and "streaming" not in request:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        fn = getattr(_legacy, "chat_with_huggingface", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            fname = getattr(fn, "__name__", "") or ""
            if (os.getenv("PYTEST_CURRENT_TEST") or mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_huggingface(**kwargs)
