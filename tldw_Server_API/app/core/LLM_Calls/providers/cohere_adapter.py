from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, AsyncIterator
import asyncio
import threading

from loguru import logger

from .base import ChatProvider
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload
from tldw_Server_API.app.core.LLM_Calls.legacy_chat_calls import chat_with_cohere


class CohereAdapter(ChatProvider):
    name = "cohere"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 180,
        }

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool] = None) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if stream_flag is None:
            stream_flag = request.get("streaming")
        if streaming is not None:
            stream_flag = streaming

        return {
            "input_data": request.get("messages") or [],
            "model": request.get("model"),
            "api_key": request.get("api_key"),
            "system_prompt": request.get("system_message"),
            "temp": request.get("temperature"),
            "streaming": bool(stream_flag) if stream_flag is not None else False,
            "topp": request.get("top_p"),
            "topk": request.get("top_k"),
            "max_tokens": request.get("max_tokens"),
            "stop_sequences": request.get("stop"),
            "seed": request.get("seed"),
            "num_generations": request.get("num_generations"),
            "frequency_penalty": request.get("frequency_penalty"),
            "presence_penalty": request.get("presence_penalty"),
            "tools": request.get("tools"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        request = validate_payload(self.name, request or {})
        if timeout is not None:
            logger.debug("Cohere adapter ignoring explicit timeout override.")
        return chat_with_cohere(**self._to_handler_args(request, streaming=False))

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        request = validate_payload(self.name, request or {})
        if timeout is not None:
            logger.debug("Cohere adapter ignoring explicit timeout override.")
        return chat_with_cohere(**self._to_handler_args(request, streaming=True))

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
