from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List, Union

from .base import ChatProvider

from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_anthropic


class AnthropicAdapter(ChatProvider):
    name = "anthropic"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 60,
            "max_output_tokens_default": 8192,
        }

    def _to_handler_args(self, request: Dict[str, Any]) -> Dict[str, Any]:
        messages = request.get("messages") or []
        model = request.get("model")
        api_key = request.get("api_key")
        system_message = request.get("system_message")
        temperature = request.get("temperature")
        top_p = request.get("top_p")
        top_k = request.get("top_k")
        streaming_raw = request.get("stream")
        if streaming_raw is None:
            streaming_raw = request.get("streaming")

        return {
            "input_data": messages,
            "model": model,
            "api_key": api_key,
            "system_prompt": system_message,
            "temp": temperature,
            "topp": top_p,
            "topk": top_k,
            "streaming": streaming_raw,
            "max_tokens": request.get("max_tokens"),
            "stop_sequences": request.get("stop"),
            "tools": request.get("tools"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = False
        return chat_with_anthropic(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        return chat_with_anthropic(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item

