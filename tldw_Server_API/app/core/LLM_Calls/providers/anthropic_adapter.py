from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List
import os
import asyncio
import threading

from .base import ChatProvider
from tldw_Server_API.app.core.LLM_Calls.sse import (
    openai_delta_chunk,
    sse_data,
    sse_done,
    normalize_provider_line,
    is_done_line,
    finalize_stream,
)
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload


def _prefer_httpx_in_tests() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
    fetch as _hc_fetch,
    RetryPolicy as _HC_RetryPolicy,
)

http_client_factory = _hc_create_client


class AnthropicAdapter(ChatProvider):
    name = "anthropic"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 60,
            "max_output_tokens_default": 8192,
        }

    def _use_native_http(self) -> bool:
        import os
        if os.getenv("PYTEST_CURRENT_TEST"):
            return True
        enabled = (os.getenv("LLM_ADAPTERS_ENABLED") or "").strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            return False
        if enabled in {"1", "true", "yes", "on"}:
            return True
        v = (os.getenv("LLM_ADAPTERS_NATIVE_HTTP_ANTHROPIC") or "").strip().lower()
        if v in {"0", "false", "no", "off"}:
            return False
        if v in {"1", "true", "yes", "on"}:
            return True
        return True

    def _anthropic_base_url(self) -> str:
        import os
        return os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")

    def _resolve_base_url(self, request: Dict[str, Any]) -> str:
        """Resolve API base URL with precedence: app_config -> env -> default."""
        try:
            cfg = (request or {}).get("app_config") or {}
            anth_cfg = cfg.get("anthropic_api") or {}
            base = anth_cfg.get("api_base_url")
            if isinstance(base, str) and base.strip():
                return base.strip()
        except Exception:
            pass
        return self._anthropic_base_url()

    def _resolve_timeout(self, request: Dict[str, Any], fallback: Optional[float]) -> float:
        """Resolve request timeout seconds from request/app_config, else fallback/capability default."""
        try:
            cfg = (request or {}).get("app_config") or {}
            anth_cfg = cfg.get("anthropic_api") or {}
            t = anth_cfg.get("api_timeout")
            if t is not None:
                # Accept int/float/str that can be cast to float
                try:
                    return float(t)
                except Exception:
                    pass
        except Exception:
            pass
        if fallback is not None:
            return float(fallback)
        # Use adapter capability default
        try:
            return float(self.capabilities().get("default_timeout_seconds", 60))
        except Exception:
            return 60.0

    def _headers(self, api_key: Optional[str]) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": api_key or "",
            "anthropic-version": "2023-06-01",
        }

    @staticmethod
    def _to_anthropic_messages(messages: List[Dict[str, Any]], system: Optional[str]) -> Dict[str, Any]:
        # Anthropic expects a list of {role, content}; include system separately
        out = {"messages": messages}
        if system:
            out["system"] = system
        return out

    def _parse_data_url_for_multimodal(self, url: str) -> Optional[tuple[str, str]]:
        try:
            if not isinstance(url, str) or not url.startswith("data:"):
                return None
            # Format: data:<mime>;base64,<data>
            head, b64 = url.split(",", 1)
            mime = head[5:]  # strip 'data:'
            if ";base64" in mime:
                mime = mime.replace(";base64", "").strip()
            return mime, b64
        except Exception:
            return None

    def _anthropic_image_source_from_part(self, image_url: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url_str = (image_url or {}).get("url")
        if not url_str:
            return None
        parsed = self._parse_data_url_for_multimodal(url_str)
        if parsed:
            mime_type, b64 = parsed
            return {"type": "base64", "media_type": mime_type, "data": b64}
        if isinstance(url_str, str) and url_str.startswith(("http://", "https://")):
            return {"type": "url", "url": url_str}
        return None

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        raw_messages = request.get("messages") or []
        system_message = request.get("system_message")

        # Convert OpenAI-style messages to Anthropic messages format
        messages: List[Dict[str, Any]] = []
        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content")
            parts: List[Dict[str, Any]] = []
            if isinstance(content, str):
                parts.append({"type": "text", "text": content})
            elif isinstance(content, list):
                for p in content:
                    if not isinstance(p, dict):
                        continue
                    pt = p.get("type")
                    if pt == "text":
                        parts.append({"type": "text", "text": p.get("text", "")})
                    elif pt == "image_url":
                        src = self._anthropic_image_source_from_part(p.get("image_url", {}))
                        if src:
                            parts.append({"type": "image", "source": src})
            if parts:
                messages.append({"role": role, "content": parts})

        payload = {
            "model": request.get("model"),
            "messages": messages,
            "max_tokens": request.get("max_tokens") or 1024,
        }
        if system_message:
            payload["system"] = system_message
        if request.get("temperature") is not None:
            payload["temperature"] = request.get("temperature")
        if request.get("top_p") is not None:
            payload["top_p"] = request.get("top_p")
        if request.get("top_k") is not None:
            payload["top_k"] = request.get("top_k")
        if request.get("stop") is not None:
            payload["stop_sequences"] = request.get("stop")
        # Tools mapping (OpenAI-style → Anthropic)
        tool_choice = request.get("tool_choice")
        tools = request.get("tools")
        if tool_choice == "none":
            # Honor explicit none by omitting tools entirely
            tools = None
        if isinstance(tools, list) and tools:
            converted: List[Dict[str, Any]] = []
            for t in tools:
                try:
                    if isinstance(t, dict) and (t.get("type") == "function") and isinstance(t.get("function"), dict):
                        fn = t["function"]
                        # Require a non-empty string function name; otherwise skip as malformed.
                        name_raw = fn.get("name")
                        if not isinstance(name_raw, str):
                            continue
                        name = name_raw.strip()
                        if not name:
                            continue
                        desc_val = fn.get("description")
                        desc = str(desc_val) if isinstance(desc_val, (str, int, float)) else (desc_val or "")
                        schema = fn.get("parameters") or {}
                        if not isinstance(schema, dict):
                            schema = {}
                        converted.append({
                            "name": name,
                            "description": desc,
                            "input_schema": schema,
                        })
                except Exception:
                    continue
            # Only include tools if at least one valid entry exists.
            # Valid means function name is a non-empty string; malformed entries are skipped.
            # This ensures tests like malformed-tools expect 'tools' to be omitted entirely.
            # Filter again defensively in case prior logic added any invalid entries.
            converted = [
                t for t in converted
                if isinstance(t.get("name"), str) and t.get("name", "").strip()
            ]
            if converted:
                payload["tools"] = converted
        # tool_choice mapping (force a specific tool when requested)
        if isinstance(tool_choice, dict):
            try:
                if tool_choice.get("type") == "function" and isinstance(tool_choice.get("function"), dict):
                    name = tool_choice["function"].get("name")
                    if name:
                        payload["tool_choice"] = {"type": "tool", "name": str(name)}
            except Exception:
                pass
        return payload

    @staticmethod
    def _normalize_to_openai_shape(data: Dict[str, Any]) -> Dict[str, Any]:
        # Best-effort shaping of Anthropic "message" into OpenAI-like chat completion
        if not (isinstance(data, dict) and data.get("type") == "message"):
            return data
        parts = data.get("content") or []
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        if isinstance(parts, list):
            for p in parts:
                if not isinstance(p, dict):
                    continue
                if p.get("type") == "text":
                    text_parts.append(p.get("text", ""))
                elif p.get("type") == "tool_use":
                    tool_id = p.get("id") or f"anthropic_tool_{len(tool_calls)}"
                    name = p.get("name") or ""
                    try:
                        args = __import__("json").dumps(p.get("input", {}))
                    except Exception:
                        args = str(p.get("input"))
                    tool_calls.append({
                        "id": tool_id,
                        "type": "function",
                        "function": {"name": name, "arguments": args},
                    })
        message_payload: Dict[str, Any] = {"role": "assistant", "content": None}
        content_text = "\n".join([t for t in text_parts if t]).strip()
        if content_text:
            message_payload["content"] = content_text
        if tool_calls:
            message_payload["tool_calls"] = tool_calls
        finish_reason_map = {"end_turn": "stop", "max_tokens": "length", "stop_sequence": "stop", "tool_use": "tool_calls"}
        shaped = {
            "id": data.get("id"),
            "object": "chat.completion",
            "model": data.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": message_payload,
                    "finish_reason": finish_reason_map.get(data.get("stop_reason"), data.get("stop_reason")),
                }
            ],
        }
        usage = data.get("usage") or {}
        if isinstance(usage, dict):
            shaped["usage"] = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
                "total_tokens": (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0),
            }
        return shaped

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            url = f"{self._resolve_base_url(request).rstrip('/')}/messages"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                resolved_timeout = self._resolve_timeout(request, timeout)
                with http_client_factory(timeout=resolved_timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return self._normalize_to_openai_shape(data)
            except Exception as e:
                raise self.normalize_error(e)
        # If native HTTP is explicitly disabled, raise a clear error rather than
        # delegating to legacy paths to avoid recursion and mixed behaviors.
        raise RuntimeError("AnthropicAdapter native HTTP disabled by configuration")

    def _tool_delta_chunk(self, tool_index: int, tool_id: str, tool_name: Optional[str], arguments: str) -> str:
        return sse_data({
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_calls": [{
                        "index": tool_index,
                        "id": tool_id,
                        "type": "function",
                        "function": {"name": tool_name or "", "arguments": arguments},
                    }]
                },
            }]
        })

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        if _prefer_httpx_in_tests() or os.getenv("PYTEST_CURRENT_TEST") or self._use_native_http():
            api_key = request.get("api_key")
            url = f"{self._resolve_base_url(request).rstrip('/')}/messages"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            payload["stream"] = True
            try:
                resolved_timeout = self._resolve_timeout(request, timeout)
                with http_client_factory(timeout=resolved_timeout) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as resp:
                        resp.raise_for_status()
                        tool_states: Dict[int, Dict[str, Any]] = {}
                        tool_counter = 0
                        done_sent = False
                        for raw in resp.iter_lines():
                            if not raw:
                                continue
                            if is_done_line(raw):
                                if not done_sent:
                                    done_sent = True
                                    yield sse_done()
                                continue
                            ls = raw.strip()
                            if not ls or not ls.startswith("data:"):
                                # Drop provider control lines/comments by default
                                normalized = normalize_provider_line(ls)
                                if normalized is not None:
                                    yield normalized
                                continue
                            event_data = ls[len("data:"):].strip()
                            if not event_data:
                                continue
                            try:
                                ev = __import__("json").loads(event_data)
                            except Exception:
                                continue
                            ev_type = ev.get("type")
                            if ev_type == "content_block_start":
                                cb = ev.get("content_block", {})
                                if cb.get("type") == "tool_use":
                                    idx = int(ev.get("index", 0))
                                    tool_id = cb.get("id") or f"anthropic_tool_{tool_counter}"
                                    tool_name = cb.get("name")
                                    initial_input = cb.get("input")
                                    buf = ""
                                    if initial_input is not None:
                                        try:
                                            buf = __import__("json").dumps(initial_input)
                                        except Exception:
                                            buf = str(initial_input)
                                    tool_states[idx] = {"id": tool_id, "name": tool_name, "buffer": buf, "position": tool_counter}
                                    tool_counter += 1
                                    yield self._tool_delta_chunk(tool_states[idx]["position"], tool_id, tool_name, buf)
                            elif ev_type == "content_block_delta":
                                delta = ev.get("delta", {})
                                idx = int(ev.get("index", 0))
                                dt = delta.get("type")
                                if dt == "text_delta" and "text" in delta:
                                    yield openai_delta_chunk(delta.get("text", ""))
                                elif dt == "input_json_delta" and idx in tool_states:
                                    partial = delta.get("partial_json", "")
                                    if partial:
                                        st = tool_states[idx]
                                        st["buffer"] += partial
                                        yield self._tool_delta_chunk(st["position"], st["id"], st["name"], st["buffer"])
                                elif dt == "tool_use_delta" and idx in tool_states:
                                    st = tool_states[idx]
                                    if "name" in delta and delta["name"]:
                                        st["name"] = delta["name"]
                                    if "input" in delta and delta["input"] is not None:
                                        try:
                                            st["buffer"] = __import__("json").dumps(delta["input"])
                                        except Exception:
                                            st["buffer"] = str(delta["input"])
                                    yield self._tool_delta_chunk(st["position"], st["id"], st["name"], st["buffer"])
                            elif ev_type == "message_delta":
                                stop_reason = (ev.get("delta") or {}).get("stop_reason")
                                if stop_reason:
                                    fr_map = {"end_turn": "stop", "max_tokens": "length", "stop_sequence": "stop", "tool_use": "tool_calls"}
                                    finish_reason = fr_map.get(stop_reason, stop_reason)
                                    yield sse_data({"choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]})
                        for tail in finalize_stream(response=resp, done_already=done_sent):
                            yield tail
                return
            except Exception as e:
                raise self.normalize_error(e)
        # If native HTTP is explicitly disabled, raise a clear error rather than
        # delegating to legacy paths to avoid recursion and mixed behaviors.
        raise RuntimeError("AnthropicAdapter native HTTP disabled by configuration")

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return await asyncio.to_thread(self.chat, request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        sentinel = object()
        stop_event = threading.Event()

        def _worker() -> None:
            try:
                for item in gen:
                    if stop_event.is_set():
                        break
                    loop.call_soon_threadsafe(queue.put_nowait, item)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                try:
                    if hasattr(gen, "close"):
                        gen.close()
                except Exception:
                    pass
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            stop_event.set()

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
            # Anthropic returns {"error": {"type": "...", "message": "..."}}
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
