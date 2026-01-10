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
from tldw_Server_API.app.core.LLM_Calls.error_utils import (
    get_http_error_text,
    get_http_status_from_exception,
    is_http_status_error,
    log_http_400_body,
)
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload
from loguru import logger
import re

# Expose a patchable factory for tests; production uses the centralized client.
# Important: make this a delegating function so that monkeypatching
# `_hc_create_client` in tests takes effect (rather than binding once at import).
def http_client_factory(*args, **kwargs):  # pragma: no cover - behavior verified by unit tests
    return _hc_create_client(*args, **kwargs)


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

    def _apply_config_defaults(self, request: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(request)
        cfg = (merged.get("app_config") or {}).get("deepseek_api", {})

        def _coerce_float(value: Any) -> Any:
            if value is None or isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    return value
            return value

        def _coerce_int(value: Any) -> Any:
            if value is None or isinstance(value, bool):
                return value
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(float(value))
                except ValueError:
                    return value
            return value

        if merged.get("api_key") is None and cfg.get("api_key") is not None:
            merged["api_key"] = cfg.get("api_key")
        if merged.get("model") is None:
            merged["model"] = cfg.get("model") or "deepseek-chat"
        if merged.get("temperature") is None and cfg.get("temperature") is not None:
            merged["temperature"] = _coerce_float(cfg.get("temperature"))
        if merged.get("top_p") is None and cfg.get("top_p") is not None:
            merged["top_p"] = _coerce_float(cfg.get("top_p"))
        if merged.get("max_tokens") is None and cfg.get("max_tokens") is not None:
            merged["max_tokens"] = _coerce_int(cfg.get("max_tokens"))
        if merged.get("seed") is None and cfg.get("seed") is not None:
            merged["seed"] = _coerce_int(cfg.get("seed"))
        if merged.get("stop") is None and cfg.get("stop") is not None:
            merged["stop"] = cfg.get("stop")
        if merged.get("logprobs") is None and cfg.get("logprobs") is not None:
            merged["logprobs"] = cfg.get("logprobs")
        if merged.get("top_logprobs") is None and cfg.get("top_logprobs") is not None:
            merged["top_logprobs"] = _coerce_int(cfg.get("top_logprobs"))
        if merged.get("presence_penalty") is None and cfg.get("presence_penalty") is not None:
            merged["presence_penalty"] = _coerce_float(cfg.get("presence_penalty"))
        if merged.get("frequency_penalty") is None and cfg.get("frequency_penalty") is not None:
            merged["frequency_penalty"] = _coerce_float(cfg.get("frequency_penalty"))
        if merged.get("response_format") is None and cfg.get("response_format") is not None:
            merged["response_format"] = cfg.get("response_format")
        if merged.get("n") is None and cfg.get("n") is not None:
            merged["n"] = _coerce_int(cfg.get("n"))
        if merged.get("user") is None and cfg.get("user") is not None:
            merged["user"] = cfg.get("user")
        if merged.get("tools") is None and cfg.get("tools") is not None:
            merged["tools"] = cfg.get("tools")
        if merged.get("tool_choice") is None and cfg.get("tool_choice") is not None:
            merged["tool_choice"] = cfg.get("tool_choice")
        if merged.get("logit_bias") is None and cfg.get("logit_bias") is not None:
            merged["logit_bias"] = cfg.get("logit_bias")
        return merged

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
        request = validate_payload(self.name, request or {})
        request = self._apply_config_defaults(request)
        api_key = request.get("api_key")
        if not api_key:
            from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
            raise ChatConfigurationError(provider=self.name, message="DeepSeek API Key required.")
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
            if is_http_status_error(e):
                status = get_http_status_from_exception(e) or "?"
                text = get_http_error_text(e)
                if len(text) > 500:
                    text = text[:500]
                logger.error(
                    "DeepSeekAdapter.chat upstream error {}: {}",
                    status,
                    text,
                )
            raise self.normalize_error(e)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        request = self._apply_config_defaults(request)
        api_key = request.get("api_key")
        if not api_key:
            from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
            raise ChatConfigurationError(provider=self.name, message="DeepSeek API Key required.")
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
            if is_http_status_error(e):
                status = get_http_status_from_exception(e) or "?"
                text = get_http_error_text(e)
                if len(text) > 500:
                    text = text[:500]
                logger.error(
                    "DeepSeekAdapter.stream upstream error {}: {}",
                    status,
                    text,
                )
            raise self.normalize_error(e)

    def normalize_error(self, exc: Exception):  # type: ignore[override]
        def _redact_secrets(text: str) -> str:
            try:
                # Redact Authorization bearer tokens
                text = re.sub(r"(?i)(Authorization\s*:\s*Bearer)\s+[^\s,;]+", r"\1 [REDACTED]", text)
                text = re.sub(r"(?i)(Bearer)\s+[^\s,;]+", r"\1 [REDACTED]", text)
                # Redact phrases like "api key: XYZ" or "api_key=XYZ"
                text = re.sub(r"(?i)(api[ _-]?key\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]", text)
            except Exception:
                pass
            return text
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
            if resp is not None:
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
                composed = (f"{typ} {msg}" if typ else msg) or str(exc)
                detail = _redact_secrets(composed)
            else:
                detail = _redact_secrets(get_http_error_text(exc))
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
