from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List

from .base import ChatProvider


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
        import os
        v = os.getenv("LLM_ADAPTERS_NATIVE_HTTP_GROQ")
        return bool(v and v.lower() in {"1", "true", "yes", "on"})

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
        if request.get("tools") is not None:
            payload["tools"] = request.get("tools")
        if request.get("tool_choice") is not None:
            payload["tool_choice"] = request.get("tool_choice")
        if request.get("response_format") is not None:
            payload["response_format"] = request.get("response_format")
        if request.get("seed") is not None:
            payload["seed"] = request.get("seed")
        if request.get("stop") is not None:
            payload["stop"] = request.get("stop")
        return payload

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        if self._use_native_http():
            try:
                import httpx
            except Exception as e:  # pragma: no cover
                raise self.normalize_error(e)
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            url = f"{self._base_url().rstrip('/')}/chat/completions"
            payload = self._build_payload(request)
            payload["stream"] = False
            try:
                with httpx.Client(timeout=timeout or 60.0) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                raise self.normalize_error(e)

        # Legacy delegate
        import os
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        streaming_raw = request.get("stream") if "stream" in request else request.get("streaming")
        kwargs = {
            "input_data": request.get("messages") or [],
            "model": request.get("model"),
            "api_key": request.get("api_key"),
            "system_message": request.get("system_message"),
            "temp": request.get("temperature"),
            "maxp": request.get("top_p"),
            "streaming": streaming_raw if streaming_raw is not None else False,
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
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
        if os.getenv("TEST_MODE") and os.getenv("TEST_MODE").lower() in {"1", "true", "yes", "on"}:
            return _legacy.chat_with_groq(**kwargs)
        return _legacy.legacy_chat_with_groq(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        if self._use_native_http():
            try:
                import httpx
            except Exception as e:  # pragma: no cover
                raise self.normalize_error(e)
            api_key = request.get("api_key")
            headers = self._headers(api_key)
            url = f"{self._base_url().rstrip('/')}/chat/completions"
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
        kwargs = self._build_payload(request)
        # map to legacy kwargs
        kwargs = {
            "input_data": request.get("messages") or [],
            "model": request.get("model"),
            "api_key": request.get("api_key"),
            "system_message": request.get("system_message"),
            "temp": request.get("temperature"),
            "maxp": request.get("top_p"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
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
            "streaming": True,
        }
        if os.getenv("TEST_MODE") and os.getenv("TEST_MODE").lower() in {"1", "true", "yes", "on"}:
            return _legacy.chat_with_groq(**kwargs)
        return _legacy.legacy_chat_with_groq(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
