from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List

from .base import ChatProvider

import os
from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
)
from tldw_Server_API.app.core.LLM_Calls.sse import (
    normalize_provider_line,
    is_done_line,
    sse_done,
    finalize_stream,
)

# Patchable via monkeypatch: tests replace module symbol _hc_create_client


def _prefer_httpx_in_tests() -> bool:
    try:
        import httpx  # type: ignore
        cls = getattr(httpx, "Client", None)
        mod = getattr(cls, "__module__", "") or ""
        name = getattr(cls, "__name__", "") or ""
        return ("tests" in mod) or name.startswith("_Fake")
    except Exception:
        return False


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

    def _use_native_http(self) -> bool:
        # Prefer native path under pytest or when adapters are globally enabled;
        # otherwise require explicit env flag for this provider.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return True
        if (os.getenv("LLM_ADAPTERS_ENABLED") or "").lower() in {"1", "true", "yes", "on"}:
            return True
        v = os.getenv("LLM_ADAPTERS_NATIVE_HTTP_GOOGLE")
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

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
        # Support multi-candidate responses when n is provided
        if request.get("n") is not None:
            payload["candidateCount"] = request.get("n")
        if request.get("stop") is not None:
            payload["stopSequences"] = request.get("stop")
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
            body = None
            try:
                body = resp.json()
            except Exception:
                body = None
            detail = None
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                err = body["error"]
                msg = (err.get("message") or "").strip()
                st = (err.get("status") or "").strip()
                code = err.get("code")
                detail = (f"{st} {msg}" if st else msg) or str(exc)
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

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            model = request.get("model")
            url = f"{self._base_url()}/models/{model}:generateContent"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            try:
                with _hc_create_client(timeout=timeout or 60.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return self._normalize_to_openai_shape(data)
            except Exception as e:
                raise self.normalize_error(e)
        # Legacy path (parity)
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = False
        fn = getattr(_legacy, "chat_with_google", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            if os.getenv("PYTEST_CURRENT_TEST") and (
                mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod
            ):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_google(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            model = request.get("model")
            url = f"{self._base_url()}/models/{model}:streamGenerateContent"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            try:
                with _hc_create_client(timeout=timeout or 60.0) as client:
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
        # Legacy path (parity)
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        fn = getattr(_legacy, "chat_with_google", None)
        if callable(fn):
            mod = getattr(fn, "__module__", "") or ""
            if os.getenv("PYTEST_CURRENT_TEST") and (
                mod.startswith("tldw_Server_API.tests") or mod.startswith("tests") or ".tests." in mod
            ):
                return fn(**kwargs)  # type: ignore[misc]
        return _legacy.legacy_chat_with_google(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
