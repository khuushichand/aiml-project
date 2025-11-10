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
from loguru import logger

# Expose a patchable factory for tests; production uses the centralized client
http_client_factory = _hc_create_client


class DeepSeekAdapter(ChatProvider):
    name = "deepseek"

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
            # DeepSeek expects 'topp' param name in legacy path
            "topp": request.get("top_p"),
            "streaming": streaming_raw,
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "user": request.get("user"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "logit_bias": request.get("logit_bias"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }

    def _use_native_http(self) -> bool:
        # In tests, prefer adapter if the http client factory is monkeypatched
        if os.getenv("PYTEST_CURRENT_TEST"):
            try:
                from tldw_Server_API.app.core.http_client import create_client as _default_factory
                if http_client_factory is not _default_factory:
                    return True
                from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
                fn = getattr(_legacy, "chat_with_deepseek", None)
                if callable(fn):
                    mod = getattr(fn, "__module__", "") or ""
                    fname = getattr(fn, "__name__", "") or ""
                    if (mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                        return False
            except Exception:
                pass
        if (os.getenv("LLM_ADAPTERS_ENABLED") or "").lower() in {"1", "true", "yes", "on"}:
            return True
        v = os.getenv("LLM_ADAPTERS_NATIVE_HTTP_DEEPSEEK")
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

    def _base_url(self, cfg: Optional[Dict[str, Any]]) -> str:
        default_base = "https://api.deepseek.com"
        api_base = None
        if cfg:
            api_base = ((cfg.get("deepseek_api") or {}).get("api_base_url"))
        return (os.getenv("DEEPSEEK_BASE_URL") or api_base or default_base).rstrip("/")

    def _resolve_timeout(self, request: Dict[str, Any], fallback: Optional[float]) -> float:
        try:
            cfg = request.get("app_config") or {}
            dcfg = cfg.get("deepseek_api") or {}
            t = dcfg.get("api_timeout")
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
        payload: Dict[str, Any] = {"model": request.get("model"), "messages": payload_messages}
        # OpenAI-style knobs
        for k in (
            "temperature",
            "top_p",
            "max_tokens",
            "seed",
            "stop",
            "logprobs",
            "top_logprobs",
            "presence_penalty",
            "frequency_penalty",
            "response_format",
            "n",
            "user",
        ):
            if request.get(k) is not None:
                payload[k] = request.get(k)
        if request.get("tools") is not None:
            payload["tools"] = request.get("tools")
        if request.get("tool_choice") is not None:
            payload["tool_choice"] = request.get("tool_choice")
        if request.get("logit_bias") is not None:
            payload["logit_bias"] = request.get("logit_bias")
        return payload

    def _payload_meta(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a sanitized summary of the payload for logging.

        Avoids logging raw message content or secrets. Only includes counts/flags.
        """
        meta: Dict[str, Any] = {}
        try:
            meta["model"] = payload.get("model")
            meta["stream"] = bool(payload.get("stream"))
            msgs = payload.get("messages") or []
            meta["messages_count"] = len(msgs) if isinstance(msgs, list) else 0
            meta["has_tools"] = bool(payload.get("tools"))
            if payload.get("tool_choice") is not None:
                # Only surface that tool_choice is present; not its full content
                meta["tool_choice_present"] = True
            # Common numeric knobs (if present)
            for k in ("temperature", "top_p", "max_tokens"):
                if payload.get(k) is not None:
                    meta[k] = payload.get(k)
        except Exception:
            pass
        return meta

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
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
                    logger.debug(
                        "DeepSeekAdapter.chat POST {} with meta {}",
                        url,
                        self._payload_meta(payload),
                    )
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                # Try to log upstream response text if available
                try:
                    import httpx  # type: ignore
                    if isinstance(e, getattr(httpx, "HTTPStatusError", ())):
                        r = getattr(e, "response", None)
                        status = getattr(r, "status_code", "?")
                        text = ""
                        try:
                            text = (r.text or "")[:500]
                        except Exception:
                            text = "<unreadable>"
                        logger.error(
                            "DeepSeekAdapter.chat upstream error {}: {}",
                            status,
                            text,
                        )
                except Exception:
                    pass
                raise self.normalize_error(e)

        kwargs = self._to_handler_args(request)
        if "stream" not in request and "streaming" not in request:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        fn = getattr(_legacy, "chat_with_deepseek", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            fname = getattr(fn, "__name__", "") or ""
            # Only honor an explicitly monkeypatched test helper to avoid recursion.
            if (mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                return fn(**kwargs)  # type: ignore[misc]
        # Fallback to the preserved legacy implementation to avoid adapter recursion under pytest
        return _legacy.legacy_chat_with_deepseek(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
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
                    logger.debug(
                        "DeepSeekAdapter.stream POST {} with meta {}",
                        url,
                        self._payload_meta(payload),
                    )
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
                # Try to log upstream response text if available
                try:
                    import httpx  # type: ignore
                    if isinstance(e, getattr(httpx, "HTTPStatusError", ())):
                        r = getattr(e, "response", None)
                        status = getattr(r, "status_code", "?")
                        text = ""
                        try:
                            text = (r.text or "")[:500]
                        except Exception:
                            text = "<unreadable>"
                        logger.error(
                            "DeepSeekAdapter.stream upstream error {}: {}",
                            status,
                            text,
                        )
                except Exception:
                    pass
                raise self.normalize_error(e)

        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        fn = getattr(_legacy, "chat_with_deepseek", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            fname = getattr(fn, "__name__", "") or ""
            if (mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod or fname.startswith("_fake")):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_deepseek(**kwargs)

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

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
