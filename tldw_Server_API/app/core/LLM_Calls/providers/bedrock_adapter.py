from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List
import os

from .base import ChatProvider, apply_tool_choice
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
from tldw_Server_API.app.core.LLM_Calls.sse import (
    normalize_provider_line,
    is_done_line,
    sse_done,
    finalize_stream,
)
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload
from tldw_Server_API.app.core.LLM_Calls.payload_utils import merge_extra_body, merge_extra_headers
from tldw_Server_API.app.core.LLM_Calls.streaming import wrap_sync_stream
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
)


# Patchable client factory (mirrors other adapters)
http_client_factory = _hc_create_client

_BEDROCK_OPENAI_MODEL_MAP = {
    "gpt-oss-20b-1": "openai.gpt-oss-20b-1:0",
}
_OPENAI_STYLE_PREFIXES = ("gpt-", "gpt_", "o1", "o3", "text-", "chatgpt")


class BedrockAdapter(ChatProvider):
    """AWS Bedrock (OpenAI-compatible) chat adapter.

    Targets the Bedrock Runtime OpenAI compatibility surface:
      https://bedrock-runtime.<region>.amazonaws.com/openai/v1/chat/completions

    Auth uses a Bearer token (BEDROCK_API_KEY or AWS_BEARER_TOKEN_BEDROCK) unless
    an explicit api_key is supplied via the request dict.
    """

    name = "bedrock"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 90,
            "max_output_tokens_default": None,
        }

    def _use_native_http(self) -> bool:
        # Always use native HTTP unless explicitly disabled
        v = (os.getenv("LLM_ADAPTERS_NATIVE_HTTP_BEDROCK") or "").lower()
        if v in {"0", "false", "no", "off"}:
            return False
        return True

    def _base_url(self, request: Optional[Dict[str, Any]] = None) -> str:
        # Allow explicit base override; otherwise derive from runtime endpoint or region
        override = (request or {}).get("base_url")
        if isinstance(override, str) and override.strip():
            return override.strip().rstrip("/")
        runtime = os.getenv("BEDROCK_RUNTIME_ENDPOINT")
        if runtime:
            # Expect a hostname like https://bedrock-runtime.us-west-2.amazonaws.com
            return runtime.rstrip("/") + "/openai"
        base = (
            os.getenv("BEDROCK_API_BASE_URL")
            or os.getenv("BEDROCK_OPENAI_BASE_URL")
        )
        if base:
            return base

        region = os.getenv("BEDROCK_REGION") or "us-west-2"
        return f"https://bedrock-runtime.{region}.amazonaws.com/openai"

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        key = api_key or os.getenv("BEDROCK_API_KEY") or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        h = {"Content-Type": "application/json"}
        if key:
            h["Authorization"] = f"Bearer {key}"
        return h

    def _normalize_model(self, model: Optional[str]) -> Optional[str]:
        if model is None:
            return None
        normalized = model.strip()
        if not normalized:
            return normalized
        mapped = _BEDROCK_OPENAI_MODEL_MAP.get(normalized)
        if mapped:
            return mapped
        lowered = normalized.lower()
        if lowered.startswith(_OPENAI_STYLE_PREFIXES):
            raise ChatConfigurationError(
                provider=self.name,
                message=(
                    "Invalid Bedrock model ID. Use a Bedrock model identifier like "
                    "'anthropic.claude-3-5-sonnet-20241022-v2:0' or "
                    "'meta.llama3-8b-instruct', not an OpenAI-style ID."
                ),
            )
        if "." not in normalized:
            raise ChatConfigurationError(
                provider=self.name,
                message=(
                    "Invalid Bedrock model ID. Expected a provider-qualified model "
                    "like 'anthropic.claude-3-5-sonnet-20241022-v2:0'."
                ),
            )
        return normalized

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = request.get("messages") or []
        system_message = request.get("system_message")
        payload_messages: List[Dict[str, Any]] = []
        if system_message:
            payload_messages.append({"role": "system", "content": system_message})
        payload_messages.extend(messages)
        model = self._normalize_model(request.get("model"))
        payload: Dict[str, Any] = {
            "model": model,
            "messages": payload_messages,
            "temperature": request.get("temperature"),
            "top_p": request.get("top_p"),
            "max_tokens": request.get("max_tokens"),
            "n": request.get("n"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logit_bias": request.get("logit_bias"),
            "user": request.get("user"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "seed": request.get("seed"),
        }
        # Optional fields
        if request.get("response_format") is not None:
            payload["response_format"] = request.get("response_format")
        if request.get("stop") is not None:
            payload["stop"] = request.get("stop")
        tools = request.get("tools")
        if tools is not None:
            payload["tools"] = tools
        apply_tool_choice(payload, tools, request.get("tool_choice"))
        return payload

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        if not self._use_native_http():
            raise RuntimeError("BedrockAdapter native HTTP disabled by configuration")

        api_key = request.get("api_key")
        headers = self._headers(api_key)
        url = f"{self._base_url(request).rstrip('/')}/v1/chat/completions"
        payload = self._build_payload(request)
        payload["stream"] = False
        payload = merge_extra_body(payload, request)
        headers = merge_extra_headers(headers, request)
        try:
            with http_client_factory(timeout=timeout or 90.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            raise self.normalize_error(e)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        if not self._use_native_http():
            raise RuntimeError("BedrockAdapter native HTTP disabled by configuration")

        api_key = request.get("api_key")
        headers = self._headers(api_key)
        url = f"{self._base_url(request).rstrip('/')}/v1/chat/completions"
        payload = self._build_payload(request)
        payload["stream"] = True
        payload = merge_extra_body(payload, request)
        headers = merge_extra_headers(headers, request)
        try:
            with http_client_factory(timeout=timeout or 90.0) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    seen_done = False
                    for raw in resp.iter_lines():
                        if not raw:
                            continue
                        # Normalize to str for helper functions
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
                    # Ensure a single terminal DONE marker
                    for tail in finalize_stream(response=resp, done_already=seen_done):
                        yield tail
            return
        except Exception as e:
            raise self.normalize_error(e)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        async for item in wrap_sync_stream(self.stream(request, timeout=timeout)):
            yield item

    def normalize_error(self, exc: Exception):  # type: ignore[override]
        # Reuse Groq/OpenAI-style mapping which inspects httpx/requests error payloads
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
