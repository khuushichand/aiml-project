from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator

from .base import ChatProvider


class CustomOpenAIAdapter(ChatProvider):
    name = "custom-openai-api"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 120,
            "max_output_tokens_default": 4096,
        }

    def _to_handler_args(self, request: Dict[str, Any]) -> Dict[str, Any]:
        streaming_raw = request.get("stream")
        if streaming_raw is None:
            streaming_raw = request.get("streaming")
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_message": request.get("system_message"),
            "streaming": streaming_raw,
            "model": request.get("model"),
            # Compatibility knobs
            "maxp": request.get("top_p"),
            "topp": request.get("top_p"),
            "minp": request.get("min_p"),
            "topk": request.get("top_k"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "user_identifier": request.get("user"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "app_config": request.get("app_config"),
        }

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        kwargs = self._to_handler_args(request)
        if "stream" in request or "streaming" in request:
            pass
        else:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item


class CustomOpenAIAdapter2(CustomOpenAIAdapter):
    name = "custom-openai-api-2"

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        kwargs = self._to_handler_args(request)
        if "stream" in request or "streaming" in request:
            pass
        else:
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai_2(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls_Local as _legacy_local
        return _legacy_local.chat_with_custom_openai_2(**kwargs)
