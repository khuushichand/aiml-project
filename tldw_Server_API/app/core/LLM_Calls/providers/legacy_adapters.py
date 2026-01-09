from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Iterable, Optional, Callable, AsyncIterator

from .base import ChatProvider
from tldw_Server_API.app.core.Chat.chat_helpers import extract_response_content
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload
from tldw_Server_API.app.core.LLM_Calls.sse import openai_delta_chunk, sse_done


class LegacyChatAdapter(ChatProvider):
    """Adapter wrapper around legacy provider callables."""

    name = "legacy"
    legacy_module: str = ""
    legacy_function: str = ""
    supports_streaming = True
    supports_tools = False
    default_timeout_seconds = 120
    max_output_tokens_default: Optional[int] = 4096

    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_streaming": bool(self.supports_streaming),
            "supports_tools": bool(self.supports_tools),
            "default_timeout_seconds": self.default_timeout_seconds,
            "max_output_tokens_default": self.max_output_tokens_default,
        }

    def _legacy_callable(self) -> Callable[..., Any]:
        module = import_module(self.legacy_module)
        return getattr(module, self.legacy_function)

    def _strip_internal(self, request: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        sanitized = dict(request or {})
        internal: Dict[str, Any] = {}
        for key in ("http_client_factory", "http_fetcher"):
            if key in sanitized:
                internal[key] = sanitized.pop(key)
        return sanitized, internal

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        raise NotImplementedError

    def _wrap_non_streaming(self, response: Any) -> Iterable[str]:
        content = extract_response_content(response)
        if content:
            yield openai_delta_chunk(content)
        yield sse_done()

    def chat(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        sanitized, internal = self._strip_internal(request or {})
        sanitized = validate_payload(self.name, sanitized)
        args = self._to_handler_args(sanitized, streaming=False)
        for key, value in internal.items():
            if value is not None:
                args[key] = value
        return self._legacy_callable()(**args)

    def stream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> Iterable[str]:
        sanitized, internal = self._strip_internal(request or {})
        sanitized = validate_payload(self.name, sanitized)
        args = self._to_handler_args(sanitized, streaming=True)
        for key, value in internal.items():
            if value is not None:
                args[key] = value
        result = self._legacy_callable()(**args)
        if not isinstance(result, (dict, str, bytes, bytearray)) and hasattr(result, "__iter__"):
            return result
        return self._wrap_non_streaming(result)

    async def astream(self, request: Dict[str, Any], *, timeout: Optional[float] = None) -> AsyncIterator[str]:
        for item in self.stream(request, timeout=timeout):
            yield item


class MoonshotAdapter(LegacyChatAdapter):
    name = "moonshot"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_chat_calls"
    legacy_function = "chat_with_moonshot"
    supports_streaming = True
    supports_tools = True

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "model": request.get("model"),
            "api_key": request.get("api_key"),
            "system_message": request.get("system_message"),
            "temp": request.get("temperature"),
            "maxp": request.get("top_p"),
            "streaming": stream_flag,
            "frequency_penalty": request.get("frequency_penalty"),
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


class ZaiAdapter(LegacyChatAdapter):
    name = "zai"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_chat_calls"
    legacy_function = "chat_with_zai"
    supports_streaming = True
    supports_tools = True

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "model": request.get("model"),
            "api_key": request.get("api_key"),
            "system_message": request.get("system_message"),
            "temp": request.get("temperature"),
            "maxp": request.get("top_p"),
            "streaming": stream_flag,
            "max_tokens": request.get("max_tokens"),
            "tools": request.get("tools"),
            "do_sample": request.get("do_sample"),
            "request_id": request.get("request_id"),
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "app_config": request.get("app_config"),
        }


class LlamaCppAdapter(LegacyChatAdapter):
    name = "llama.cpp"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_llama"
    supports_streaming = True
    supports_tools = False

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_prompt": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_k": request.get("top_k"),
            "top_p": request.get("top_p"),
            "min_p": request.get("min_p"),
            "n_predict": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "logit_bias": request.get("logit_bias"),
            "n": request.get("n"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "app_config": request.get("app_config"),
        }


class KoboldAdapter(LegacyChatAdapter):
    name = "kobold"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_kobold"
    supports_streaming = False
    supports_tools = False

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt_input": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_message": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_k": request.get("top_k"),
            "top_p": request.get("top_p"),
            "max_length": request.get("max_tokens"),
            "stop_sequence": request.get("stop"),
            "num_responses": request.get("n"),
            "seed": request.get("seed"),
            "app_config": request.get("app_config"),
        }


class OobaAdapter(LegacyChatAdapter):
    name = "ooba"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_oobabooga"
    supports_streaming = True
    supports_tools = False

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_prompt": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_k": request.get("top_k"),
            "top_p": request.get("top_p"),
            "min_p": request.get("min_p"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "user_identifier": request.get("user"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "app_config": request.get("app_config"),
        }


class TabbyAPIAdapter(LegacyChatAdapter):
    name = "tabbyapi"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_tabbyapi"
    supports_streaming = True
    supports_tools = True

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt_input": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_message": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_k": request.get("top_k"),
            "top_p": request.get("top_p"),
            "min_p": request.get("min_p"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "user_identifier": request.get("user"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "app_config": request.get("app_config"),
        }


class VLLMAdapter(LegacyChatAdapter):
    name = "vllm"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_vllm"
    supports_streaming = True
    supports_tools = True

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt_input": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_prompt": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_k": request.get("top_k"),
            "top_p": request.get("top_p"),
            "min_p": request.get("min_p"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "user_identifier": request.get("user"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "app_config": request.get("app_config"),
        }


class LocalLLMAdapter(LegacyChatAdapter):
    name = "local-llm"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_local_llm"
    supports_streaming = True
    supports_tools = True

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "custom_prompt_arg": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_message": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_k": request.get("top_k"),
            "top_p": request.get("top_p"),
            "min_p": request.get("min_p"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "user_identifier": request.get("user"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "app_config": request.get("app_config"),
        }


class OllamaAdapter(LegacyChatAdapter):
    name = "ollama"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_ollama"
    supports_streaming = True
    supports_tools = True

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_message": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_p": request.get("top_p"),
            "top_k": request.get("top_k"),
            "num_predict": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "format_str": request.get("response_format"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "user_identifier": request.get("user"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "app_config": request.get("app_config"),
        }


class AphroditeAdapter(LegacyChatAdapter):
    name = "aphrodite"
    legacy_module = "tldw_Server_API.app.core.LLM_Calls.legacy_local_calls"
    legacy_function = "chat_with_aphrodite"
    supports_streaming = True
    supports_tools = True

    def _to_handler_args(self, request: Dict[str, Any], *, streaming: Optional[bool]) -> Dict[str, Any]:
        stream_flag = request.get("stream")
        if streaming is not None:
            stream_flag = streaming
        return {
            "input_data": request.get("messages") or [],
            "api_key": request.get("api_key"),
            "custom_prompt": request.get("custom_prompt_arg"),
            "temp": request.get("temperature"),
            "system_message": request.get("system_message"),
            "streaming": stream_flag,
            "model": request.get("model"),
            "top_k": request.get("top_k"),
            "top_p": request.get("top_p"),
            "min_p": request.get("min_p"),
            "max_tokens": request.get("max_tokens"),
            "seed": request.get("seed"),
            "stop": request.get("stop"),
            "response_format": request.get("response_format"),
            "n": request.get("n"),
            "logit_bias": request.get("logit_bias"),
            "presence_penalty": request.get("presence_penalty"),
            "frequency_penalty": request.get("frequency_penalty"),
            "logprobs": request.get("logprobs"),
            "top_logprobs": request.get("top_logprobs"),
            "user_identifier": request.get("user"),
            "tools": request.get("tools"),
            "tool_choice": request.get("tool_choice"),
            "app_config": request.get("app_config"),
        }
