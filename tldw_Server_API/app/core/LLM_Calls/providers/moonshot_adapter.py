from __future__ import annotations

import contextlib
from collections.abc import Iterable
from typing import Any

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError, ChatProviderError
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload
from tldw_Server_API.app.core.LLM_Calls.chat_calls import (
    _parse_data_url_for_multimodal,
    _safe_cast,
)
from tldw_Server_API.app.core.LLM_Calls.error_utils import (
    get_http_error_text,
    get_http_status_from_exception,
    is_http_status_error,
    is_network_error,
    raise_chat_error_from_http,
)
from tldw_Server_API.app.core.LLM_Calls.payload_utils import (
    _sanitize_payload_for_logging,
    merge_extra_body,
    merge_extra_headers,
)
from tldw_Server_API.app.core.LLM_Calls.sse import finalize_stream
from tldw_Server_API.app.core.LLM_Calls.streaming import iter_sse_lines_requests
from tldw_Server_API.app.core.Utils.Utils import logging

from .base import ChatProvider, apply_tool_choice


def _moonshot_request(
    input_data: list[dict[str, Any]],
    model: str | None = None,
    api_key: str | None = None,
    system_message: str | None = None,
    temp: float | None = None,
    maxp: float | None = None,
    streaming: bool | None = False,
    frequency_penalty: float | None = None,
    max_tokens: int | None = None,
    n: int | None = None,
    presence_penalty: float | None = None,
    response_format: dict[str, str] | None = None,
    seed: int | None = None,
    stop: str | list[str] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    user: str | None = None,
    custom_prompt_arg: str | None = None,
    app_config: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    extra_body: dict[str, Any] | None = None,
    base_url: str | None = None,
):
    loaded_config_data = app_config or load_and_log_configs()
    moonshot_config = loaded_config_data.get("moonshot_api", {})

    final_api_key = api_key or moonshot_config.get("api_key")
    if not final_api_key:
        logging.error("Moonshot: API key is missing.")
        raise ChatConfigurationError(provider="moonshot", message="Moonshot API Key is required but not found.")

    logging.debug("Moonshot: Using configured API key")

    final_model = model if model is not None else moonshot_config.get("model", "moonshot-v1-8k")
    final_temp = temp if temp is not None else _safe_cast(moonshot_config.get("temperature"), float, 0.7)
    final_top_p = maxp if maxp is not None else _safe_cast(moonshot_config.get("top_p"), float, 0.95)

    final_n = n if n is not None else 1
    if final_n > 1 and final_temp is not None and final_temp < 0.3:
        logging.warning(f"Moonshot: n={final_n} requested but temperature={final_temp} < 0.3. Setting n=1.")
        final_n = 1

    final_streaming_cfg = moonshot_config.get("streaming", False)
    final_streaming = (
        streaming
        if streaming is not None
        else (str(final_streaming_cfg).lower() == "true" if isinstance(final_streaming_cfg, str) else bool(final_streaming_cfg))
    )

    final_max_tokens = max_tokens if max_tokens is not None else _safe_cast(moonshot_config.get("max_tokens"), int)

    if custom_prompt_arg:
        logging.warning(
            "Moonshot: 'custom_prompt_arg' was provided but is generally ignored if "
            "'input_data' and 'system_message' are used correctly."
        )

    api_messages: list[dict[str, Any]] = []
    has_system_message_in_input = any(msg.get("role") == "system" for msg in input_data)
    if system_message and not has_system_message_in_input:
        api_messages.append({"role": "system", "content": system_message})

    is_vision_model = "vision" in str(final_model).lower()
    for msg in input_data:
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, list):
            if is_vision_model:
                moonshot_content = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            moonshot_content.append(
                                {"type": "text", "text": part.get("text", "")}
                            )
                        elif part.get("type") == "image_url":
                            image_url_obj = part.get("image_url", {})
                            url_str = image_url_obj.get("url", "")
                            parsed_image = _parse_data_url_for_multimodal(url_str)
                            if parsed_image:
                                moonshot_content.append(
                                    {"type": "image_url", "image_url": {"url": url_str}}
                                )
                            else:
                                moonshot_content.append(
                                    {"type": "image_url", "image_url": {"url": url_str}}
                                )
                    elif isinstance(part, str):
                        moonshot_content.append({"type": "text", "text": part})
                api_messages.append({"role": role, "content": moonshot_content})
            else:
                text_parts = []
                has_images = False
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, dict) and part.get("type") == "image_url":
                        has_images = True
                    elif isinstance(part, str):
                        text_parts.append(part)

                if has_images and not is_vision_model:
                    logging.warning(
                        f"Moonshot: Images found in messages but model {final_model} "
                        "doesn't support vision. Images will be ignored."
                    )

                combined_text = "\n".join(text_parts)
                api_messages.append({"role": role, "content": combined_text})
        else:
            api_messages.append({"role": role, "content": content})

    payload: dict[str, Any] = {
        "model": final_model,
        "messages": api_messages,
        "stream": final_streaming,
    }

    if final_temp is not None:
        payload["temperature"] = final_temp
    if final_top_p is not None:
        payload["top_p"] = final_top_p
    if final_max_tokens is not None:
        payload["max_tokens"] = final_max_tokens
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if final_n is not None and final_n != 1:
        payload["n"] = final_n
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if response_format is not None:
        payload["response_format"] = response_format
    if seed is not None:
        payload["seed"] = seed
    if stop is not None:
        payload["stop"] = stop
    if tools is not None:
        payload["tools"] = tools
        apply_tool_choice(payload, tools, tool_choice)
    if user is not None:
        payload["user"] = user

    headers = {
        "Authorization": f"Bearer {final_api_key}",
        "Content-Type": "application/json",
    }
    headers = merge_extra_headers(headers, {"extra_headers": extra_headers})

    api_base_url = base_url or moonshot_config.get("api_base_url", "https://api.moonshot.cn/v1")
    api_url = api_base_url.rstrip("/") + "/chat/completions"

    payload = merge_extra_body(payload, {"extra_body": extra_body})
    payload_metadata = _sanitize_payload_for_logging(payload)
    logging.debug(f"Moonshot request metadata: {payload_metadata}")

    try:
        if final_streaming:
            logging.debug("Moonshot: Posting request (streaming)")
            from tldw_Server_API.app.core.LLM_Calls import chat_calls as _chat_calls
            session = _chat_calls.create_session_with_retries(
                total=_safe_cast(moonshot_config.get("api_retries"), int, 3),
                backoff_factor=_safe_cast(moonshot_config.get("api_retry_delay"), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            stream_timeout = _safe_cast(moonshot_config.get("api_timeout"), float, 90.0)
            try:
                response = session.post(api_url, headers=headers, json=payload, stream=True, timeout=stream_timeout)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            def stream_generator():
                try:
                    yield from iter_sse_lines_requests(response, decode_unicode=True, provider="moonshot")
                    yield from finalize_stream(response, done_already=False)
                finally:
                    with contextlib.suppress(Exception):
                        session.close()

            return stream_generator()

        logging.debug("Moonshot: Posting request (non-streaming)")
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _chat_calls
        session = _chat_calls.create_session_with_retries(
            total=_safe_cast(moonshot_config.get("api_retries"), int, 3),
            backoff_factor=_safe_cast(moonshot_config.get("api_retry_delay"), float, 1.0),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        try:
            response = session.post(api_url, headers=headers, json=payload, timeout=120)
            logging.debug(f"Moonshot: Full API response status: {response.status_code}")
            response.raise_for_status()
            try:
                response_data = response.json()
            finally:
                with contextlib.suppress(Exception):
                    response.close()
            logging.debug("Moonshot: Non-streaming request successful.")
            return response_data
        finally:
            with contextlib.suppress(Exception):
                session.close()

    except Exception as e:
        if is_http_status_error(e):
            status = get_http_status_from_exception(e)
            if getattr(e, "response", None) is not None:
                logging.error(f"Moonshot Full Error Response (status {status}): {get_http_error_text(e)}")
            else:
                logging.error(f"Moonshot HTTP error with no response object: {e}")
            raise_chat_error_from_http("moonshot", e)
        if is_network_error(e):
            logging.error(f"Moonshot RequestException: {e}", exc_info=True)
            raise ChatProviderError(provider="moonshot", message=f"Network error: {e}", status_code=504) from e
        logging.error(f"Moonshot: Unexpected error in chat_with_moonshot: {e}", exc_info=True)
        raise ChatProviderError(provider="moonshot", message=f"Unexpected error: {e}") from e


class MoonshotAdapter(ChatProvider):
    name = "moonshot"

    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 90,
            "max_output_tokens_default": 8192,
        }

    def _to_handler_args(self, request: dict[str, Any], *, streaming: bool | None) -> dict[str, Any]:
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
            "extra_headers": request.get("extra_headers"),
            "extra_body": request.get("extra_body"),
            "base_url": request.get("base_url"),
        }

    def chat(self, request: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        sanitized = validate_payload(self.name, request or {})
        return _moonshot_request(**self._to_handler_args(sanitized, streaming=False))

    def stream(self, request: dict[str, Any], *, timeout: float | None = None) -> Iterable[str]:
        sanitized = validate_payload(self.name, request or {})
        return _moonshot_request(**self._to_handler_args(sanitized, streaming=True))
