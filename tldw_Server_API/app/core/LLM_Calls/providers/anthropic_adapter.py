from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List

from .base import ChatProvider


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
        v = os.getenv("LLM_ADAPTERS_NATIVE_HTTP_ANTHROPIC")
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

    def _anthropic_base_url(self) -> str:
        import os
        return os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")

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

    def _build_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages = request.get("messages") or []
        system_message = request.get("system_message")
        payload = {
            "model": request.get("model"),
            **self._to_anthropic_messages(messages, system_message),
            "max_tokens": request.get("max_tokens") or 1024,
        }
        if request.get("temperature") is not None:
            payload["temperature"] = request.get("temperature")
        if request.get("top_p") is not None:
            payload["top_p"] = request.get("top_p")
        if request.get("top_k") is not None:
            payload["top_k"] = request.get("top_k")
        if request.get("stop") is not None:
            payload["stop_sequences"] = request.get("stop")
        return payload

    @staticmethod
    def _normalize_to_openai_shape(data: Dict[str, Any]) -> Dict[str, Any]:
        # Best-effort shaping of Anthropic message into OpenAI-like response
        if data and isinstance(data, dict) and data.get("type") == "message":
            content = data.get("content")
            text = None
            if isinstance(content, list) and content:
                first = content[0] or {}
                text = first.get("text") if isinstance(first, dict) else None
            shaped = {
                "id": data.get("id"),
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": data.get("stop_reason") or "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": data.get("usage", {}).get("input_tokens"),
                    "completion_tokens": data.get("usage", {}).get("output_tokens"),
                    "total_tokens": None,
                },
            }
            try:
                shaped["usage"]["total_tokens"] = (shaped["usage"].get("prompt_tokens") or 0) + (shaped["usage"].get("completion_tokens") or 0)
            except Exception:
                pass
            return shaped
        return data

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        if self._use_native_http():
            try:
                import httpx
            except Exception as e:  # pragma: no cover
                raise self.normalize_error(e)
            api_key = request.get("api_key")
            url = f"{self._anthropic_base_url().rstrip('/')}/messages"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                with httpx.Client(timeout=timeout or 60.0) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return self._normalize_to_openai_shape(data)
            except Exception as e:
                raise self.normalize_error(e)

        # Delegate to legacy for parity when native HTTP is disabled
        import os
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        streaming_raw = request.get("stream") if "stream" in request else request.get("streaming")
        kwargs = {
            "input_data": request.get("messages") or [],
            "model": request.get("model"),
            "api_key": request.get("api_key"),
            "system_prompt": request.get("system_message"),
            "temp": request.get("temperature"),
            "topp": request.get("top_p"),
            "topk": request.get("top_k"),
            "streaming": streaming_raw if streaming_raw is not None else False,
            "max_tokens": request.get("max_tokens"),
            "stop_sequences": request.get("stop"),
            "tools": request.get("tools"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }
        if os.getenv("TEST_MODE") and os.getenv("TEST_MODE").lower() in {"1", "true", "yes", "on"}:
            return _legacy.chat_with_anthropic(**kwargs)
        return _legacy.legacy_chat_with_anthropic(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        if self._use_native_http():
            try:
                import httpx
            except Exception as e:  # pragma: no cover
                raise self.normalize_error(e)
            api_key = request.get("api_key")
            url = f"{self._anthropic_base_url().rstrip('/')}/messages"
            headers = self._headers(api_key)
            payload = self._build_payload(request)
            payload["stream"] = True

            def _gen() -> Iterable[str]:
                try:
                    with httpx.Client(timeout=timeout or 60.0) as client:
                        with client.stream("POST", url, json=payload, headers=headers) as resp:
                            resp.raise_for_status()
                            for line in resp.iter_lines():
                                if not line:
                                    continue
                                yield f"{line}\n\n"
                except Exception as e:
                    raise self.normalize_error(e)

            return _gen()

        import os
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        kwargs = {
            **{
                "input_data": request.get("messages") or [],
                "model": request.get("model"),
                "api_key": request.get("api_key"),
                "system_prompt": request.get("system_message"),
                "temp": request.get("temperature"),
                "topp": request.get("top_p"),
                "topk": request.get("top_k"),
                "max_tokens": request.get("max_tokens"),
                "stop_sequences": request.get("stop"),
                "tools": request.get("tools"),
                "custom_prompt_arg": request.get("custom_prompt_arg"),
                "app_config": request.get("app_config"),
            }
        }
        kwargs["streaming"] = True
        if os.getenv("TEST_MODE") and os.getenv("TEST_MODE").lower() in {"1", "true", "yes", "on"}:
            return _legacy.chat_with_anthropic(**kwargs)
        return _legacy.legacy_chat_with_anthropic(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
