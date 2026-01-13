from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List
import os

from .base import ChatProvider
from tldw_Server_API.app.core.LLM_Calls.sse import (
    normalize_provider_line,
    is_done_line,
    sse_done,
    finalize_stream,
)
from tldw_Server_API.app.core.LLM_Calls.streaming import wrap_sync_stream
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload
from tldw_Server_API.app.core.LLM_Calls.payload_utils import merge_extra_body, merge_extra_headers


def _prefer_httpx_in_tests() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
    fetch as _hc_fetch,
    RetryPolicy as _HC_RetryPolicy,
)

http_client_factory = _hc_create_client


class OpenRouterAdapter(ChatProvider):
    name = "openrouter"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 90,
            "max_output_tokens_default": 8192,
        }

    def _use_native_http(self) -> bool:
        # Always native unless explicitly disabled
        v = (os.getenv("LLM_ADAPTERS_NATIVE_HTTP_OPENROUTER") or "").lower()
        if v in {"0", "false", "no", "off"}:
            return False
        return True

    def _base_url(self) -> str:
        import os
        return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    def _resolve_base_url(self, request: Dict[str, Any]) -> str:
        override = (request or {}).get("base_url")
        if isinstance(override, str) and override.strip():
            return override.strip()
        try:
            cfg = (request or {}).get("app_config") or {}
            or_cfg = cfg.get("openrouter_api") or {}
            base = or_cfg.get("api_base_url")
            if isinstance(base, str) and base.strip():
                return base.strip()
        except Exception:
            pass
        return self._base_url()

    def _resolve_timeout(self, request: Dict[str, Any], fallback: Optional[float]) -> float:
        try:
            cfg = (request or {}).get("app_config") or {}
            or_cfg = cfg.get("openrouter_api") or {}
            t = or_cfg.get("api_timeout")
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

    def _headers(self, api_key: Optional[str], request: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Build headers including OpenRouter-specific metadata.

        - Authorization: Bearer <key>
        - HTTP-Referer: site URL (from config or env), defaults to http://localhost
        - X-Title: site name (from config or env), defaults to TLDW-API
        """
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"

        # Preserve provider-specific header quirks used by OpenRouter
        site_url = os.getenv("OPENROUTER_SITE_URL")
        site_name = os.getenv("OPENROUTER_SITE_NAME")
        try:
            cfg = (request or {}).get("app_config") or {}
            or_cfg = cfg.get("openrouter_api") or {}
            site_url = or_cfg.get("site_url") or site_url
            site_name = or_cfg.get("site_name") or site_name
        except Exception:
            # best-effort; fall back to env/defaults
            pass
        # OpenRouter strongly prefers a valid public referer; use their site as a safe default
        h["HTTP-Referer"] = site_url or "https://openrouter.ai"
        h["X-Title"] = site_name or "TLDW-API"
        return h

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = request.get("messages") or []
        system_message = request.get("system_message")
        payload_messages: List[Dict[str, Any]] = []
        if system_message:
            payload_messages.append({"role": "system", "content": system_message})
        payload_messages.extend(messages)
        # Start with required fields
        payload = {
            "model": request.get("model"),
            "messages": payload_messages,
        }
        # Add optional fields only when not None to avoid sending nulls
        for key in (
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "max_tokens",
            "n",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "user",
        ):
            val = request.get(key)
            if val is not None:
                payload[key] = val
        tool_choice = request.get("tool_choice")
        tools = request.get("tools")
        if tool_choice == "none":
            payload["tool_choice"] = "none"
        elif tool_choice is not None and tools:
            payload["tool_choice"] = tool_choice
        if tools is not None and tool_choice != "none":
            payload["tools"] = tools
        rf = request.get("response_format")
        # Forward response_format as-is for parity with other adapters and tests
        # (e.g., JSON mode: {"type": "json_object"}).
        if rf is not None:
            payload["response_format"] = rf
        if request.get("seed") is not None:
            payload["seed"] = request.get("seed")
        if request.get("stop") is not None:
            payload["stop"] = request.get("stop")
        return payload

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key, request)
            url = f"{self._resolve_base_url(request).rstrip('/')}/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = False
            payload = merge_extra_body(payload, request)
            headers = merge_extra_headers(headers, request)
            try:
                resolved_timeout = self._resolve_timeout(request, timeout)
                with http_client_factory(timeout=resolved_timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                raise self.normalize_error(e)

        # Native disabled -> error to avoid legacy recursion
        raise RuntimeError("OpenRouterAdapter native HTTP disabled by configuration")

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key, request)
            url = f"{self._resolve_base_url(request).rstrip('/')}/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = True
            payload = merge_extra_body(payload, request)
            headers = merge_extra_headers(headers, request)
            try:
                resolved_timeout = self._resolve_timeout(request, timeout)
                with http_client_factory(timeout=resolved_timeout) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as resp:
                        resp.raise_for_status()
                        seen_done = False
                        for line in resp.iter_lines():
                            if not line:
                                continue
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

        # Native disabled -> error to avoid legacy recursion
        raise RuntimeError("OpenRouterAdapter native HTTP disabled by configuration")

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        async for item in wrap_sync_stream(self.stream(request, timeout=timeout)):
            yield item

    def normalize_error(self, exc: Exception):  # type: ignore[override]
        """Parse OpenRouter error payloads and map to Chat*Error types.

        OpenRouter is OpenAI-compatible; error bodies often match {error: {message, type}}.
        """
        from tldw_Server_API.app.core.LLM_Calls.error_utils import (
            get_http_status_from_exception,
            get_http_error_text,
            is_http_status_error,
            log_http_400_body,
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
            log_http_400_body(self.name, exc, body)
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
