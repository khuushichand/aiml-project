from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator

from .base import ChatProvider


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

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        kwargs = self._to_handler_args(request)
        if "stream" in request or "streaming" in request:
            pass
        else:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        return _legacy.chat_with_deepseek(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        return _legacy.chat_with_deepseek(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
