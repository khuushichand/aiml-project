from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List
import os

from .base import ChatProvider
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
    fetch as _hc_fetch,
    RetryPolicy as _HC_RetryPolicy,
)

http_client_factory = _hc_create_client


def _prefer_httpx_in_tests() -> bool:
    try:
        import httpx  # type: ignore
        cls = getattr(httpx, "Client", None)
        mod = getattr(cls, "__module__", "") or ""
        name = getattr(cls, "__name__", "") or ""
        return ("tests" in mod) or name.startswith("_Fake")
    except Exception:
        return False


class GroqAdapter(ChatProvider):
    name = "groq"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 60,
            "max_output_tokens_default": 4096,
        }

    def _use_native_http(self) -> bool:
        # Always native unless explicitly disabled
        v = (os.getenv("LLM_ADAPTERS_NATIVE_HTTP_GROQ") or "").lower()
        if v in {"0", "false", "no", "off"}:
            return False
        return True

    def _base_url(self) -> str:
        import os
        # Groq exposes OpenAI-compatible API under /openai/v1
        return os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

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
        payload = {
            "model": request.get("model"),
            "messages": payload_messages,
            "temperature": request.get("temperature"),
            "top_p": request.get("top_p"),
            "max_tokens": request.get("max_tokens"),
            "n": request.get("n"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logit_bias": request.get("logit_bias"),
            "user": request.get("user"),
        }
        # Tools and tool_choice gating (consistent with OpenAI-compatible behavior)
        tools = request.get("tools")
        if tools is not None:
            payload["tools"] = tools
        tc = request.get("tool_choice")
        if tc == "none":
            payload["tool_choice"] = "none"
        elif tc is not None and tools:
            payload["tool_choice"] = tc
        if request.get("response_format") is not None:
            payload["response_format"] = request.get("response_format")
        if request.get("seed") is not None:
            payload["seed"] = request.get("seed")
        if request.get("stop") is not None:
            payload["stop"] = request.get("stop")
        return payload

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            url = f"{self._base_url().rstrip('/')}/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                with http_client_factory(timeout=timeout or 60.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                raise self.normalize_error(e)

        # Native disabled -> error to avoid legacy recursion
        raise RuntimeError("GroqAdapter native HTTP disabled by configuration")

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            url = f"{self._base_url().rstrip('/')}/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = True
            try:
                with http_client_factory(timeout=timeout or 60.0) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as resp:
                        resp.raise_for_status()
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            yield line
                return
            except Exception as e:
                raise self.normalize_error(e)

        # Native disabled -> error to avoid legacy recursion
        raise RuntimeError("GroqAdapter native HTTP disabled by configuration")

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item

    def normalize_error(self, exc: Exception):  # type: ignore[override]
        """Parse Groq HTTP error payloads and map to Chat*Error with better messages.

        Groq uses an OpenAI-compatible surface; errors often include {error: {message, type}}.
        """
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
