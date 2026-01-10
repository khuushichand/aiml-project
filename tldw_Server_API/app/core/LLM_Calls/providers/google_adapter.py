from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List

from .base import ChatProvider

import os
import json
from loguru import logger
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
)
from tldw_Server_API.app.core.LLM_Calls.sse import (
    normalize_provider_line,
    is_done_line,
    sse_done,
    finalize_stream,
    openai_delta_chunk,
    sse_data,
)
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload

# Expose a patchable factory for tests; production uses the centralized client
http_client_factory = _hc_create_client


def _stream_debug_enabled(provider: str) -> bool:
    value = (os.getenv("LLM_ADAPTERS_STREAM_DEBUG") or "").strip().lower()
    if not value:
        return False
    if value in {"1", "true", "yes", "on", "all"}:
        return True
    providers = {p.strip() for p in value.split(",") if p.strip()}
    return provider.lower() in providers


class GoogleAdapter(ChatProvider):
    name = "google"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 90,
            "max_output_tokens_default": None,
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
            "topk": request.get("top_k"),
            "max_output_tokens": request.get("max_tokens"),
            "stop_sequences": request.get("stop"),
            "candidate_count": request.get("n"),
            "response_format": request.get("response_format"),
            "tools": request.get("tools"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }

    def _apply_config_defaults(self, request: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(request)
        cfg = (merged.get("app_config") or {}).get("google_api", {})
        if merged.get("api_key") is None and cfg.get("api_key") is not None:
            merged["api_key"] = cfg.get("api_key")
        if merged.get("model") is None:
            merged["model"] = cfg.get("model") or "gemini-1.5-flash-latest"
        if merged.get("temperature") is None and cfg.get("temperature") is not None:
            merged["temperature"] = cfg.get("temperature")
        if merged.get("top_p") is None:
            merged["top_p"] = cfg.get("top_p", cfg.get("topP"))
        if merged.get("top_k") is None:
            merged["top_k"] = cfg.get("top_k", cfg.get("topK"))
        if merged.get("max_tokens") is None:
            merged["max_tokens"] = cfg.get("max_output_tokens", cfg.get("max_tokens"))
        if merged.get("stop") is None and cfg.get("stop_sequences") is not None:
            merged["stop"] = cfg.get("stop_sequences")
        if merged.get("n") is None:
            merged["n"] = cfg.get("candidate_count", cfg.get("n"))
        if merged.get("response_format") is None and cfg.get("response_format") is not None:
            merged["response_format"] = cfg.get("response_format")
        if merged.get("tools") is None and cfg.get("tools") is not None:
            merged["tools"] = cfg.get("tools")
        return merged

    def _base_url(self) -> str:
        return os.getenv("GOOGLE_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        # Gemini typically accepts API key via header or query param. Prefer header here.
        h = {"Content-Type": "application/json"}
        if api_key:
            h["x-goog-api-key"] = api_key
        return h

    @staticmethod
    def _to_gemini_contents(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        contents: List[Dict[str, Any]] = []
        allow_image_urls = os.getenv("LLM_ADAPTERS_GEMINI_IMAGE_URLS_BETA")
        allow_audio_urls = os.getenv("LLM_ADAPTERS_GEMINI_AUDIO_URLS_BETA")
        allow_video_urls = os.getenv("LLM_ADAPTERS_GEMINI_VIDEO_URLS_BETA")
        for m in messages:
            role = m.get("role") or "user"
            # Gemini uses "model" instead of "assistant"
            if role == "assistant":
                role = "model"
            content = m.get("content")
            parts: List[Dict[str, Any]] = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type")
                    if ptype == "text" and "text" in part:
                        parts.append({"text": str(part.get("text", ""))})
                    elif ptype in {"image", "image_url"}:
                        # OpenAI-style image parts: {"type":"image_url","image_url": {"url": "..."}}
                        url_obj = part.get("image_url")
                        u = None
                        if isinstance(url_obj, dict):
                            u = url_obj.get("url")
                        elif isinstance(url_obj, str):
                            u = url_obj
                        if isinstance(u, str) and u:
                            if u.startswith("data:") and ";base64," in u:
                                try:
                                    header, b64 = u.split(",", 1)
                                    mime = header.split(":", 1)[1].split(";", 1)[0] or "application/octet-stream"
                                    parts.append({"inlineData": {"mimeType": mime, "data": b64}})
                                except Exception:
                                    parts.append({"text": "[image: unsupported data URI]"})
                            elif allow_image_urls and (u.startswith("http://") or u.startswith("https://")):
                                parts.append({"fileData": {"mimeType": "image/*", "fileUri": u}})
                            else:
                                parts.append({"text": f"Image: {u}"})
                    elif ptype in {"audio", "audio_url", "input_audio"}:
                        aobj = part.get("audio_url") or part.get("audio")
                        u = None
                        if isinstance(aobj, dict):
                            u = aobj.get("url")
                        elif isinstance(aobj, str):
                            u = aobj
                        if isinstance(u, str) and u:
                            if u.startswith("data:") and ";base64," in u:
                                try:
                                    header, b64 = u.split(",", 1)
                                    mime = header.split(":", 1)[1].split(";", 1)[0] or "audio/*"
                                    parts.append({"inlineData": {"mimeType": mime, "data": b64}})
                                except Exception:
                                    parts.append({"text": "[audio: unsupported data URI]"})
                            elif allow_audio_urls and (u.startswith("http://") or u.startswith("https://")):
                                parts.append({"fileData": {"mimeType": "audio/*", "fileUri": u}})
                            else:
                                parts.append({"text": f"Audio: {u}"})
                    elif ptype in {"video", "video_url", "input_video"}:
                        vobj = part.get("video_url") or part.get("video")
                        u = None
                        if isinstance(vobj, dict):
                            u = vobj.get("url")
                        elif isinstance(vobj, str):
                            u = vobj
                        if isinstance(u, str) and u:
                            if u.startswith("data:") and ";base64," in u:
                                try:
                                    header, b64 = u.split(",", 1)
                                    mime = header.split(":", 1)[1].split(";", 1)[0] or "video/*"
                                    parts.append({"inlineData": {"mimeType": mime, "data": b64}})
                                except Exception:
                                    parts.append({"text": "[video: unsupported data URI]"})
                            elif allow_video_urls and (u.startswith("http://") or u.startswith("https://")):
                                parts.append({"fileData": {"mimeType": "video/*", "fileUri": u}})
                            else:
                                parts.append({"text": f"Video: {u}"})
            contents.append({"role": role, "parts": parts or [{"text": ""}]})
        return contents

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = request.get("messages") or []
        system_message = request.get("system_message")
        payload: Dict[str, Any] = {
            "contents": self._to_gemini_contents(messages),
            "generationConfig": {}
        }
        gc = payload["generationConfig"]
        if request.get("temperature") is not None:
            gc["temperature"] = request.get("temperature")
        if request.get("top_p") is not None:
            gc["topP"] = request.get("top_p")
        if request.get("top_k") is not None:
            gc["topK"] = request.get("top_k")
        if request.get("max_tokens") is not None:
            gc["maxOutputTokens"] = request.get("max_tokens")
        # Support multi-candidate responses when n is provided (Gemini expects this in generationConfig)
        if request.get("n") is not None:
            gc["candidateCount"] = request.get("n")
        # Stop sequences belong to generationConfig for the models API
        if request.get("stop") is not None:
            gc["stopSequences"] = request.get("stop")
        response_format = request.get("response_format")
        if isinstance(response_format, dict) and response_format.get("type") == "json_object":
            gc["responseMimeType"] = "application/json"
        # Best-effort system instruction
        if system_message:
            payload["systemInstruction"] = {"parts": [{"text": system_message}]}
        # Optional: map OpenAI-style tools to Gemini functionDeclarations behind a flag
        try:
            if os.getenv("LLM_ADAPTERS_GEMINI_TOOLS_BETA"):
                tools = request.get("tools") or []
                fdecls: List[Dict[str, Any]] = []
                for t in tools:
                    if isinstance(t, dict) and t.get("type") == "function" and isinstance(t.get("function"), dict):
                        fn = t["function"]
                        name = str(fn.get("name", ""))
                        if not name:
                            continue
                        # Pass OpenAI JSON Schema through as-is; callers can supply Gemini-flavored schema if needed
                        params = fn.get("parameters")
                        fdecl = {"name": name}
                        if params is not None:
                            fdecl["parameters"] = params
                        if fn.get("description"):
                            fdecl["description"] = str(fn.get("description"))
                        fdecls.append(fdecl)
                if fdecls:
                    payload["tools"] = [{"functionDeclarations": fdecls}]
        except Exception:
            # tools mapping is best-effort and optional
            pass
        if "tools" not in payload and request.get("tools") is not None:
            payload["tools"] = request.get("tools")
        return payload

    @staticmethod
    def _normalize_to_openai_shape(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            cands = data.get("candidates") or []
            choices: List[Dict[str, Any]] = []
            for idx, cand in enumerate(cands):
                content = (cand or {}).get("content") or {}
                parts = content.get("parts") or []
                text_accum = ""
                tool_calls: List[Dict[str, Any]] = []
                if parts:
                    tc_idx = 0
                    for p in parts:
                        if not isinstance(p, dict):
                            continue
                        if isinstance(p.get("text"), str):
                            text_accum += p.get("text") or ""
                        elif isinstance(p.get("functionCall"), dict):
                            fc = p["functionCall"]
                            name = str(fc.get("name", ""))
                            args = fc.get("args")
                            try:
                                import json as _json
                                arg_str = _json.dumps(args if args is not None else {})
                            except Exception:
                                arg_str = "{}"
                            tool_calls.append({
                                "id": f"call_{tc_idx}",
                                "type": "function",
                                "function": {"name": name, "arguments": arg_str},
                            })
                            tc_idx += 1
                message: Dict[str, Any] = {"role": "assistant", "content": text_accum or None}
                if tool_calls:
                    message["tool_calls"] = tool_calls
                finish_reason_raw = cand.get("finishReason")
                finish_map = {"STOP": "stop", "MAX_TOKENS": "length"}
                finish_reason = finish_map.get(str(finish_reason_raw).upper(), finish_reason_raw)
                choices.append({
                    "index": idx,
                    "message": message,
                    "finish_reason": finish_reason,
                })

            usage_src = data.get("usageMetadata") or {}
            usage = {
                "prompt_tokens": usage_src.get("promptTokenCount"),
                "completion_tokens": usage_src.get("candidatesTokenCount"),
                "total_tokens": usage_src.get("totalTokenCount"),
            }
            return {
                "id": data.get("id") or data.get("responseId"),
                "object": "chat.completion",
                "choices": choices or [{"index": 0, "message": {"role": "assistant", "content": None}, "finish_reason": None}],
                "usage": usage,
            }
        except Exception:
            return data

    @staticmethod
    def _stream_event_deltas(event: Any) -> Iterable[str]:
        if isinstance(event, list):
            for item in event:
                yield from GoogleAdapter._stream_event_deltas(item)
            return
        if not isinstance(event, dict):
            return
        cands = event.get("candidates") or []
        tool_index = 0
        for idx, cand in enumerate(cands):
            emitted = False
            content = (cand or {}).get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if isinstance(part.get("text"), str):
                    text = part.get("text") or ""
                    if text:
                        yield openai_delta_chunk(text)
                        emitted = True
                elif isinstance(part.get("functionCall"), dict):
                    fc = part.get("functionCall") or {}
                    name = str(fc.get("name") or "")
                    args = fc.get("args")
                    try:
                        arg_str = json.dumps(args if args is not None else {})
                    except Exception:
                        arg_str = "{}"
                    yield sse_data({
                        "choices": [{
                            "index": idx,
                            "delta": {
                                "tool_calls": [{
                                    "index": tool_index,
                                    "id": f"call_{tool_index}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": arg_str},
                                }]
                            },
                        }]
                    })
                    tool_index += 1
                    emitted = True
            finish_reason_raw = cand.get("finishReason")
            if finish_reason_raw and not emitted:
                finish_map = {"STOP": "stop", "MAX_TOKENS": "length"}
                finish_reason = finish_map.get(str(finish_reason_raw).upper(), finish_reason_raw)
                yield sse_data({
                    "choices": [{
                        "index": idx,
                        "delta": {},
                        "finish_reason": finish_reason,
                    }]
                })

    def normalize_error(self, exc: Exception):  # type: ignore[override]
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
                err = body["error"]
                msg = (err.get("message") or "").strip()
                st = (err.get("status") or "").strip()
                code = err.get("code")
                detail = (f"{st} {msg}" if st else msg) or str(exc)
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
        model = request.get("model")
        if not api_key:
            from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
            raise ChatConfigurationError(provider=self.name, message="Google API Key required.")
        url = f"{self._base_url()}/models/{model}:generateContent"
        headers = self._headers(api_key)
        payload = self._build_payload(request)
        try:
            with http_client_factory(timeout=timeout or 60.0) as client:
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
        model = request.get("model")
        if not api_key:
            from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
            raise ChatConfigurationError(provider=self.name, message="Google API Key required.")
        url = f"{self._base_url()}/models/{model}:streamGenerateContent?alt=sse"
        headers = self._headers(api_key)
        payload = self._build_payload(request)
        try:
            with http_client_factory(timeout=timeout or 60.0) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    debug_stream = _stream_debug_enabled(self.name)
                    seen_done = False
                    buffer = ""
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
                        stripped = line.strip()
                        if stripped.startswith("data:"):
                            payload_text = stripped[len("data:"):].strip()
                            if payload_text.lower() == "[done]":
                                if not seen_done:
                                    seen_done = True
                                    yield sse_done()
                                continue
                            try:
                                event = json.loads(payload_text)
                            except Exception:
                                normalized = normalize_provider_line(line)
                                if normalized is not None:
                                    yield normalized
                                continue
                            for delta in self._stream_event_deltas(event):
                                yield delta
                            continue
                        if stripped and (stripped.startswith("{") or stripped.startswith("[")):
                            buffer += stripped
                            try:
                                event = json.loads(buffer)
                            except Exception:
                                continue
                            buffer = ""
                            yielded = False
                            for delta in self._stream_event_deltas(event):
                                yielded = True
                                yield delta
                            if yielded:
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
