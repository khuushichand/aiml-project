from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator

from .base import ChatProvider

import os
from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as _legacy


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

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = False
        if os.getenv("TEST_MODE") and os.getenv("TEST_MODE").lower() in {"1", "true", "yes", "on"}:
            return _legacy.chat_with_google(**kwargs)
        return _legacy.legacy_chat_with_google(**kwargs)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        kwargs = self._to_handler_args(request)
        kwargs["streaming"] = True
        if os.getenv("TEST_MODE") and os.getenv("TEST_MODE").lower() in {"1", "true", "yes", "on"}:
            return _legacy.chat_with_google(**kwargs)
        return _legacy.legacy_chat_with_google(**kwargs)

    async def achat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        return self.chat(request, timeout=timeout)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        gen = self.stream(request, timeout=timeout)
        for item in gen:
            yield item
