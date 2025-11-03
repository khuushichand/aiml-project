from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator, List, Union

from loguru import logger

from .base import ChatProvider

# Reuse the existing, stable implementation to ensure behavior parity during migration
# Do not import legacy handler at module import time to keep tests patchable.
# Resolve the function from the module at call time so monkeypatching
# tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.chat_with_openai works.


class OpenAIAdapter(ChatProvider):
    name = "openai"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 60,
            "max_output_tokens_default": 4096,
        }

    def _to_handler_args(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Translate OpenAI-like request dict to chat_with_openai kwargs."""
        messages = request.get("messages") or []
        model = request.get("model")
        api_key = request.get("api_key")
        system_message = request.get("system_message")
        temperature = request.get("temperature")
        top_p = request.get("top_p")
        # Preserve None to allow legacy default-from-config behavior
        streaming_raw = request.get("stream")
        if streaming_raw is None:
            streaming_raw = request.get("streaming")

        args: Dict[str, Any] = {
            "input_data": messages,
            "model": model,
            "api_key": api_key,
            "system_message": system_message,
            "temp": temperature,
            "maxp": top_p,
            "streaming": streaming_raw,
            "frequency_penalty": request.get("frequency_penalty"),
            "logit_bias": request.get("logit_bias"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "max_tokens": request.get("max_tokens"),
            "n": request.get("n"),
            "presence_penalty": request.get("presence_penalty"),
            "response_format": request.get("response_format"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "user": request.get("user"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }
        return args

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        kwargs = self._to_handler_args(request)
        # Preserve None to allow legacy default-from-config behavior when caller
        # does not explicitly choose streaming vs. non-streaming.
        # Only coerce when an explicit boolean was provided in the request.
        if "stream" in request or "streaming" in request:
            # Respect explicit caller intent
            streaming_raw = request.get("stream")
            if streaming_raw is None:
                streaming_raw = request.get("streaming")
            kwargs["streaming"] = streaming_raw
        else:
            # Explicitly pass None so legacy handler can read config default
            kwargs["streaming"] = None
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        return _legacy.chat_with_openai(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy
        return _legacy.chat_with_openai(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        # Fallback to sync path for now to preserve behavior; future: call native async if available
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        # Wrap sync generator into async iterator for compatibility
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
