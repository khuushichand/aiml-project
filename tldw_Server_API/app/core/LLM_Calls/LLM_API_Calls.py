"""
LLM_API_Calls
General LLM API calling library for commercial providers.

This module implements provider-specific chat/embeddings calls while returning
OpenAI-compatible request/response formats whenever feasible. Streaming
responses are normalized to Server-Sent Events (SSE) semantics: lines prefixed
with "data: " and separated by a blank line. Provider errors are mapped to
ChatAPIError subclasses so FastAPI endpoints can return appropriate status
codes without leaking internal exceptions.

Notes
- Avoid logging secrets; this module only logs high-level metadata.
- Timeouts and retries are per-provider configurable via config.
- Use environment variables to override base URLs for testing/mocking.
"""
#########################################
# General LLM API Calling Library
# This library is used to perform API Calls against commercial LLM endpoints.
#
####
####################
# Function List
#
# 1. extract_text_from_segments(segments: List[Dict]) -> str
# 2. chat_with_openai(api_key, file_path, custom_prompt_arg, streaming=None)
# 3. chat_with_anthropic(api_key, file_path, model, custom_prompt_arg, max_retries=3, retry_delay=5, streaming=None)
# 4. chat_with_cohere(api_key, file_path, model, custom_prompt_arg, streaming=None)
# 5. chat_with_qwen(api_key, input_data, custom_prompt_arg, system_prompt=None, streaming=None)
# 6. chat_with_groq(api_key, input_data, custom_prompt_arg, system_prompt=None, streaming=None)
# 7. chat_with_openrouter(api_key, input_data, custom_prompt_arg, system_prompt=None, streaming=None)
# 8. chat_with_huggingface(api_key, input_data, custom_prompt_arg, system_prompt=None, streaming=None)
# 9. chat_with_deepseek(api_key, input_data, custom_prompt_arg, system_prompt=None, streaming=None)
#
#
####################
#
# Import necessary libraries
import asyncio
import json
import os
import time
from typing import List, Any, Optional, Tuple, Dict, Union, Iterable
#
# Import 3rd-Party Libraries
import requests
import httpx

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAPIError
#
# Import Local libraries
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.Utils.Utils import logging
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAuthenticationError, ChatRateLimitError, \
    ChatBadRequestError, ChatProviderError, ChatConfigurationError
from tldw_Server_API.app.core.LLM_Calls.sse import (
    finalize_stream,
    ensure_sse_line,
    is_done_line,
    normalize_provider_line,
    openai_delta_chunk,
    sse_data,
    sse_done,
)
from tldw_Server_API.app.core.LLM_Calls.http_helpers import create_session_with_retries
from tldw_Server_API.app.core.LLM_Calls.streaming import (
    iter_sse_lines_requests,
    aiter_sse_lines_httpx,
)
#
# Shared helper for consistent tool_choice gating across providers
def _apply_tool_choice(payload: Dict[str, Any], tools: Optional[List[Dict[str, Any]]], tool_choice: Optional[Union[str, Dict[str, Any]]]) -> None:
    """Set tool_choice in payload only when supported.

    - Always allow "none" to disable tools explicitly.
    - Otherwise include tool_choice only when tools are present.
    """
    try:
        if tool_choice == "none":
            payload["tool_choice"] = "none"
        elif tool_choice is not None and tools:
            payload["tool_choice"] = tool_choice
    except Exception:
        # Never break the call due to helper failure
        pass
#
#######################################################################################################################
# Function Definitions
#

# FIXME: Update to include full arguments

# --- Helper function for safe type conversion ---
def _safe_cast(value: Any, cast_to: type, default: Any = None) -> Any:
    """Safely casts value to specified type, returning default on failure."""
    if value is None:
        return default
    try:
        return cast_to(value)
    except (ValueError, TypeError):
        logging.warning(f"Could not cast '{value}' to {cast_to}. Using default: {default}")
        return default


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _resolve_openai_api_base(openai_cfg: Dict[str, Any]) -> str:
    """Resolve the OpenAI API base URL.

    Precedence: config keys (api_base_url, api_base, base_url),
    then environment vars (OPENAI_API_BASE_URL, OPENAI_API_BASE, OPENAI_BASE_URL, MOCK_OPENAI_BASE_URL),
    then default 'https://api.openai.com/v1'.
    """
    try:
        cfg_base = (
            openai_cfg.get('api_base_url')
            or openai_cfg.get('api_base')
            or openai_cfg.get('base_url')
        )
    except Exception:
        cfg_base = None

    env_api_base = (
        os.getenv('OPENAI_API_BASE_URL')
        or os.getenv('OPENAI_API_BASE')
        or os.getenv('OPENAI_BASE_URL')
        or os.getenv('MOCK_OPENAI_BASE_URL')
    )
    return (cfg_base or env_api_base or 'https://api.openai.com/v1')


async def _async_retry_sleep(base_delay: float, attempt: int) -> None:
    """Async sleep helper applying linear backoff per attempt (1-indexed)."""
    delay = base_delay * (attempt + 1)
    if delay > 0:
        await asyncio.sleep(delay)


def _is_retryable_status(status_code: Optional[int]) -> bool:
    return status_code in _RETRYABLE_STATUS_CODES


def _summarize_message_content(content: Any) -> Tuple[int, bool]:
    """Return (text_char_count, has_attachments) for a message content payload."""
    text_chars = 0
    has_attachments = False

    if content is None:
        return text_chars, has_attachments

    if isinstance(content, str):
        return len(content), has_attachments

    if isinstance(content, dict):
        # Handle single-part dicts (e.g., Gemini parts or Cohere history entries)
        possible_text = content.get("text") or content.get("message")
        if isinstance(possible_text, str):
            text_chars += len(possible_text)
        if any(key in content for key in ("image_url", "inline_data", "data", "file_id")):
            has_attachments = True
        if "parts" in content:
            extra_chars, extra_attach = _summarize_message_content(content.get("parts"))
            text_chars += extra_chars
            has_attachments = has_attachments or extra_attach
        return text_chars, has_attachments

    if isinstance(content, (list, tuple)):
        for part in content:
            if isinstance(part, dict):
                part_type = (part.get("type") or "").lower()
                if part_type in {"text", "input_text"} and isinstance(part.get("text"), str):
                    text_chars += len(part.get("text") or "")
                elif part_type in {"image_url", "input_image", "image"}:
                    has_attachments = True
                elif part_type in {"tool_use"}:
                    continue
                if "inline_data" in part or "image_url" in part:
                    has_attachments = True
                if "functionCall" in part and isinstance(part.get("functionCall", {}).get("args"), str):
                    text_chars += len(part["functionCall"]["args"])
            elif isinstance(part, str):
                text_chars += len(part)
    return text_chars, has_attachments


def _summarize_messages(messages: Any, key: str) -> Dict[str, Any]:
    """Summarize a messages-like payload without logging raw content."""
    if messages is None:
        return {f"{key}_count": 0, f"{key}_text_chars": 0}

    if not isinstance(messages, list):
        messages_iterable = [messages]
    else:
        messages_iterable = messages

    role_counts: Dict[str, int] = {}
    total_text_chars = 0
    has_attachments = False

    for entry in messages_iterable:
        if isinstance(entry, dict):
            role = entry.get("role")
            if isinstance(role, str):
                role_counts[role] = role_counts.get(role, 0) + 1
            entry_content = None
            if "content" in entry:
                entry_content = entry.get("content")
            elif "parts" in entry:
                entry_content = entry.get("parts")
            elif "message" in entry:
                entry_content = entry.get("message")
            elif "text" in entry:
                entry_content = entry.get("text")
            text_chars, attachments = _summarize_message_content(entry_content)
            total_text_chars += text_chars
            has_attachments = has_attachments or attachments
        elif isinstance(entry, str):
            total_text_chars += len(entry)

    summary: Dict[str, Any] = {
        f"{key}_count": len(messages_iterable),
        f"{key}_text_chars": total_text_chars,
    }
    if role_counts:
        summary[f"{key}_roles"] = role_counts
    if has_attachments:
        summary[f"{key}_has_attachments"] = True
    return summary


def _summarize_dict_field(key: str, value: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize dict values without exposing raw content."""
    if key == "response_format":
        summary: Dict[str, Any] = {f"{key}_keys_count": len(value)}
        response_type = value.get("type")
        if isinstance(response_type, str):
            summary["response_format_type"] = response_type
        return summary

    if key == "generationConfig":
        summary = {f"{key}_keys_count": len(value)}
        for numeric_key in ("temperature", "topP", "topK", "maxOutputTokens", "candidateCount"):
            numeric_val = value.get(numeric_key)
            if isinstance(numeric_val, (int, float)):
                summary[f"{key}_{numeric_key}"] = numeric_val
        if isinstance(value.get("responseMimeType"), str):
            summary["response_mime_type"] = value["responseMimeType"]
        if isinstance(value.get("stopSequences"), (list, tuple)):
            summary[f"{key}_stop_sequences_count"] = len(value["stopSequences"])
        return summary

    if key == "logit_bias":
        return {f"{key}_size": len(value)}

    if key == "system_instruction":
        parts = value.get("parts")
        text_chars, attachments = _summarize_message_content(parts)
        summary = {
            f"{key}_parts_count": len(parts or []),
            f"{key}_text_chars": text_chars,
        }
        if attachments:
            summary[f"{key}_has_attachments"] = True
        return summary

    return {f"{key}_keys_count": len(value)}


def _summarize_list_field(key: str, value: Iterable[Any]) -> Dict[str, Any]:
    """Summarize list/tuple values."""
    items = list(value)
    summary: Dict[str, Any] = {f"{key}_count": len(items)}
    if key in {"stop", "stop_sequences", "stopSequences"}:
        summary[f"{key}_total_chars"] = sum(len(item) for item in items if isinstance(item, str))
    return summary


def _sanitize_payload_for_logging(
        payload: Optional[Dict[str, Any]],
        *,
        message_keys: Tuple[str, ...] = ("messages",),
        text_keys: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """Build a metadata dict safe for logging, omitting raw prompts or filenames."""
    if not isinstance(payload, dict):
        return {}

    metadata: Dict[str, Any] = {}

    model = payload.get("model")
    if isinstance(model, str):
        metadata["model"] = model

    if "stream" in payload:
        metadata["stream"] = bool(payload.get("stream"))

    for key in message_keys:
        if key in payload:
            metadata.update(_summarize_messages(payload.get(key), key))

    for key, value in payload.items():
        if key in message_keys or key in {"model", "stream"}:
            continue
        if value is None:
            continue
        if isinstance(value, (int, float, bool)):
            metadata[key] = value
        elif isinstance(value, str):
            if key in text_keys or key in {"stop"}:
                metadata[f"{key}_chars"] = len(value)
            elif key in {"tool_choice"}:
                metadata[key] = value
            else:
                metadata[f"{key}_present"] = True
        elif isinstance(value, dict):
            metadata.update(_summarize_dict_field(key, value))
        elif isinstance(value, (list, tuple, set)):
            metadata.update(_summarize_list_field(key, value))
        else:
            metadata[f"{key}_present"] = True

    return metadata

def extract_text_from_segments(segments):
    logging.debug(f"Segments received: {segments}")
    logging.debug(f"Type of segments: {type(segments)}")

    text = ""

    if isinstance(segments, list):
        for segment in segments:
            logging.debug(f"Current segment: {segment}")
            logging.debug(f"Type of segment: {type(segment)}")
            if 'Text' in segment:
                text += segment['Text'] + " "
            else:
                logging.warning(f"Skipping segment due to missing 'Text' key: {segment}")
    else:
        logging.warning(f"Unexpected type of 'segments': {type(segments)}")

    return text.strip()


def _parse_data_url_for_multimodal(data_url: str) -> Optional[Tuple[str, str]]:
    """Parses a data URL (e.g., data:image/png;base64,xxxx) into (mime_type, base64_data)."""
    if data_url.startswith("data:") and ";base64," in data_url:
        try:
            header, b64_data = data_url.split(";base64,", 1)
            mime_type = header.split("data:", 1)[1]
            return mime_type, b64_data
        except Exception as e:
            logging.warning(f"Could not parse data URL: {data_url[:60]}... Error: {e}")
            return None
    logging.debug(f"Data URL did not match expected format: {data_url[:60]}...")
    return None


def _anthropic_image_source_from_part(image_url_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build an Anthropic-compatible image source from an OpenAI-style image_url part.

    Supports both base64 data URLs and remote HTTP(S) URLs.
    """
    url_str = (image_url_obj or {}).get("url", "")
    if not url_str:
        return None
    parsed = _parse_data_url_for_multimodal(url_str)
    if parsed:
        mime_type, b64_data = parsed
        return {"type": "base64", "media_type": mime_type, "data": b64_data}
    if url_str.startswith(("http://", "https://")):
        return {"type": "url", "url": url_str}
    logging.warning(f"Anthropic: Unsupported image URL format; skipping: {url_str[:60]}...")
    return None


def _anthropic_tool_delta_chunk(
        tool_index: int,
        tool_id: str,
        tool_name: Optional[str],
        arguments: str,
) -> str:
    """Return an SSE chunk containing an OpenAI-compatible tool_call delta."""
    return sse_data({
        "choices": [{
            "index": 0,
            "delta": {
                "tool_calls": [{
                    "index": tool_index,
                    "id": tool_id,
                    "type": "function",
                    "function": {
                        "name": tool_name or "",
                        "arguments": arguments,
                    },
                }]
            }
        }]
    })


def _normalize_anthropic_response(response_data: Dict[str, Any], model_name: Optional[str]) -> Dict[str, Any]:
    """
    Convert Anthropic's Messages API response into an OpenAI-compatible chat completion response.
    """
    assistant_text_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    for part in response_data.get("content", []):
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            assistant_text_parts.append(part.get("text", ""))
        elif part.get("type") == "tool_use":
            tool_id = part.get("id") or f"anthropic_tool_{len(tool_calls)}"
            tool_calls.append({
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": part.get("name") or "",
                    "arguments": json.dumps(part.get("input", {})),
                }
            })

    message_content = "\n".join(assistant_text_parts).strip()
    message_payload: Dict[str, Any] = {"role": "assistant", "content": message_content if message_content else None}
    if tool_calls:
        message_payload["tool_calls"] = tool_calls
        if not message_content:
            message_payload["content"] = None

    finish_reason_map = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    finish_reason = finish_reason_map.get(response_data.get("stop_reason"), response_data.get("stop_reason"))

    normalized: Dict[str, Any] = {
        "id": response_data.get("id", f"anthropic-{time.time_ns()}"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": response_data.get("model", model_name),
        "choices": [{
            "index": 0,
            "message": message_payload,
            "finish_reason": finish_reason,
        }],
    }
    usage = response_data.get("usage")
    if usage:
        normalized["usage"] = usage
    return normalized


def _raise_chat_error_from_http(provider: str, error: requests.exceptions.HTTPError) -> None:
    """Normalize requests HTTPError into project ChatAPIError subclasses."""
    status_code: Optional[int] = None
    message: str = ""
    response = getattr(error, "response", None)

    if response is not None:
        status_code = getattr(response, "status_code", None)
        try:
            response_text = repr(response.text)
        except Exception:
            response_text = "<unable to read response text>"
        logging.error(f"{provider.capitalize()} HTTP error response (status {status_code}): {response_text}")
        try:
            err_json = response.json()
            message = err_json.get("error", {}).get("message") or err_json.get("message") or response.text or str(error)
        except Exception:
            message = response.text or str(error)
    else:
        logging.error(f"{provider.capitalize()} HTTPError with no response payload: {error}")
        message = str(error)

    if not message:
        message = f"{provider} API error"

    if status_code in (400, 404, 422):
        raise ChatBadRequestError(provider=provider, message=message)
    if status_code in (401, 403):
        raise ChatAuthenticationError(provider=provider, message=message)
    if status_code == 429:
        raise ChatRateLimitError(provider=provider, message=message)
    if status_code and 500 <= status_code < 600:
        raise ChatProviderError(provider=provider, message=message, status_code=status_code)

    raise ChatAPIError(provider=provider, message=message, status_code=status_code or 500)


def _raise_httpx_chat_error(provider: str, error: httpx.HTTPStatusError) -> None:
    """Normalize httpx HTTPStatusError into project ChatAPIError subclasses."""
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    text = None
    try:
        text = response.text if response is not None else str(error)
    except Exception:
        text = str(error)

    if status_code in (400, 404, 422):
        raise ChatBadRequestError(provider=provider, message=text)
    if status_code in (401, 403):
        raise ChatAuthenticationError(provider=provider, message=text)
    if status_code == 429:
        raise ChatRateLimitError(provider=provider, message=text)
    if status_code and 500 <= status_code < 600:
        raise ChatProviderError(provider=provider, message=text, status_code=status_code)
    raise ChatAPIError(provider=provider, message=text, status_code=status_code or 500)


def get_openai_embeddings(input_data: str, model: str, app_config: Optional[Dict[str, Any]] = None) -> List[float]:
    """
    Get embeddings for a single input text from OpenAI API.
    Args:
        input_data (str): The input text to get embeddings for.
        model (str): The model to use for generating embeddings.
        app_config (Optional[Dict[str, Any]]): Pre-loaded application configuration.
                                               If None, config will be loaded internally.
    Returns:
        List[float]: The embeddings generated by the API.
    """
    api_key = None
    openai_cfg: Dict[str, Any] = {}
    if app_config:
        # Preferred: explicit openai_api section
        openai_cfg = (app_config.get('openai_api') or {})
        api_key = openai_cfg.get('api_key')
        # Fallback: embedding_config holds per-model API keys
        if not api_key:
            try:
                emb_cfg = app_config.get('embedding_config') or {}
                models = emb_cfg.get('models') or {}
                model_spec = models.get(model)
                if model_spec is not None:
                    # Pydantic model or dict-like
                    api_key = getattr(model_spec, 'api_key', None) or (
                        model_spec.get('api_key') if isinstance(model_spec, dict) else None
                    )
            except Exception:
                api_key = None
    else:
        loaded_config_data = load_and_log_configs()
        openai_cfg = loaded_config_data.get('openai_api', {})
        api_key = openai_cfg.get('api_key')

    if not api_key:
        logging.error("OpenAI Embeddings (single): API key not found or is empty")
        raise ValueError("OpenAI Embeddings (single): API Key Not Provided/Found or is empty")

    logging.debug("OpenAI Embeddings (single): Using configured API key")
    logging.debug(
        f"OpenAI Embeddings (single): input length={len(str(input_data)) if input_data is not None else 0} chars"
    )
    logging.debug(f"OpenAI Embeddings (single): Using model: {model}")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    request_data = {
        "input": input_data,
        "model": model,
    }
    # Resolve OpenAI API base URL using shared helper
    api_base = _resolve_openai_api_base(openai_cfg)
    api_url = api_base.rstrip('/') + '/embeddings'
    try:
        logging.debug(f"OpenAI Embeddings (single): Posting request to embeddings API at {api_url}")
        session = create_session_with_retries(
            total=_safe_cast(openai_cfg.get('api_retries'), int, 3),
            backoff_factor=_safe_cast(openai_cfg.get('api_retry_delay'), float, 1.0),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        timeout = _safe_cast(openai_cfg.get('api_timeout'), float, 90.0)
        try:
            response = session.post(api_url, headers=headers, json=request_data, timeout=timeout)
            logging.debug(f"OpenAI Embeddings (single): API response status: {response.status_code}")

            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

            response_data = response.json()
            if 'data' in response_data and len(response_data['data']) > 0 and 'embedding' in response_data['data'][0]:
                embedding = response_data['data'][0]['embedding']
                logging.debug("OpenAI Embeddings (single): Embedding retrieved successfully")
                return embedding
            else:
                logging.warning(
                    f"OpenAI Embeddings (single): Embedding data not found or malformed in response: {response_data}")
                raise ValueError("OpenAI Embeddings (single): Embedding data not available or malformed in the response")
        finally:
            session.close()
    except requests.exceptions.HTTPError as e:
        logging.error(
            f"OpenAI Embeddings (single): HTTP request failed with status {e.response.status_code}, Response: {e.response.text}",
            exc_info=True)
        raise  # Re-raise the HTTPError to be potentially caught by retry logic
    except requests.exceptions.RequestException as e:
        logging.error(f"OpenAI Embeddings (single): Error making API request: {str(e)}", exc_info=True)
        raise ValueError(
            f"OpenAI Embeddings (single): Error making API request: {str(e)}")  # Wrap for consistent error type if preferred
    except Exception as e:
        logging.error(f"OpenAI Embeddings (single): Unexpected error: {str(e)}", exc_info=True)
        raise ValueError(f"OpenAI Embeddings (single): Unexpected error occurred: {str(e)}")


# NEW BATCH FUNCTION
def get_openai_embeddings_batch(texts: List[str], model: str, app_config: Optional[Dict[str, Any]] = None) -> List[
    List[float]]:
    """
    Get embeddings for a batch of input texts from OpenAI API in a single call.
    Args:
        texts (List[str]): The list of input texts to get embeddings for.
        model (str): The model to use for generating embeddings.
        app_config (Optional[Dict[str, Any]]): Pre-loaded application configuration.
                                               If None, config will be loaded internally.
    Returns:
        List[List[float]]: A list of embeddings, corresponding to the input texts.
    """
    if not texts:
        return []

    openai_cfg: Dict[str, Any] = {}
    if app_config:
        openai_cfg = app_config.get('openai_api', {}) or {}
        api_key = openai_cfg.get('api_key')
    else:
        # Fallback to loading config internally if not provided
        loaded_config_data = load_and_log_configs()
        openai_cfg = loaded_config_data.get('openai_api', {})
        api_key = openai_cfg.get('api_key')

    if not api_key:
        logging.error("OpenAI Embeddings (batch): API key not found or is empty")
        raise ValueError("OpenAI Embeddings (batch): API Key Not Provided/Found or is empty")

    logging.debug(f"OpenAI Embeddings (batch): Processing {len(texts)} texts.")
    logging.debug("OpenAI Embeddings (batch): Using configured API key")
    logging.debug(f"OpenAI Embeddings (batch): Using model: {model}")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    # OpenAI API expects a list of strings for the "input" field for batching
    request_data = {
        "input": texts,
        "model": model,
    }
    # Resolve OpenAI API base URL using shared helper
    api_base = _resolve_openai_api_base(openai_cfg)
    api_url = api_base.rstrip('/') + '/embeddings'
    try:
        logging.debug(f"OpenAI Embeddings (batch): Posting batch request of {len(texts)} items to API: {api_url}")
        session = create_session_with_retries(
            total=_safe_cast(openai_cfg.get('api_retries'), int, 3),
            backoff_factor=_safe_cast(openai_cfg.get('api_retry_delay'), float, 1.0),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        timeout = _safe_cast(openai_cfg.get('api_timeout'), float, 90.0)
        try:
            response = session.post(api_url, headers=headers, json=request_data, timeout=timeout)
            logging.debug(f"OpenAI Embeddings (batch): API response status: {response.status_code}")

            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

            response_data = response.json()

            if 'data' in response_data and isinstance(response_data['data'], list):
                # Ensure the number of embeddings matches the number of input texts
                if len(response_data['data']) != len(texts):
                    logging.error(
                        f"OpenAI Embeddings (batch): Mismatch in count. Input: {len(texts)}, Output: {len(response_data['data'])}")
                    raise ValueError(
                        "OpenAI Embeddings (batch): API returned a different number of embeddings than texts provided.")

                embeddings_list = []
                for item in response_data['data']:
                    if 'embedding' in item and isinstance(item['embedding'], list):
                        embeddings_list.append(item['embedding'])
                    else:
                        logging.error(f"OpenAI Embeddings (batch): Malformed embedding item in response: {item}")
                        raise ValueError("OpenAI Embeddings (batch): API response contained malformed embedding data.")

                logging.debug(f"OpenAI Embeddings (batch): {len(embeddings_list)} embeddings retrieved successfully.")
                return embeddings_list
            else:
                logging.warning(
                    f"OpenAI Embeddings (batch): 'data' field not found or not a list in response: {response_data}")
                raise ValueError("OpenAI Embeddings (batch): 'data' field not available or malformed in the API response.")
        finally:
            session.close()

    except requests.exceptions.HTTPError as e:
        # Log the detailed error including the response text for better debugging
        error_message = f"OpenAI Embeddings (batch): HTTP request failed with status {e.response.status_code}."
        try:
            error_body = e.response.json()  # Try to parse JSON error from OpenAI
            error_message += f" Error details: {error_body.get('error', {}).get('message', e.response.text)}"
        except ValueError:  # If response is not JSON
            error_message += f" Response: {e.response.text}"
        logging.error(error_message, exc_info=True)
        raise  # Re-raise the HTTPError
    except requests.exceptions.RequestException as e:
        # Propagate request exceptions so upstream retry logic can handle transient failures
        logging.error(f"OpenAI Embeddings (batch): RequestException: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"OpenAI Embeddings (batch): Unexpected error: {str(e)}", exc_info=True)
        raise ValueError(f"OpenAI Embeddings (batch): Unexpected error occurred: {str(e)}")


def chat_with_openai(
        input_data: List[Dict[str, Any]],  # Mapped from 'messages_payload'
        model: Optional[str] = None,  # Mapped from 'model'
        api_key: Optional[str] = None,  # Mapped from 'api_key'
        system_message: Optional[str] = None,  # Mapped from 'system_message'
        temp: Optional[float] = None,  # Mapped from 'temp' (temperature)
        maxp: Optional[float] = None,  # Mapped from 'maxp' (top_p)
        streaming: Optional[bool] = False,  # Mapped from 'streaming'
        # New OpenAI specific parameters (and some from original ChatCompletionRequest schema)
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        logprobs: Optional[bool] = None,  # True/False
        top_logprobs: Optional[int] = None,
        max_tokens: Optional[int] = None,  # This was already implicitly handled by config, now explicit
        n: Optional[int] = None,  # Number of completions
        presence_penalty: Optional[float] = None,
        response_format: Optional[Dict[str, str]] = None,  # e.g., {"type": "json_object"}
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        user: Optional[str] = None, # This is the 'user_identifier' mapped
        custom_prompt_arg: Optional[str] = None, # Legacy
        app_config: Optional[Dict[str, Any]] = None,
):
    """
    Sends a chat completion request to the OpenAI API.

    Args:
        input_data: List of message objects (OpenAI format).
        model: ID of the model to use.
        api_key: OpenAI API key.
        system_message: Optional system message to prepend.
        temp: Sampling temperature.
        maxp: Top-p (nucleus) sampling parameter.
        streaming: Whether to stream the response.
        frequency_penalty: Penalizes new tokens based on their existing frequency.
        logit_bias: Modifies the likelihood of specified tokens appearing.
        logprobs: Whether to return log probabilities of output tokens.
        top_logprobs: An integer between 0 and 5 specifying the number of most likely tokens to return at each token position.
        max_tokens: Maximum number of tokens to generate.
        n: How many chat completion choices to generate for each input message.
        presence_penalty: Penalizes new tokens based on whether they appear in the text so far.
        response_format: An object specifying the format that the model must output. e.g. {"type": "json_object"}.
        seed: This feature is in Beta. If specified, the system will make a best effort to sample deterministically.
        stop: Up to 4 sequences where the API will stop generating further tokens.
        tools: A list of tools the model may call.
        tool_choice: Controls which (if any) function is called by the model.
        user: A unique identifier representing your end-user, which can help OpenAI to monitor and detect abuse.
        custom_prompt_arg: Legacy, largely ignored.
        **kwargs: Catches any unexpected keyword arguments.
    """
    loaded_config_data = app_config or load_and_log_configs()
    openai_config = loaded_config_data.get('openai_api', {})

    final_api_key = api_key or openai_config.get('api_key')
    if not final_api_key:
        logging.error("OpenAI: API key is missing.")
        raise ChatConfigurationError(provider="openai", message="OpenAI API Key is required but not found.")

    logging.debug("OpenAI: Using configured API key")

    # Resolve parameters: User-provided > Function arg default > Config default > Hardcoded default
    final_model = model if model is not None else openai_config.get('model', 'gpt-4o-mini')
    final_temp = temp if temp is not None else _safe_cast(openai_config.get('temperature'), float, 0.7)
    final_top_p = maxp if maxp is not None else _safe_cast(
        openai_config.get('top_p'), float, 0.95)  # 'maxp' from chat_api_call maps to 'top_p'

    final_streaming_cfg = openai_config.get('streaming', False)
    final_streaming = streaming if streaming is not None else \
        (str(final_streaming_cfg).lower() == 'true' if isinstance(final_streaming_cfg, str) else bool(final_streaming_cfg))

    final_max_tokens = max_tokens if max_tokens is not None else _safe_cast(openai_config.get('max_tokens'), int)

    if custom_prompt_arg:
        logging.warning(
            "OpenAI: 'custom_prompt_arg' was provided but is generally ignored if 'input_data' and 'system_message' are used correctly.")

    # Construct messages for OpenAI API
    api_messages = []
    has_system_message_in_input = any(msg.get("role") == "system" for msg in input_data)
    if system_message and not has_system_message_in_input:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    payload = {
        "model": final_model,
        "messages": api_messages,
        "stream": final_streaming,
    }
    # Add optional parameters if they have a value
    # gpt-5-mini has special requirements
    if final_model and 'gpt-5' in final_model.lower():
        # gpt-5-mini only supports temperature of 1 (default), and doesn't support top_p
        if final_temp is not None and final_temp != 1.0:
            logging.debug(f"OpenAI: gpt-5-mini only supports temperature of 1.0, ignoring temperature={final_temp}")
        # Don't include temperature for gpt-5 models unless it's 1.0
        if final_temp == 1.0:
            payload["temperature"] = final_temp
        # gpt-5-mini doesn't support top_p
        if final_top_p is not None:
            logging.debug(f"OpenAI: gpt-5-mini does not support top_p, ignoring top_p={final_top_p}")
    else:
        if final_temp is not None: payload["temperature"] = final_temp
        if final_top_p is not None: payload["top_p"] = final_top_p # OpenAI uses top_p
    # gpt-5-mini uses max_completion_tokens instead of max_tokens
    if final_max_tokens is not None:
        if final_model and 'gpt-5' in final_model:
            payload["max_completion_tokens"] = final_max_tokens
        else:
            payload["max_tokens"] = final_max_tokens
    if frequency_penalty is not None: payload["frequency_penalty"] = frequency_penalty
    if logit_bias is not None: payload["logit_bias"] = logit_bias
    if logprobs is not None: payload["logprobs"] = logprobs
    if top_logprobs is not None and payload.get("logprobs") is True:
        payload["top_logprobs"] = top_logprobs
    elif top_logprobs is not None:
         logging.warning("OpenAI: 'top_logprobs' provided but 'logprobs' is not true. 'top_logprobs' will be ignored.")
    if n is not None: payload["n"] = n
    if presence_penalty is not None: payload["presence_penalty"] = presence_penalty
    if response_format is not None: payload["response_format"] = response_format
    if seed is not None: payload["seed"] = seed
    if stop is not None: payload["stop"] = stop
    if tools is not None: payload["tools"] = tools

    # Then conditionally add tool_choice:
    _apply_tool_choice(payload, tools, tool_choice)
    if user is not None: payload["user"] = user # 'user' is OpenAI's user identifier field

    payload_metadata = _sanitize_payload_for_logging(payload)
    headers = {
        'Authorization': f'Bearer {final_api_key}',
        'Content-Type': 'application/json'
    }
    # Keep this phrasing aligned with tests that assert on the log text
    logging.debug(f"OpenAI Request Payload (excluding messages): {payload_metadata}")

    # Allow environment override for API base URL (useful for mock servers in tests)
    env_api_base = os.getenv('OPENAI_API_BASE_URL') or os.getenv('MOCK_OPENAI_BASE_URL')
    api_base = env_api_base or openai_config.get('api_base_url', 'https://api.openai.com/v1')
    api_url = api_base.rstrip('/') + '/chat/completions'
    try:
        if final_streaming:
            logging.debug("OpenAI: Posting request (streaming)")
            session = create_session_with_retries(
                total=_safe_cast(openai_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(openai_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            stream_timeout = _safe_cast(openai_config.get('api_timeout'), float, 90.0)
            try:
                response = session.post(api_url, headers=headers, json=payload, stream=True, timeout=stream_timeout)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            def stream_generator():
                try:
                    for chunk in iter_sse_lines_requests(response, decode_unicode=True, provider="openai"):
                        yield chunk
                    # Always append a single final sentinel; helper suppresses provider [DONE]
                    for tail in finalize_stream(response, done_already=False):
                        yield tail
                finally:
                    try:
                        session.close()
                    except Exception:
                        pass

            return stream_generator()

        else:  # Non-streaming
            logging.debug("OpenAI: Posting request (non-streaming)")
            session = create_session_with_retries(
                total=_safe_cast(openai_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(openai_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=payload,
                                        timeout=_safe_cast(openai_config.get('api_timeout'), float, 90.0))

                logging.debug(f"OpenAI: Full API response status: {response.status_code}")
                response.raise_for_status()  # Raise HTTPError for 4xx/5xx AFTER retries
                response_data = response.json()
                logging.debug("OpenAI: Non-streaming request successful.")
                return response_data
            finally:
                try:
                    session.close()
                except Exception:
                    pass

    except requests.exceptions.HTTPError as e:
        # Map HTTP errors from OpenAI into structured Chat* errors so the
        # FastAPI endpoint can return appropriate status codes instead of 500.
        status_code = None
        msg = ""
        if e.response is not None:
            status_code = e.response.status_code
            # Use repr() to safely log messages that may contain braces
            logging.error(
                f"OpenAI Full Error Response (status {status_code}): {repr(e.response.text)}"
            )
            try:
                err_json = e.response.json()
                msg = err_json.get("error", {}).get("message") or err_json.get("message") or ""
            except Exception:
                msg = e.response.text or str(e)
        else:
            logging.error(f"OpenAI HTTPError with no response object: {e}")
            msg = str(e)

        # Default a generic message if empty
        if not msg:
            msg = "OpenAI API error"

        # Map status codes
        if status_code in (400, 404, 422):
            raise ChatBadRequestError(provider="openai", message=msg)
        elif status_code in (401, 403):
            raise ChatAuthenticationError(provider="openai", message=msg)
        elif status_code == 429:
            raise ChatRateLimitError(provider="openai", message=msg)
        elif status_code in (500, 502, 503, 504):
            raise ChatProviderError(provider="openai", message=msg, status_code=status_code)
        else:
            raise ChatAPIError(provider="openai", message=msg, status_code=(status_code or 500))

    except requests.exceptions.RequestException as e:
        # Network/transport layer issue → surface as provider/unavailable (504-like)
        logging.error(f"OpenAI RequestException: {e}", exc_info=True)
        raise ChatProviderError(provider="openai", message=f"Network error: {e}", status_code=504)
    except Exception as e: # Catch any other unexpected error
        logging.error(f"OpenAI: Unexpected error in chat_with_openai: {e}", exc_info=True)
        raise ChatProviderError(provider="openai", message=f"Unexpected error: {e}")


async def chat_with_openai_async(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        maxp: Optional[float] = None,
        streaming: Optional[bool] = False,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        response_format: Optional[Dict[str, str]] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        user: Optional[str] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    """Async variant of chat_with_openai using httpx.AsyncClient.

    Returns JSON dict for non-streaming, and an async iterator of SSE lines for streaming.
    """
    loaded_config_data = app_config or load_and_log_configs()
    openai_config = loaded_config_data.get('openai_api', {})
    final_api_key = api_key or openai_config.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="openai", message="OpenAI API Key is required but not found.")

    final_model = model if model is not None else openai_config.get('model', 'gpt-4o-mini')
    final_temp = temp if temp is not None else _safe_cast(openai_config.get('temperature'), float, 0.7)
    final_top_p = maxp if maxp is not None else _safe_cast(openai_config.get('top_p'), float, 0.95)
    final_max_tokens = max_tokens if max_tokens is not None else _safe_cast(openai_config.get('max_tokens'), int)
    final_streaming_cfg = openai_config.get('streaming', False)
    final_streaming = bool(streaming if streaming is not None else (
        str(final_streaming_cfg).lower() == 'true' if isinstance(final_streaming_cfg, str) else final_streaming_cfg))

    api_messages: List[Dict[str, Any]] = []
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    is_gpt5_model = bool(final_model and 'gpt-5' in final_model.lower())
    payload: Dict[str, Any] = {
        "model": final_model,
        "messages": api_messages,
        "stream": final_streaming,
    }
    if is_gpt5_model:
        if final_temp is not None and final_temp != 1.0:
            logging.debug(f"OpenAI async: gpt-5 models only accept temperature=1.0, ignoring {final_temp}")
        if final_temp == 1.0:
            payload["temperature"] = final_temp
        if final_top_p is not None:
            logging.debug(f"OpenAI async: gpt-5 models do not accept top_p, ignoring {final_top_p}")
    else:
        if final_temp is not None:
            payload["temperature"] = final_temp
        if final_top_p is not None:
            payload["top_p"] = final_top_p
    if final_max_tokens is not None:
        if is_gpt5_model:
            payload["max_completion_tokens"] = final_max_tokens
        else:
            payload["max_tokens"] = final_max_tokens
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if logit_bias is not None:
        payload["logit_bias"] = logit_bias
    if logprobs is not None:
        payload["logprobs"] = logprobs
    if top_logprobs is not None and payload.get("logprobs"):
        payload["top_logprobs"] = top_logprobs
    if n is not None:
        payload["n"] = n
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
    _apply_tool_choice(payload, tools, tool_choice)
    if user is not None:
        payload["user"] = user

    env_api_base = os.getenv('OPENAI_API_BASE_URL') or os.getenv('MOCK_OPENAI_BASE_URL')
    api_base = env_api_base or openai_config.get('api_base_url', 'https://api.openai.com/v1')
    api_url = api_base.rstrip('/') + '/chat/completions'
    headers = {"Authorization": f"Bearer {final_api_key}", "Content-Type": "application/json"}

    timeout = _safe_cast(openai_config.get('api_timeout'), float, 90.0)
    retry_limit = max(0, _safe_cast(openai_config.get('api_retries'), int, 3))
    retry_delay = max(0.0, _safe_cast(openai_config.get('api_retry_delay'), float, 1.0))

    def _raise_openai_http_error(exc: httpx.HTTPStatusError) -> None:
        _raise_httpx_chat_error("openai", exc)

    try:
        if final_streaming:
            async def _stream_async():
                for attempt in range(retry_limit + 1):
                    try:
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            async with client.stream("POST", api_url, headers=headers, json=payload) as resp:
                                try:
                                    resp.raise_for_status()
                                except httpx.HTTPStatusError as e:
                                    status_code = getattr(e.response, "status_code", None)
                                    if _is_retryable_status(status_code) and attempt < retry_limit:
                                        await _async_retry_sleep(retry_delay, attempt)
                                        continue
                                    _raise_httpx_chat_error("openai", e)
                                async for chunk in aiter_sse_lines_httpx(resp, provider="openai"):
                                    yield chunk
                                # Append a single [DONE]
                                yield sse_done()
                                return
                    except httpx.RequestError as e:
                        if attempt < retry_limit:
                            await _async_retry_sleep(retry_delay, attempt)
                            continue
                        raise ChatProviderError(provider="openai", message=f"Network error: {e}", status_code=504)
                    except ChatAPIError:
                        raise
                raise ChatProviderError(provider="openai", message="Exceeded retry attempts for OpenAI stream", status_code=504)

            return _stream_async()
        else:
            for attempt in range(retry_limit + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.post(api_url, headers=headers, json=payload)
                        try:
                            resp.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            status_code = getattr(e.response, "status_code", None)
                            if _is_retryable_status(status_code) and attempt < retry_limit:
                                await _async_retry_sleep(retry_delay, attempt)
                                continue
                            _raise_httpx_chat_error("openai", e)
                        return resp.json()
                except httpx.RequestError as e:
                    if attempt < retry_limit:
                        await _async_retry_sleep(retry_delay, attempt)
                        continue
                    raise ChatProviderError(provider="openai", message=f"Network error: {e}", status_code=504)
            raise ChatProviderError(provider="openai", message="Exceeded retry attempts for OpenAI request", status_code=504)
    except ChatAPIError:
        raise
    except httpx.RequestError as e:
        raise ChatProviderError(provider="openai", message=f"Network error: {e}", status_code=504)
    except Exception as e:
        raise ChatProviderError(provider="openai", message=f"Unexpected error: {e}")


async def chat_with_groq_async(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        maxp: Optional[float] = None,
        streaming: Optional[bool] = False,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    """Async Groq provider using httpx.AsyncClient with SSE normalization."""
    cfg_source = app_config or load_and_log_configs()
    cfg = cfg_source.get('groq_api', {})
    final_api_key = api_key or cfg.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="groq", message="Groq API Key required.")
    current_model = model or cfg.get('model', 'llama3-8b-8192')
    current_temp = temp if temp is not None else _safe_cast(cfg.get('temperature'), float, 0.2)
    current_top_p = maxp if maxp is not None else _safe_cast(cfg.get('top_p'), float, None)
    stream_cfg = cfg.get('streaming', False)
    current_streaming = streaming if streaming is not None else (
        str(stream_cfg).lower() == 'true' if isinstance(stream_cfg, str) else bool(stream_cfg))
    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(cfg.get('max_tokens'), int, None)

    api_messages: List[Dict[str, Any]] = []
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)
    payload: Dict[str, Any] = {"model": current_model, "messages": api_messages, "stream": current_streaming}
    if current_temp is not None:
        payload["temperature"] = current_temp
    if current_top_p is not None:
        payload["top_p"] = current_top_p
    if current_max_tokens is not None:
        payload["max_tokens"] = current_max_tokens
    if seed is not None:
        payload["seed"] = seed
    if stop is not None:
        payload["stop"] = stop
    if response_format is not None:
        payload["response_format"] = response_format
    if n is not None:
        payload["n"] = n
    if user is not None:
        payload["user"] = user
    if tools is not None:
        payload["tools"] = tools
    _apply_tool_choice(payload, tools, tool_choice)
    if logit_bias is not None:
        payload["logit_bias"] = logit_bias
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if logprobs is not None:
        payload["logprobs"] = logprobs
    if top_logprobs is not None and payload.get("logprobs"):
        payload["top_logprobs"] = top_logprobs

    api_url = (cfg.get('api_base_url', 'https://api.groq.com/openai/v1').rstrip('/') + '/chat/completions')
    headers = {"Authorization": f"Bearer {final_api_key}", "Content-Type": "application/json"}
    timeout = _safe_cast(cfg.get('api_timeout'), float, 90.0)
    retry_limit = max(0, _safe_cast(cfg.get('api_retries'), int, 3))
    retry_delay = max(0.0, _safe_cast(cfg.get('api_retry_delay'), float, 1.0))

    def _raise_groq_http_error(exc: httpx.HTTPStatusError) -> None:
        _raise_httpx_chat_error("groq", exc)

    try:
        if current_streaming:
            async def _stream():
                for attempt in range(retry_limit + 1):
                    try:
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            async with client.stream("POST", api_url, headers=headers, json=payload) as resp:
                                try:
                                    resp.raise_for_status()
                                except httpx.HTTPStatusError as e:
                                    sc = getattr(e.response, "status_code", None)
                                    if _is_retryable_status(sc) and attempt < retry_limit:
                                        await _async_retry_sleep(retry_delay, attempt)
                                        continue
                                    _raise_groq_http_error(e)
                                async for chunk in aiter_sse_lines_httpx(resp, provider="groq"):
                                    yield chunk
                                yield sse_done()
                                return
                    except httpx.RequestError as e:
                        if attempt < retry_limit:
                            await _async_retry_sleep(retry_delay, attempt)
                            continue
                        raise ChatProviderError(provider="groq", message=f"Network error: {e}", status_code=504)
                    except ChatAPIError:
                        raise
                raise ChatProviderError(provider="groq", message="Exceeded retry attempts for Groq stream", status_code=504)

            return _stream()
        else:
            for attempt in range(retry_limit + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.post(api_url, headers=headers, json=payload)
                        try:
                            resp.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            sc = getattr(e.response, "status_code", None)
                            if _is_retryable_status(sc) and attempt < retry_limit:
                                await _async_retry_sleep(retry_delay, attempt)
                                continue
                            _raise_groq_http_error(e)
                        return resp.json()
                except httpx.RequestError as e:
                    if attempt < retry_limit:
                        await _async_retry_sleep(retry_delay, attempt)
                        continue
                    raise ChatProviderError(provider="groq", message=f"Network error: {e}", status_code=504)
            raise ChatProviderError(provider="groq", message="Exceeded retry attempts for Groq request", status_code=504)
    except ChatAPIError:
        raise
    except httpx.RequestError as e:
        raise ChatProviderError(provider="groq", message=f"Network error: {e}", status_code=504)
    except Exception as e:
        raise ChatProviderError(provider="groq", message=f"Unexpected error: {e}")


async def chat_with_anthropic_async(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temp: Optional[float] = None,
        topp: Optional[float] = None,
        topk: Optional[int] = None,
        streaming: Optional[bool] = False,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    """Async Anthropic messages API with SSE normalization."""
    cfg_source = app_config or load_and_log_configs()
    cfg = cfg_source.get('anthropic_api', {})
    final_api_key = api_key or cfg.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="anthropic", message="Anthropic API Key is required.")
    current_model = model or cfg.get('model', 'claude-3-haiku-20240307')
    current_temp = temp if temp is not None else _safe_cast(cfg.get('temperature'), float, 0.7)
    stream_cfg = cfg.get('streaming', False)
    current_streaming = streaming if streaming is not None else (
        str(stream_cfg).lower() == 'true' if isinstance(stream_cfg, str) else bool(stream_cfg))
    default_max_tokens = int(cfg.get('max_tokens_to_sample', cfg.get('max_tokens', 4096)))
    current_max_tokens = max_tokens if max_tokens is not None else default_max_tokens

    anthropic_messages: List[Dict[str, Any]] = []
    for msg in input_data:
        role = msg.get("role")
        content = msg.get("content")
        if role not in ["user", "assistant"]:
            continue
        parts: List[Dict[str, Any]] = []
        if isinstance(content, str):
            parts.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    parts.append({"type": "text", "text": part.get("text", "")})
                elif part.get("type") == "image_url":
                    image_source = _anthropic_image_source_from_part(part.get("image_url", {}))
                    if image_source:
                        parts.append({"type": "image", "source": image_source})
        if parts:
            anthropic_messages.append({"role": role, "content": parts})
    if not any(m['role'] == 'user' for m in anthropic_messages):
        raise ChatBadRequestError(provider="anthropic", message="No valid user messages found.")

    headers = {
        'x-api-key': final_api_key,
        'anthropic-version': cfg.get('api_version', '2023-06-01'),
        'Content-Type': 'application/json'
    }
    payload: Dict[str, Any] = {
        "model": current_model,
        "max_tokens": current_max_tokens,
        "messages": anthropic_messages,
        "stream": current_streaming,
    }
    if system_prompt is not None:
        payload["system"] = system_prompt
    if current_temp is not None:
        payload["temperature"] = current_temp
    if topp is not None:
        payload["top_p"] = topp
    if topk is not None:
        payload["top_k"] = topk
    if stop_sequences is not None:
        payload["stop_sequences"] = stop_sequences
    if tools is not None:
        payload["tools"] = tools

    api_url = (cfg.get('api_base_url', 'https://api.anthropic.com/v1').rstrip('/') + '/messages')
    timeout = _safe_cast(cfg.get('api_timeout'), float, 90.0)
    retry_limit = max(0, _safe_cast(cfg.get('api_retries'), int, 3))
    retry_delay = max(0.0, _safe_cast(cfg.get('api_retry_delay'), float, 1.0))

    def _raise_anthropic_http_error(exc: httpx.HTTPStatusError) -> None:
        _raise_httpx_chat_error("anthropic", exc)

    try:
        if current_streaming:
            async def _stream():
                for attempt in range(retry_limit + 1):
                    try:
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            async with client.stream("POST", api_url, headers=headers, json=payload) as resp:
                                try:
                                    resp.raise_for_status()
                                except httpx.HTTPStatusError as e:
                                    sc = getattr(e.response, "status_code", None)
                                    if _is_retryable_status(sc) and attempt < retry_limit:
                                        await _async_retry_sleep(retry_delay, attempt)
                                        continue
                                    _raise_anthropic_http_error(e)
                                tool_states: Dict[int, Dict[str, Any]] = {}
                                tool_counter = 0
                                done_sent = False
                                async for line in resp.aiter_lines():
                                    if not line:
                                        continue
                                    if is_done_line(line):
                                        if not done_sent:
                                            done_sent = True
                                            yield sse_done()
                                        continue
                                    ls = line.strip()
                                    if not ls or not ls.startswith('data:'):
                                        continue
                                    event_data_str = ls[len('data:'):].strip()
                                    if not event_data_str:
                                        continue
                                    try:
                                        ev = json.loads(event_data_str)
                                    except Exception:
                                        continue
                                    ev_type = ev.get('type')
                                    if ev_type == 'content_block_start':
                                        content_block = ev.get('content_block', {})
                                        if content_block.get('type') == 'tool_use':
                                            block_index = ev.get('index')
                                            tool_id = content_block.get('id') or f"anthropic_tool_{tool_counter}"
                                            tool_name = content_block.get('name')
                                            initial_input = content_block.get('input')
                                            buffer = ""
                                            if initial_input:
                                                try:
                                                    buffer = json.dumps(initial_input)
                                                except Exception:
                                                    buffer = str(initial_input)
                                            tool_states[block_index] = {
                                                "id": tool_id,
                                                "name": tool_name,
                                                "buffer": buffer,
                                                "position": tool_counter,
                                            }
                                            tool_counter += 1
                                            yield _anthropic_tool_delta_chunk(
                                                tool_states[block_index]["position"],
                                                tool_id,
                                                tool_name,
                                                buffer,
                                            )
                                    elif ev_type == 'content_block_delta':
                                        delta = ev.get('delta', {})
                                        block_index = ev.get('index')
                                        delta_type = delta.get('type')
                                        if delta_type == 'text_delta' and 'text' in delta:
                                            yield openai_delta_chunk(delta.get('text', ''))
                                        elif delta_type == 'input_json_delta' and block_index in tool_states:
                                            partial = delta.get('partial_json', '')
                                            if partial:
                                                state = tool_states[block_index]
                                                state['buffer'] += partial
                                                yield _anthropic_tool_delta_chunk(
                                                    state['position'], state['id'], state['name'], state['buffer']
                                                )
                                        elif delta_type == 'tool_use_delta' and block_index in tool_states:
                                            state = tool_states[block_index]
                                            if 'name' in delta and delta['name']:
                                                state['name'] = delta['name']
                                            if 'input' in delta and delta['input'] is not None:
                                                try:
                                                    state['buffer'] = json.dumps(delta['input'])
                                                except Exception:
                                                    state['buffer'] = str(delta['input'])
                                            yield _anthropic_tool_delta_chunk(
                                                state['position'], state['id'], state['name'], state['buffer']
                                            )
                                    elif ev_type == 'message_delta':
                                        stop_reason = (ev.get('delta') or {}).get('stop_reason')
                                        if stop_reason:
                                            finish_reason_map = {
                                                "end_turn": "stop",
                                                "max_tokens": "length",
                                                "stop_sequence": "stop",
                                                "tool_use": "tool_calls",
                                            }
                                            finish_reason = finish_reason_map.get(stop_reason, stop_reason)
                                            yield sse_data({"choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]})
                                if not done_sent:
                                    yield sse_done()
                                return
                    except httpx.RequestError as e:
                        if attempt < retry_limit:
                            await _async_retry_sleep(retry_delay, attempt)
                            continue
                        raise ChatProviderError(provider="anthropic", message=f"Network error: {e}", status_code=504)
                    except ChatAPIError:
                        raise
                raise ChatProviderError(provider="anthropic", message="Exceeded retry attempts for Anthropic stream", status_code=504)

            return _stream()
        else:
            for attempt in range(retry_limit + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.post(api_url, headers=headers, json=payload)
                        try:
                            resp.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            sc = getattr(e.response, "status_code", None)
                            if _is_retryable_status(sc) and attempt < retry_limit:
                                await _async_retry_sleep(retry_delay, attempt)
                                continue
                            _raise_anthropic_http_error(e)
                        data = resp.json()
                        return _normalize_anthropic_response(data, current_model)
                except httpx.RequestError as e:
                    if attempt < retry_limit:
                        await _async_retry_sleep(retry_delay, attempt)
                        continue
                    raise ChatProviderError(provider="anthropic", message=f"Network error: {e}", status_code=504)
            raise ChatProviderError(provider="anthropic", message="Exceeded retry attempts for Anthropic request", status_code=504)
    except ChatAPIError:
        raise
    except Exception as e:
        raise ChatProviderError(provider="anthropic", message=f"Unexpected error: {e}")


async def chat_with_openrouter_async(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        min_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    cfg_source = app_config or load_and_log_configs()
    cfg = cfg_source.get('openrouter_api', {})
    final_api_key = api_key or cfg.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider='openrouter', message='OpenRouter API Key required.')
    current_model = model or cfg.get('model', 'mistralai/mistral-7b-instruct:free')
    stream_cfg = cfg.get('streaming', False)
    current_streaming = streaming if streaming is not None else (
        str(stream_cfg).lower() == 'true' if isinstance(stream_cfg, str) else bool(stream_cfg))

    api_messages = []
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    payload: Dict[str, Any] = {"model": current_model, "messages": api_messages, "stream": current_streaming}
    if temp is not None:
        payload["temperature"] = temp
    if top_p is not None:
        payload["top_p"] = top_p
    if top_k is not None:
        payload["top_k"] = top_k
    if min_p is not None:
        payload["min_p"] = min_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if seed is not None:
        payload["seed"] = seed
    if stop is not None:
        payload["stop"] = stop
    if response_format is not None:
        payload["response_format"] = response_format
    if n is not None:
        payload["n"] = n
    if user is not None:
        payload["user"] = user
    if tools is not None:
        payload["tools"] = tools
    _apply_tool_choice(payload, tools, tool_choice)
    if logit_bias is not None:
        payload["logit_bias"] = logit_bias
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if logprobs is not None:
        payload["logprobs"] = logprobs
    if top_logprobs is not None and payload.get("logprobs"):
        payload["top_logprobs"] = top_logprobs

    base_url = cfg.get('api_base_url', 'https://openrouter.ai/api/v1')
    api_url = base_url.rstrip('/') + '/chat/completions'
    headers = {
        "Authorization": f"Bearer {final_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": cfg.get("site_url", "http://localhost"),
        "X-Title": cfg.get("site_name", "TLDW-API"),
    }
    timeout = _safe_cast(cfg.get('api_timeout'), float, 90.0)
    retry_limit = max(0, _safe_cast(cfg.get('api_retries'), int, 3))
    retry_delay = max(0.0, _safe_cast(cfg.get('api_retry_delay'), float, 1.0))

    def _raise_openrouter_http_error(exc: httpx.HTTPStatusError) -> None:
        _raise_httpx_chat_error("openrouter", exc)

    try:
        if current_streaming:
            async def _stream():
                for attempt in range(retry_limit + 1):
                    try:
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            async with client.stream("POST", api_url, headers=headers, json=payload) as resp:
                                try:
                                    resp.raise_for_status()
                                except httpx.HTTPStatusError as e:
                                    sc = getattr(e.response, "status_code", None)
                                    if _is_retryable_status(sc) and attempt < retry_limit:
                                        await _async_retry_sleep(retry_delay, attempt)
                                        continue
                                    _raise_openrouter_http_error(e)
                                async for chunk in aiter_sse_lines_httpx(resp, provider="openrouter"):
                                    yield chunk
                                yield sse_done()
                                return
                    except httpx.RequestError as e:
                        if attempt < retry_limit:
                            await _async_retry_sleep(retry_delay, attempt)
                            continue
                        raise ChatProviderError(provider="openrouter", message=f"Network error: {e}", status_code=504)
                    except ChatAPIError:
                        raise
                raise ChatProviderError(provider="openrouter", message="Exceeded retry attempts for OpenRouter stream", status_code=504)

            return _stream()
        else:
            for attempt in range(retry_limit + 1):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.post(api_url, headers=headers, json=payload)
                        try:
                            resp.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            sc = getattr(e.response, "status_code", None)
                            if _is_retryable_status(sc) and attempt < retry_limit:
                                await _async_retry_sleep(retry_delay, attempt)
                                continue
                            _raise_openrouter_http_error(e)
                        return resp.json()
                except httpx.RequestError as e:
                    if attempt < retry_limit:
                        await _async_retry_sleep(retry_delay, attempt)
                        continue
                    raise ChatProviderError(provider="openrouter", message=f"Network error: {e}", status_code=504)
            raise ChatProviderError(provider="openrouter", message="Exceeded retry attempts for OpenRouter request", status_code=504)
    except ChatAPIError:
        raise
    except httpx.RequestError as e:
        raise ChatProviderError(provider="openrouter", message=f"Network error: {e}", status_code=504)
    except Exception as e:
        raise ChatProviderError(provider="openrouter", message=f"Unexpected error: {e}")


def chat_with_bedrock(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        maxp: Optional[float] = None,  # top_p
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        seed: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        user: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    """
    AWS Bedrock via OpenAI-compatible Chat Completions endpoint.

    Uses Bedrock Runtime OpenAI compatibility layer:
    https://bedrock-runtime.<region>.amazonaws.com/openai/v1/chat/completions

    Auth supports Bedrock API key (Bearer). AWS SigV4 is not implemented here.
    """
    loaded_config_data = app_config or load_and_log_configs()
    if loaded_config_data is None:
        raise ChatConfigurationError(provider="bedrock", message="Configuration not available.")

    br_cfg = loaded_config_data.get('bedrock_api', {})
    final_api_key = api_key or br_cfg.get('api_key') or os.getenv('BEDROCK_API_KEY')
    if not final_api_key:
        # Support the AWS docs' bearer token env var as a fallback
        final_api_key = os.getenv('AWS_BEARER_TOKEN_BEDROCK')
    if not final_api_key:
        raise ChatConfigurationError(provider="bedrock", message="Bedrock API key is required (BEDROCK_API_KEY or AWS_BEARER_TOKEN_BEDROCK).")

    # Determine endpoint
    runtime_endpoint = br_cfg.get('runtime_endpoint')  # e.g., https://bedrock-runtime.us-west-2.amazonaws.com
    region = br_cfg.get('region') or os.getenv('BEDROCK_REGION') or 'us-west-2'
    api_base_url = br_cfg.get('api_base_url')
    if not api_base_url:
        if runtime_endpoint:
            api_base_url = runtime_endpoint.rstrip('/') + '/openai'
        else:
            api_base_url = f"https://bedrock-runtime.{region}.amazonaws.com/openai"

    current_model = model or br_cfg.get('model')
    if not current_model:
        raise ChatConfigurationError(provider="bedrock", message="Bedrock model is required (set model or configure bedrock_model).")

    current_temp = temp if temp is not None else _safe_cast(br_cfg.get('temperature'), float, 0.7)
    current_streaming = streaming if streaming is not None else (
        str(br_cfg.get('streaming', 'false')).lower() == 'true'
    )
    current_top_p = maxp if maxp is not None else _safe_cast(br_cfg.get('top_p'), float, None)
    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(br_cfg.get('max_tokens'), int, None)

    headers = {
        'Authorization': f'Bearer {final_api_key}',
        'Content-Type': 'application/json'
    }

    # Build messages list and payload
    api_messages: List[Dict[str, Any]] = []
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    payload: Dict[str, Any] = {
        "model": current_model,
        "messages": api_messages,
        "stream": current_streaming,
    }
    if current_temp is not None: payload["temperature"] = current_temp
    if current_top_p is not None: payload["top_p"] = current_top_p
    if current_max_tokens is not None: payload["max_tokens"] = current_max_tokens
    if n is not None: payload["n"] = n
    if stop is not None: payload["stop"] = stop
    if presence_penalty is not None: payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None: payload["frequency_penalty"] = frequency_penalty
    if logit_bias is not None: payload["logit_bias"] = logit_bias
    if seed is not None: payload["seed"] = seed
    if response_format is not None: payload["response_format"] = response_format
    if tools is not None: payload["tools"] = tools
    _apply_tool_choice(payload, tools, tool_choice)
    if logprobs is not None: payload["logprobs"] = logprobs
    if top_logprobs is not None: payload["top_logprobs"] = top_logprobs
    if user is not None: payload["user"] = user
    if extra_headers is not None:
        headers.update({str(k): str(v) for k, v in extra_headers.items()})
    if extra_body is not None: payload["extra_body"] = extra_body

    # Endpoint path
    api_url = api_base_url.rstrip('/') + '/v1/chat/completions'

    retry_count = _safe_cast(br_cfg.get('api_retries'), int, 3)
    retry_delay = _safe_cast(br_cfg.get('api_retry_delay'), float, 1.0)
    timeout = _safe_cast(br_cfg.get('api_timeout'), float, 90.0)

    logging.debug(f"Bedrock: POST {api_url} (stream={current_streaming})")

    session = create_session_with_retries(
        total=retry_count,
        backoff_factor=retry_delay,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )

    try:
        if current_streaming:
            response = session.post(api_url, headers=headers, json=payload, stream=True, timeout=timeout + 60)
            response.raise_for_status()
            session_handle = session
            response_handle = response

            def stream_generator():
                done_sent = False
                try:
                    for raw in response_handle.iter_lines():
                        if not raw:
                            continue
                        try:
                            line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                        except Exception:
                            # Fallback best-effort
                            line = str(raw)
                        if is_done_line(line):
                            done_sent = True
                        normalized = normalize_provider_line(line)
                        if normalized is None:
                            continue
                        yield normalized
                    if not done_sent:
                        done_sent = True
                        yield sse_done()
                except requests.exceptions.ChunkedEncodingError as e_chunk:
                    logging.error(f"Bedrock stream chunked encoding error: {e_chunk}")
                    yield sse_data({"error": {"message": f"Stream connection error: {str(e_chunk)}", "type": "bedrock_stream_error"}})
                except Exception as e_stream:
                    logging.error(f"Bedrock stream iteration error: {e_stream}", exc_info=True)
                    yield sse_data({"error": {"message": f"Stream iteration error: {str(e_stream)}", "type": "bedrock_stream_error"}})
                finally:
                    for tail in finalize_stream(response_handle, done_already=done_sent):
                        yield tail
                    try:
                        session_handle.close()
                    except Exception:
                        pass

            session = None
            return stream_generator()
        else:
            response = session.post(api_url, headers=headers, json=payload, timeout=timeout)
            logging.debug(f"Bedrock: status={response.status_code}")
            response.raise_for_status()
            try:
                return response.json()
            finally:
                try:
                    response.close()
                except Exception:
                    pass
    except requests.exceptions.HTTPError as e:
        status_code = getattr(e.response, 'status_code', None)
        error_text = getattr(e.response, 'text', str(e))
        logging.error(f"Bedrock HTTPError {status_code}: {repr(error_text[:500])}")
        if status_code in (400, 404, 422):
            raise ChatBadRequestError(provider="bedrock", message=error_text)
        elif status_code in (401, 403):
            raise ChatAuthenticationError(provider="bedrock", message=error_text)
        elif status_code == 429:
            raise ChatRateLimitError(provider="bedrock", message=error_text)
        elif status_code in (500, 502, 503, 504):
            raise ChatProviderError(provider="bedrock", message=error_text, status_code=status_code)
        else:
            raise ChatAPIError(provider="bedrock", message=error_text, status_code=(status_code or 500))
    except requests.exceptions.RequestException as e:
        logging.error(f"Bedrock RequestException: {e}", exc_info=True)
        raise ChatProviderError(provider="bedrock", message=f"Network error: {e}", status_code=504)
    except Exception as e:
        logging.error(f"Bedrock unexpected error: {e}", exc_info=True)
        raise ChatProviderError(provider="bedrock", message=f"Unexpected error: {e}")
    finally:
        if session is not None:
            session.close()


def chat_with_anthropic(
        input_data: List[Dict[str, Any]], # Mapped from 'messages_payload'
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None, # Mapped from 'system_message'
        temp: Optional[float] = None,
        topp: Optional[float] = None,       # Mapped from 'topp' (becomes top_p)
        topk: Optional[int] = None,
        streaming: Optional[bool] = False,
        max_tokens: Optional[int] = None,   # New: Anthropic uses 'max_tokens'
        stop_sequences: Optional[List[str]] = None, # New: Mapped from 'stop'
        tools: Optional[List[Dict[str, Any]]] = None, # New: Anthropic tool format
        # Anthropic doesn't typically use seed, response_format (for JSON object mode directly), n, user identifier, logit_bias,
        # presence_penalty, frequency_penalty, logprobs, top_logprobs in the same way as OpenAI.
        # tool_choice is usually implicit with tools or controlled differently.
        custom_prompt_arg: Optional[str] = None, # Legacy
        app_config: Optional[Dict[str, Any]] = None,
):
    # Assuming load_and_log_configs is defined elsewhere
    loaded_config_data = app_config or load_and_log_configs()
    anthropic_config = loaded_config_data.get('anthropic_api', {})
    final_api_key = api_key or anthropic_config.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="anthropic", message="Anthropic API Key is required.")

    logging.debug("Anthropic: Using configured API key")

    current_model = model or anthropic_config.get('model', 'claude-3-haiku-20240307')
    current_temp = temp if temp is not None else _safe_cast(anthropic_config.get('temperature'), float, 0.7)
    current_top_p = topp
    current_top_k = topk
    current_streaming_cfg = anthropic_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else \
        (str(current_streaming_cfg).lower() == 'true' if isinstance(current_streaming_cfg, str) else bool(current_streaming_cfg))

    # Use the passed max_tokens if available, else config, else a default
    fallback_max_tokens = _safe_cast(anthropic_config.get('max_tokens'), int, 4096)
    default_max_tokens = _safe_cast(anthropic_config.get('max_tokens_to_sample'), int, fallback_max_tokens)
    current_max_tokens = max_tokens if max_tokens is not None else default_max_tokens


    anthropic_messages = []
    for msg in input_data:
        role = msg.get("role")
        content = msg.get("content")
        if role not in ["user", "assistant"]:
            logging.warning(f"Anthropic: Skipping message with unsupported role: {role}")
            continue
        # ... (multimodal content processing for Anthropic from your existing function) ...
        anthropic_content_parts = []
        if isinstance(content, str):
            anthropic_content_parts.append({"type": "text", "text": content})
        elif isinstance(content, list): # OpenAI content part list
            for part in content:
                part_type = part.get("type")
                if part_type == "text":
                    anthropic_content_parts.append({"type": "text", "text": part.get("text", "")})
                elif part_type == "image_url":
                    image_source = _anthropic_image_source_from_part(part.get("image_url", {}))
                    if image_source:
                        anthropic_content_parts.append({"type": "image", "source": image_source})
        if anthropic_content_parts:
            anthropic_messages.append({"role": role, "content": anthropic_content_parts})


    if not any(m['role'] == 'user' for m in anthropic_messages):
        raise ChatBadRequestError(provider="anthropic", message="No valid user messages found for Anthropic.")

    headers = {
        'x-api-key': final_api_key,
        'anthropic-version': anthropic_config.get('api_version', '2023-06-01'),
        'Content-Type': 'application/json'
    }
    data = {
        "model": current_model,
        "max_tokens": current_max_tokens, # Changed from max_tokens_to_sample to the parameter
        "messages": anthropic_messages,
        "stream": current_streaming,
    }
    if system_prompt is not None: data["system"] = system_prompt # Anthropic uses 'system' at the top level
    if current_temp is not None: data["temperature"] = current_temp
    if current_top_p is not None: data["top_p"] = current_top_p
    if current_top_k is not None: data["top_k"] = current_top_k
    if stop_sequences is not None: data["stop_sequences"] = stop_sequences
    if tools is not None: data["tools"] = tools # Assuming 'tools' is already in Anthropic's required format

    api_url = anthropic_config.get('api_base_url', 'https://api.anthropic.com/v1').rstrip('/') + '/messages'
    data_metadata = _sanitize_payload_for_logging(data, text_keys=("system",))
    logging.debug(f"Anthropic request metadata: {data_metadata}")

    session = create_session_with_retries(
        total=_safe_cast(anthropic_config.get('api_retries'), int, 3),
        backoff_factor=_safe_cast(anthropic_config.get('api_retry_delay'), float, 1.0),
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )

    try:
        response = session.post(api_url, headers=headers, json=data, stream=current_streaming, timeout=180)
        response.raise_for_status()

        if current_streaming:
            logging.debug("Anthropic: Streaming response received. Normalizing to OpenAI SSE.")
            session_handle = session
            response_handle = response

            def stream_generator():
                tool_states: Dict[int, Dict[str, Any]] = {}
                tool_counter = 0
                done_sent = False

                try:
                    for line_bytes in response_handle.iter_lines():  # iter_lines gives bytes
                        if not line_bytes:
                            continue
                        try:
                            decoded = line_bytes.decode('utf-8')
                        except Exception:
                            decoded = str(line_bytes)
                        if is_done_line(decoded):
                            if not done_sent:
                                done_sent = True
                                yield sse_done()
                            continue
                        stripped = decoded.strip()
                        if not stripped or not stripped.startswith("data:"):
                            continue
                        event_data_str = stripped[len("data:"):].strip()
                        if not event_data_str:
                            continue
                        try:
                            anthropic_event = json.loads(event_data_str)
                        except json.JSONDecodeError:
                            logging.warning(f"Anthropic Stream: Could not decode JSON: {event_data_str}")
                            continue

                        ev_type = anthropic_event.get("type")
                        if ev_type == "content_block_start":
                            content_block = anthropic_event.get("content_block", {})
                            if content_block.get("type") == "tool_use":
                                block_index = anthropic_event.get("index")
                                tool_id = content_block.get("id") or f"anthropic_tool_{tool_counter}"
                                tool_name = content_block.get("name")
                                initial_input = content_block.get("input")
                                buffer = ""
                                if initial_input:
                                    try:
                                        buffer = json.dumps(initial_input)
                                    except Exception:
                                        buffer = str(initial_input)
                                tool_states[block_index] = {
                                    "id": tool_id,
                                    "name": tool_name,
                                    "buffer": buffer,
                                    "position": tool_counter,
                                }
                                tool_counter += 1
                                yield _anthropic_tool_delta_chunk(
                                    tool_states[block_index]["position"],
                                    tool_id,
                                    tool_name,
                                    buffer,
                                )
                        elif ev_type == "content_block_delta":
                            delta = anthropic_event.get("delta", {})
                            block_index = anthropic_event.get("index")
                            delta_type = delta.get("type")
                            if delta_type == "text_delta" and "text" in delta:
                                yield openai_delta_chunk(delta.get("text", ""))
                            elif delta_type == "input_json_delta" and block_index in tool_states:
                                partial = delta.get("partial_json", "")
                                if partial:
                                    state = tool_states[block_index]
                                    state["buffer"] += partial
                                    yield _anthropic_tool_delta_chunk(
                                        state["position"], state["id"], state["name"], state["buffer"]
                                    )
                            elif delta_type == "tool_use_delta" and block_index in tool_states:
                                state = tool_states[block_index]
                                new_name = delta.get("name")
                                new_input = delta.get("input")
                                if new_name:
                                    state["name"] = new_name
                                if new_input:
                                    try:
                                        state["buffer"] = json.dumps(new_input)
                                    except Exception:
                                        state["buffer"] = str(new_input)
                                yield _anthropic_tool_delta_chunk(
                                    state["position"], state["id"], state["name"], state["buffer"]
                                )
                        elif ev_type == "message_delta":
                            stop_reason = (anthropic_event.get("delta") or {}).get("stop_reason")
                            if stop_reason:
                                finish_reason_map = {
                                    "end_turn": "stop",
                                    "max_tokens": "length",
                                    "stop_sequence": "stop",
                                    "tool_use": "tool_calls",
                                }
                                finish_reason = finish_reason_map.get(stop_reason, stop_reason)
                                yield sse_data({"choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]})
                        # Ignore other event types for now
                except GeneratorExit:
                    if response:
                        response.close()
                    raise
                except requests.exceptions.ChunkedEncodingError as e:
                    logging.error(f"Anthropic: ChunkedEncodingError during stream: {e}", exc_info=True)
                    yield sse_data({"error": {"message": f"Stream connection error: {str(e)}", "type": "anthropic_stream_error"}})
                except Exception as e:
                    logging.error(f"Anthropic: Error during stream iteration: {e}", exc_info=True)
                    yield sse_data({"error": {"message": f"Stream iteration error: {str(e)}", "type": "anthropic_stream_error"}})
                finally:
                    for tail in finalize_stream(response_handle, done_already=done_sent):
                        yield tail
                    try:
                        session_handle.close()
                    except Exception:
                        pass

            session = None
            return stream_generator()
        else:
            # ... (non-streaming logic remains the same) ...
            logging.debug("Anthropic: Non-streaming request successful.")
            try:
                response_data = response.json()
            finally:
                try:
                    response.close()
                except Exception:
                    pass
            logging.debug("Anthropic: Non-streaming request successful. Normalizing response.")
            return _normalize_anthropic_response(response_data, current_model)
    except requests.exceptions.HTTPError as e:
        # ... (error handling from your file, ensure provider is "anthropic") ...
        status_code = e.response.status_code if e.response is not None else 500
        error_text = e.response.text if e.response is not None else "No response text"
        if status_code == 401: raise ChatAuthenticationError(provider="anthropic", message=f"Auth failed. Detail: {error_text[:200]}") from e
        elif status_code == 429: raise ChatRateLimitError(provider="anthropic", message=f"Rate limit. Detail: {error_text[:200]}") from e
        elif 400 <= status_code < 500: raise ChatBadRequestError(provider="anthropic", message=f"Bad request ({status_code}). Detail: {error_text[:200]}") from e
        else: raise ChatProviderError(provider="anthropic", message=f"API error ({status_code}). Detail: {error_text[:200]}", status_code=status_code) from e
    except requests.exceptions.RequestException as e:
        raise ChatProviderError(provider="anthropic", message=f"Network error: {str(e)}", status_code=504) from e
    except Exception as e:
        logging.error(f"Anthropic: Unexpected error: {e}", exc_info=True)
        raise ChatProviderError(provider="anthropic", message=f"Unexpected error: {e}")
    finally:
        if session is not None:
            session.close()


def chat_with_cohere(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        topp: Optional[float] = None,
        topk: Optional[int] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        seed: Optional[int] = None,
        num_generations: Optional[int] = None, # Only for non-streaming
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        custom_prompt_arg: Optional[str] = None, # Kept for legacy, but focus on structured input
        app_config: Optional[Dict[str, Any]] = None,
):
    logging.debug(f"Cohere Chat: Request process starting for model '{model}' (Streaming: {streaming})")
    loaded_config_data = app_config or load_and_log_configs()
    cohere_config = loaded_config_data.get('cohere_api', loaded_config_data.get('API', {}).get('cohere', {}))

    final_api_key = api_key or cohere_config.get('api_key')
    if not final_api_key:
        raise ChatAuthenticationError(provider="cohere", message="Cohere API key is missing.")
    logging.debug("Cohere: Using configured API key")

    final_model = model or cohere_config.get('model', 'command-r')
    resolved_temp_from_cfg = cohere_config.get('temperature')
    current_temp = temp if temp is not None else _safe_cast(resolved_temp_from_cfg, float, None)
    resolved_p_cfg = cohere_config.get('top_p')
    if resolved_p_cfg is None:
        resolved_p_cfg = cohere_config.get('p')
    current_p = topp if topp is not None else _safe_cast(resolved_p_cfg, float, None)
    resolved_k_cfg = cohere_config.get('top_k')
    if resolved_k_cfg is None:
        resolved_k_cfg = cohere_config.get('k')
    current_k = topk if topk is not None else _safe_cast(resolved_k_cfg, int, None)
    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(cohere_config.get('max_tokens'), int, None)
    current_stop_sequences = stop_sequences if stop_sequences is not None else cohere_config.get('stop_sequences')
    current_seed = seed if seed is not None else _safe_cast(cohere_config.get('seed'), int, None)
    current_frequency_penalty = frequency_penalty if frequency_penalty is not None else _safe_cast(
        cohere_config.get('frequency_penalty'), float, None)
    current_presence_penalty = presence_penalty if presence_penalty is not None else _safe_cast(
        cohere_config.get('presence_penalty'), float, None)
    current_tools = tools if tools is not None else cohere_config.get('tools')
    current_num_generations = num_generations if num_generations is not None else _safe_cast(
        cohere_config.get('num_generations'), int, None)

    api_base_url = cohere_config.get('api_base_url', 'https://api.cohere.com').rstrip('/')
    # Using /v1/chat is standard for Cohere's current Chat API
    COHERE_CHAT_URL = f"{api_base_url}/v1/chat"

    # Timeout for each attempt, retries will extend total possible time
    timeout_seconds = _safe_cast(cohere_config.get('api_timeout'), float, 180.0) # Increased default
    # For streaming, timeout usually applies to establishing connection and time between chunks.
    # The session timeout below will handle per-try timeout.

    headers = {
        "Authorization": f"Bearer {final_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if streaming else "application/json",
        # Consider using a more recent API version or removing if not strictly needed, to get Cohere's latest defaults
        "Cohere-Version": cohere_config.get('api_version_date', "2024-05-13")
    }

    chat_history_for_cohere = []
    current_user_message_str = ""
    preamble_str = system_prompt or "" # 'preamble' is Cohere's term for system prompt

    temp_messages = list(input_data) # Make a mutable copy

    if not preamble_str and temp_messages and temp_messages[0]['role'] == 'system':
        preamble_str = temp_messages.pop(0)['content']
        logging.debug(f"Cohere: Using system message from input_data as preamble: '{preamble_str[:100]}...'")

    if not temp_messages: # Ensure there are messages left after potential preamble extraction
        # If custom_prompt_arg is provided and meaningful as a user query, consider using it.
        # For now, raising an error if no user/assistant messages remain.
        if custom_prompt_arg:
            current_user_message_str = custom_prompt_arg
            logging.warning("Cohere: No user/assistant messages in input_data, using custom_prompt_arg as user message.")
        else:
            raise ChatBadRequestError(provider="cohere",
                                      message="No user/assistant messages found for Cohere chat after processing system message.")
    elif temp_messages[-1]['role'] == 'user':
        last_msg_content = temp_messages[-1]['content']
        # Handle cases where content might be a list (e.g. multimodal, though Cohere handles this differently)
        if isinstance(last_msg_content, list): # Assuming OpenAI structure with type:text
            current_user_message_str = next((part['text'] for part in last_msg_content if part.get('type') == 'text'), "")
        else:
            current_user_message_str = str(last_msg_content)
        chat_history_for_cohere = temp_messages[:-1] # All but the last user message
    else: # Last message is not 'user', problematic for Cohere's /chat
        current_user_message_str = custom_prompt_arg or "Please respond." # Fallback user message
        chat_history_for_cohere = temp_messages # Keep all as history, and append the placeholder user message
        logging.warning(
            f"Cohere: Last message in payload was not 'user'. Using fallback user message: '{current_user_message_str}'.")

    # Append custom_prompt_arg to the current user message if it exists
    if custom_prompt_arg and current_user_message_str != custom_prompt_arg: # Avoid duplication if already used as fallback
        current_user_message_str += f"\n{custom_prompt_arg}"
        logging.debug(f"Cohere: Appended custom_prompt_arg to current user message.")


    if not current_user_message_str.strip():
        raise ChatBadRequestError(provider="cohere", message="Current user message for Cohere is empty after processing.")

    transformed_history = []
    for msg in chat_history_for_cohere:
        role = msg.get('role', '').lower()
        content = msg.get('content', '')
        if isinstance(content, list): # Extract text if content is a list of parts
            content = next((part['text'] for part in content if part.get('type') == 'text'), "")

        if role == "user":
            transformed_history.append({"role": "USER", "message": str(content)}) # Cohere uses "USER"
        elif role == "assistant":
            transformed_history.append({"role": "CHATBOT", "message": str(content)}) # Cohere uses "CHATBOT"
        # System messages are handled by preamble

    payload: Dict[str, Any] = {
        "model": final_model,
        "message": current_user_message_str
    }
    # Add parameters to payload only if they are not None or have meaningful values
    if transformed_history: payload["chat_history"] = transformed_history
    if preamble_str: payload["preamble"] = preamble_str
    if current_temp is not None: payload["temperature"] = current_temp
    if current_p is not None: payload["p"] = current_p
    if current_k is not None: payload["k"] = current_k
    if current_max_tokens is not None: payload["max_tokens"] = current_max_tokens
    if current_stop_sequences: payload["stop_sequences"] = current_stop_sequences
    if current_seed is not None: payload["seed"] = current_seed
    if current_frequency_penalty is not None: payload["frequency_penalty"] = current_frequency_penalty
    if current_presence_penalty is not None: payload["presence_penalty"] = current_presence_penalty
    if current_tools: payload["tools"] = current_tools  # Assuming 'tools' is already in Cohere's expected format

    if streaming:
        payload["stream"] = True
    else:
        # For non-streaming, 'stream: false' can be in payload or omitted.
        # Cohere's API defaults to non-streaming if 'stream' is not true.
        # To be explicit, we can add it.
        payload["stream"] = False
        if current_num_generations is not None:
            if current_num_generations > 0:
                payload["num_generations"] = current_num_generations
            else:
                logging.warning("Cohere: 'num_generations' must be > 0. Ignoring.")


    cohere_payload_metadata = _sanitize_payload_for_logging(
        payload,
        message_keys=("chat_history",),
        text_keys=("message", "preamble"),
    )
    logging.debug(f"Cohere request metadata: {cohere_payload_metadata}")
    logging.debug(f"Cohere Request URL: {COHERE_CHAT_URL}")

    # --- Retry Mechanism ---
    session = create_session_with_retries(
        total=_safe_cast(cohere_config.get('api_retries'), int, 3),
        backoff_factor=_safe_cast(cohere_config.get('api_retry_delay'), float, 1.0),
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    # --- End Retry Mechanism ---

    try:
        if streaming:
            # For streaming, the session.post will use the retry for initial connection.
            # The timeout applies to each attempt for connection and then for pauses in stream.
            response = session.post(COHERE_CHAT_URL, headers=headers, json=payload, stream=True, timeout=timeout_seconds)
            response.raise_for_status()  # Check for HTTP errors on initial connection
            logging.debug("Cohere: Streaming response connection established.")
            session_handle = session
            response_handle = response

            def stream_generator_cohere_text_chunks(response_iterator):
                stream_properly_closed = False
                try:
                    for line_bytes in response_iterator:
                        if not line_bytes:
                            continue
                        # Handle bytes or str from iter_lines()
                        decoded_line = (
                            line_bytes.decode('utf-8', errors='replace')
                            if isinstance(line_bytes, (bytes, bytearray))
                            else str(line_bytes)
                        )
                        decoded_line = decoded_line.strip()
                        if not decoded_line:
                            continue

                        # Cohere stream uses event+data pairs where data JSON contains event_type
                        if decoded_line.startswith("data:"):
                            json_data_str = decoded_line[len("data:"):].strip()
                            if not json_data_str:
                                continue
                            try:
                                cohere_event = json.loads(json_data_str)
                            except json.JSONDecodeError:
                                logging.warning(f"Cohere Stream: JSON decode error for data: '{json_data_str}'")
                                continue

                            event_type = cohere_event.get("event_type")
                            if event_type == "text-generation":
                                text_chunk = cohere_event.get("text")
                                if text_chunk:
                                    yield openai_delta_chunk(str(text_chunk))
                            elif event_type == "stream-end":
                                stream_properly_closed = True
                                yield sse_done()
                                return
                            else:
                                # stream-start or other events: ignore
                                continue
                        else:
                            # Plain text fallback - wrap as OpenAI-style delta
                            yield openai_delta_chunk(decoded_line)

                except requests.exceptions.ChunkedEncodingError as e:
                    logging.warning(f"Cohere stream: ChunkedEncodingError: {e}")
                    yield sse_data({"error": {"message": f"Stream connection error: {str(e)}", "type": "cohere_stream_error"}})
                except Exception as e_stream:
                    logging.error(f"Cohere stream: Error during streaming: {e_stream}", exc_info=True)
                    yield sse_data({"error": {"message": f"Stream iteration error: {str(e_stream)}", "type": "cohere_stream_error"}})
                finally:
                    for tail in finalize_stream(response_handle, done_already=stream_properly_closed):
                        yield tail
                    try:
                        session_handle.close()
                    except Exception:
                        pass

            session = None  # Prevent outer finally from closing before the generator finishes
            return stream_generator_cohere_text_chunks(response_handle.iter_lines())
        else:  # Non-streaming
            # The session.post will use the retry strategy and timeout for each attempt.
            response = session.post(COHERE_CHAT_URL, headers=headers, json=payload, stream=False, timeout=timeout_seconds)
            # No params={"stream": "false"} needed; payload["stream"] = False handles it.
            response.raise_for_status() # Will raise HTTPError for bad responses (4xx or 5xx) after retries
            response_data = response.json()
            logging.debug(f"Cohere non-streaming response data: {json.dumps(response_data, indent=2)}")

            # ---- Standard OpenAI-like Response Mapping ----
            # Based on Cohere /v1/chat non-streaming response structure:
            # { "text": "...", "generation_id": "...", "citations": [...], "documents": [...],
            #   "is_search_required": bool, "search_queries": [...], "search_results": [...],
            #   "finish_reason": "...", "tool_calls": [...], "chat_history": [...], (returned chat history)
            #   "meta": { "api_version": {...}, "billed_units": {"input_tokens": X, "output_tokens": Y}}}

            chat_id = response_data.get("generation_id", f"chatcmpl-cohere-{time.time_ns()}")
            created_timestamp = int(time.time())
            choices_payload = []
            finish_reason = response_data.get("finish_reason", "stop") # Default, Cohere provides this

            if response_data.get("text"): # Standard text response
                choices_payload.append({
                    "message": {"role": "assistant", "content": response_data["text"]},
                    "finish_reason": finish_reason, "index": 0
                })
            elif response_data.get("tool_calls"): # Tool usage
                openai_like_tool_calls = []
                for tc in response_data.get("tool_calls", []):
                    openai_like_tool_calls.append({
                        "id": f"call_{tc.get('name', 'tool')}_{time.time_ns()}",
                        "type": "function", # Assuming Cohere tools map to functions
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("parameters", {}))
                        }
                    })
                choices_payload.append({
                    "message": {"role": "assistant", "content": None, "tool_calls": openai_like_tool_calls},
                    "finish_reason": "tool_calls", "index": 0
                })
            else: # Fallback for unexpected empty response
                logging.warning(f"Cohere non-streaming response missing 'text' or 'tool_calls': {response_data}")
                choices_payload.append({
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": finish_reason, "index": 0
                })

            usage_data = None
            meta = response_data.get("meta")
            if meta and meta.get("billed_units"):
                billed_units = meta["billed_units"]
                prompt_tokens = billed_units.get("input_tokens")
                completion_tokens = billed_units.get("output_tokens")
                # search_units = billed_units.get("search_units") # if you track this
                if prompt_tokens is not None and completion_tokens is not None:
                    usage_data = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens
                    }

            openai_compatible_response = {
                "id": chat_id, "object": "chat.completion", "created": created_timestamp,
                "model": final_model, "choices": choices_payload,
            }
            if usage_data: openai_compatible_response["usage"] = usage_data
            return openai_compatible_response

    except requests.exceptions.HTTPError as e:
        status_code = getattr(e.response, 'status_code', 500)
        error_text = getattr(e.response, 'text', str(e))
        logging.error(f"Cohere API call HTTPError to {COHERE_CHAT_URL} status {status_code}. Details: {repr(error_text[:500])}", exc_info=False)
        if status_code == 401:
            raise ChatAuthenticationError(provider="cohere", message=f"Authentication failed. Detail: {error_text[:200]}")
        elif status_code == 429:
            raise ChatRateLimitError(provider="cohere", message=f"Rate limit exceeded. Detail: {error_text[:200]}")
        elif 400 <= status_code < 500:
            raise ChatBadRequestError(provider="cohere", message=f"Bad request (Status {status_code}). Detail: {error_text[:200]}")
        else: # 5xx
            raise ChatProviderError(provider="cohere", message=f"Server error (Status {status_code}). Detail: {error_text[:200]}", status_code=status_code)
    except requests.exceptions.RequestException as e: # Includes ReadTimeout, ConnectionError etc.
        logging.error(f"Cohere API request failed (network error) for {COHERE_CHAT_URL}: {e}", exc_info=True)
        # This will catch the ReadTimeout after retries are exhausted
        raise ChatProviderError(provider="cohere", message=f"Network error after retries: {e}", status_code=504) # 504 for gateway timeout like
    except Exception as e:
        logging.error(f"Cohere API call: Unexpected error: {e}", exc_info=True)
        if not isinstance(e, ChatAPIError):
            raise ChatAPIError(provider="cohere", message=f"Unexpected error in Cohere API call: {e}")
        else:
            raise
    finally:
        if session: # Ensure session is closed
            session.close()


def chat_with_deepseek(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        topp: Optional[float] = None,  # top_p
        # New OpenAI-compatible params for DeepSeek
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        response_format: Optional[Dict[str, str]] = None,  # If supported
        n: Optional[int] = None,  # If supported
        user: Optional[str] = None,  # If supported
        tools: Optional[List[Dict[str, Any]]] = None,  # If supported
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,  # If supported
        logit_bias: Optional[Dict[str, float]] = None,  # If supported
        custom_prompt_arg: Optional[str] = None,  # Legacy
        app_config: Optional[Dict[str, Any]] = None,
):
    loaded_config_data = app_config or load_and_log_configs()
    deepseek_config = loaded_config_data.get('deepseek_api', {})
    final_api_key = api_key or deepseek_config.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="deepseek", message="DeepSeek API Key required.")

    # ... (logging key, model, temp, streaming, top_p setup) ...
    logging.debug("DeepSeek: Using configured API key")
    # Strip provider prefix if present (e.g., "deepseek/deepseek-chat" -> "deepseek-chat")
    if model and '/' in model:
        model = model.split('/', 1)[1]
    current_model = model or deepseek_config.get('model', 'deepseek-chat')  # Or deepseek-coder
    logging.info(f"DeepSeek: Received model='{model}', config model='{deepseek_config.get('model')}', using='{current_model}'")
    current_temp = temp if temp is not None else _safe_cast(deepseek_config.get('temperature'), float, 0.1)
    current_top_p = topp  # Deepseek uses top_p
    current_streaming_cfg = deepseek_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else \
        (str(current_streaming_cfg).lower() == 'true' if isinstance(current_streaming_cfg, str) else bool(
            current_streaming_cfg))

    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(deepseek_config.get('max_tokens'), int)

    api_messages = []
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    headers = {'Authorization': f'Bearer {final_api_key}', 'Content-Type': 'application/json'}
    data = {
        "model": current_model, "messages": api_messages, "stream": current_streaming,
    }
    if current_temp is not None: data["temperature"] = current_temp
    if current_top_p is not None: data["top_p"] = current_top_p
    if current_max_tokens is not None: data["max_tokens"] = current_max_tokens
    if seed is not None: data["seed"] = seed
    if stop is not None: data["stop"] = stop
    if logprobs is not None: data["logprobs"] = logprobs  # DeepSeek uses 'logprobs' (boolean)
    if top_logprobs is not None and data.get("logprobs"): data["top_logprobs"] = top_logprobs
    if presence_penalty is not None: data["presence_penalty"] = presence_penalty
    if frequency_penalty is not None: data["frequency_penalty"] = frequency_penalty
    if response_format is not None: data["response_format"] = response_format
    if n is not None: data["n"] = n
    if user is not None: data["user"] = user
    if tools is not None: data["tools"] = tools
    _apply_tool_choice(data, tools, tool_choice)
    if logit_bias is not None: data["logit_bias"] = logit_bias

    api_url = deepseek_config.get('api_base_url', 'https://api.deepseek.com').rstrip('/') + '/chat/completions'
    # Log the actual model being sent
    logging.info(f"DeepSeek: Sending model='{current_model}' to API")
    deepseek_metadata = _sanitize_payload_for_logging(data)
    logging.debug(f"DeepSeek request metadata: {deepseek_metadata}")

    try:
        if current_streaming:
            session = create_session_with_retries(
                total=_safe_cast(deepseek_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(deepseek_config.get('api_retry_delay'), float, 1.0),
            )
            stream_timeout = _safe_cast(deepseek_config.get('api_timeout'), float, 90.0)
            try:
                response = session.post(api_url, headers=headers, json=data, stream=True, timeout=stream_timeout)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            def stream_generator():
                    done_sent = False
                    try:
                        for raw_line in response.iter_lines(decode_unicode=True):
                            if not raw_line:
                                continue
                            if is_done_line(raw_line):
                                done_sent = True
                            normalized = normalize_provider_line(raw_line)
                            if normalized is None:
                                continue
                            yield normalized
                        if not done_sent:
                            done_sent = True
                            yield sse_done()
                    except requests.exceptions.ChunkedEncodingError as e:
                        logging.error(f"DeepSeek: ChunkedEncodingError during stream: {e}", exc_info=True)
                        yield sse_data({'error': {'message': f'Stream connection error: {str(e)}', 'type': 'deepseek_stream_error'}})
                    except Exception as e:
                        logging.error(f"DeepSeek: Stream iteration error: {e}", exc_info=True)
                        yield sse_data({'error': {'message': f'Stream iteration error: {str(e)}', 'type': 'deepseek_stream_error'}})
                    finally:
                        try:
                            for tail in finalize_stream(response, done_already=done_sent):
                                yield tail
                        finally:
                            try:
                                session.close()
                            except Exception:
                                pass

            return stream_generator()
        else:
            session = create_session_with_retries(
                total=_safe_cast(deepseek_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(deepseek_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=data, timeout=120)
                response.raise_for_status()
                try:
                    return response.json()
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
            finally:
                session.close()
    except requests.exceptions.HTTPError as e:
        _raise_chat_error_from_http("deepseek", e)
    except Exception as e:  # ... error handling ...
        raise ChatProviderError(provider="deepseek", message=f"Unexpected error: {e}")


def chat_with_google(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,  # -> system_instruction
        temp: Optional[float] = None,  # -> temperature
        streaming: Optional[bool] = False,
        topp: Optional[float] = None,  # -> topP
        topk: Optional[int] = None,  # -> topK
        max_output_tokens: Optional[int] = None,  # from max_tokens
        stop_sequences: Optional[List[str]] = None,  # from stop
        candidate_count: Optional[int] = None,  # from n
        response_format: Optional[Dict[str, str]] = None,  # for response_mime_type
        # Gemini doesn't directly take seed, user_id, logit_bias, presence/freq_penalty, logprobs via REST in the same way.
        # Tools are handled via a 'tools' field in the payload, with a specific format.
        tools: Optional[List[Dict[str, Any]]] = None,  # Gemini 'tools' config
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    loaded_config_data = app_config or load_and_log_configs()
    google_config = loaded_config_data.get('google_api', {})
    # ... (api key, model, temp, streaming, topP, topK setup) ...
    final_api_key = api_key or google_config.get('api_key')
    if not final_api_key: raise ChatConfigurationError(provider="google", message="Google API Key required.")
    current_model = model or google_config.get('model', 'gemini-1.5-flash-latest')
    # ... other param resolutions ...
    current_streaming_cfg = google_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else \
        (str(current_streaming_cfg).lower() == 'true' if isinstance(current_streaming_cfg, str) else bool(
            current_streaming_cfg))

    current_temp = temp if temp is not None else _safe_cast(google_config.get('temperature'), float, None)
    resolved_top_p_cfg = google_config.get('top_p', google_config.get('topP'))
    current_top_p = topp if topp is not None else _safe_cast(resolved_top_p_cfg, float, None)
    resolved_top_k_cfg = google_config.get('top_k', google_config.get('topK'))
    current_top_k = topk if topk is not None else _safe_cast(resolved_top_k_cfg, int, None)
    resolved_max_tokens_cfg = google_config.get('max_output_tokens', google_config.get('max_tokens'))
    current_max_output_tokens = max_output_tokens if max_output_tokens is not None else _safe_cast(
        resolved_max_tokens_cfg, int, None)
    current_stop_sequences = stop_sequences if stop_sequences is not None else google_config.get('stop_sequences')
    resolved_candidate_count_cfg = google_config.get('candidate_count', google_config.get('n'))
    current_candidate_count = candidate_count if candidate_count is not None else _safe_cast(
        resolved_candidate_count_cfg, int, None)
    current_tools = tools if tools is not None else google_config.get('tools')
    effective_response_format = response_format or google_config.get('response_format')

    gemini_contents = []
    # ... (message transformation from input_data to gemini_contents) ...
    for msg in input_data:
        role = msg.get("role")
        content = msg.get("content")
        gemini_role = "user" if role == "user" else "model" if role == "assistant" else None
        if not gemini_role: continue
        gemini_parts = []
        if isinstance(content, str):
            gemini_parts.append({"text": content})
        elif isinstance(content, list):
            for part_obj in content:
                if part_obj.get("type") == "text":
                    gemini_parts.append({"text": part_obj.get("text", "")})
                elif part_obj.get("type") == "image_url":
                    parsed_image = _parse_data_url_for_multimodal(part_obj.get("image_url", {}).get("url", ""))
                    if parsed_image: gemini_parts.append(
                        {"inline_data": {"mime_type": parsed_image[0], "data": parsed_image[1]}})
        if gemini_parts: gemini_contents.append({"role": gemini_role, "parts": gemini_parts})

    generation_config = {}
    if current_temp is not None: generation_config["temperature"] = current_temp
    if current_top_p is not None: generation_config["topP"] = current_top_p
    if current_top_k is not None: generation_config["topK"] = current_top_k
    if current_max_output_tokens is not None: generation_config["maxOutputTokens"] = current_max_output_tokens
    if current_stop_sequences is not None: generation_config["stopSequences"] = current_stop_sequences
    if current_candidate_count is not None: generation_config["candidateCount"] = current_candidate_count
    if effective_response_format and effective_response_format.get("type") == "json_object":
        generation_config["responseMimeType"] = "application/json"

    payload = {"contents": gemini_contents}
    if generation_config: payload["generationConfig"] = generation_config
    if system_message: payload["system_instruction"] = {"parts": [{"text": system_message}]}
    if current_tools: payload["tools"] = current_tools  # Assuming 'tools' is in Gemini's specific format

    stream_suffix = ":streamGenerateContent?alt=sse" if current_streaming else ":generateContent"
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}{stream_suffix}"
    headers = {'x-goog-api-key': final_api_key, 'Content-Type': 'application/json'}
    gemini_payload_metadata = _sanitize_payload_for_logging(
        payload,
        message_keys=("contents",),
    )
    logging.debug(f"Google Gemini request metadata: {gemini_payload_metadata}")

    try:
        # ... (retry logic) ...
        session = None
        response = None
        try:
            session = create_session_with_retries(
                total=_safe_cast(google_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(google_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 503],
                allowed_methods=["POST"],
            )
            response = session.post(api_url, headers=headers, json=payload, stream=current_streaming, timeout=180)
            response.raise_for_status()

            if current_streaming:
                logging.debug("Google Gemini: Streaming response received.")
                session_ref = session
                response_ref = response
                tool_call_index = 0

                def stream_generator():
                    nonlocal tool_call_index
                    done_sent = False
                    try:
                        for raw in response_ref.iter_lines():
                            if not raw:
                                continue
                            try:
                                line = raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else str(raw)
                            except Exception:
                                line = str(raw)
                            if line and line.strip().startswith('data:'):
                                json_str = line.strip()[len('data:'):]
                                clean_chunk = json_str.strip()
                                if clean_chunk.lower() == "[done]":
                                    if not done_sent:
                                        done_sent = True
                                        yield sse_done()
                                    continue
                                try:
                                    data_chunk_outer = json.loads(json_str)
                                    data_chunks_to_process = data_chunk_outer if isinstance(data_chunk_outer, list) else [
                                        data_chunk_outer]

                                    for data_chunk in data_chunks_to_process:
                                        chunk_text = ""
                                        finish_reason = None
                                        tool_calls_delta: List[Dict[str, Any]] = []

                                        candidates = data_chunk.get('candidates', [])
                                        if candidates:
                                            candidate = candidates[0]
                                            if candidate.get('content', {}).get('parts', []):
                                                for part in candidate['content']['parts']:
                                                    if 'text' in part:
                                                        chunk_text += part.get('text', '')
                                                    if 'functionCall' in part:
                                                        logging.debug(
                                                            f"Gemini Stream: Received functionCall part: {part['functionCall']}")
                                                        function_call = part['functionCall']
                                                        tool_call_entry = {
                                                            "index": tool_call_index,
                                                            "id": function_call.get("id") or f"call_gemini_{tool_call_index}_{time.time_ns()}",
                                                            "type": "function",
                                                            "function": {
                                                                "name": function_call.get("name"),
                                                                "arguments": json.dumps(function_call.get("args", {}))
                                                            }
                                                        }
                                                        tool_call_index += 1
                                                        tool_calls_delta.append(tool_call_entry)
                                            raw_finish_reason = candidate.get("finishReason")
                                            if raw_finish_reason:
                                                finish_reason_map = {"MAX_TOKENS": "length", "STOP": "stop",
                                                                     "SAFETY": "content_filter",
                                                                     "RECITATION": "content_filter", "OTHER": "error",
                                                                     "TOOL_CODE_NOT_FOUND": "error"}
                                                finish_reason = finish_reason_map.get(
                                                    raw_finish_reason, raw_finish_reason.lower())

                                        if chunk_text or tool_calls_delta:
                                            delta_payload: Dict[str, Any] = {}
                                            if chunk_text:
                                                delta_payload["content"] = chunk_text
                                            if tool_calls_delta:
                                                delta_payload["tool_calls"] = tool_calls_delta
                                            sse_chunk = {'choices': [{'delta': delta_payload,
                                                                      "finish_reason": finish_reason if finish_reason else None,
                                                                      "index": 0}]}
                                            yield sse_data(sse_chunk)
                                        elif finish_reason:
                                            sse_chunk = {'choices': [{'delta': {}, "finish_reason": finish_reason, "index": 0}]}
                                            yield sse_data(sse_chunk)
                                except json.JSONDecodeError:
                                    logging.warning(f"Google Gemini: Could not decode JSON line: {json_str}")
                        # Ensure we emit [DONE] exactly once
                        if not done_sent:
                            done_sent = True
                            yield sse_done()
                    except requests.exceptions.ChunkedEncodingError as e_chunk:
                        logging.error(f"Google Gemini stream: ChunkedEncodingError: {e_chunk}")
                        yield sse_data({"error": {"message": f"Stream connection error: {str(e_chunk)}", "type": "gemini_stream_error"}})
                    except Exception as e_stream:
                        logging.error(f"Google Gemini stream: iteration error: {e_stream}", exc_info=True)
                        yield sse_data({"error": {"message": f"Stream iteration error: {str(e_stream)}", "type": "gemini_stream_error"}})
                    finally:
                        for tail in finalize_stream(response_ref, done_already=done_sent):
                            yield tail
                        try:
                            session_ref.close()
                        except Exception:
                            pass

                session = None
                return stream_generator()
            else:
                response_data = response.json()
                logging.debug("Google Gemini: Non-streaming request successful.")
                assistant_content = ""
                finish_reason = "unknown"
                tool_calls = None

                if response_data.get("candidates"):
                    candidate = response_data["candidates"][0]
                    if candidate.get("content", {}).get("parts"):
                        parts = candidate["content"]["parts"]
                        for part in parts:
                            if "text" in part:
                                assistant_content += part.get("text", "")
                            if "functionCall" in part:
                                if tool_calls is None:
                                    tool_calls = []
                                tool_calls.append({
                                    "id": f"call_gemini_{time.time_ns()}_{len(tool_calls)}",
                                    "type": "function",
                                    "function": {
                                        "name": part["functionCall"].get("name"),
                                        "arguments": json.dumps(part["functionCall"].get("args", {}))
                                    }
                                })

                    raw_finish_reason = candidate.get("finishReason")
                    if raw_finish_reason:
                        finish_reason_map = {"MAX_TOKENS": "length", "STOP": "stop", "SAFETY": "content_filter",
                                             "RECITATION": "content_filter", "OTHER": "error",
                                             "TOOL_CODE_NOT_FOUND": "error", "FUNCTION_CALL": "tool_calls"}
                        finish_reason = finish_reason_map.get(raw_finish_reason, raw_finish_reason.lower())

                message_content = {"role": "assistant", "content": assistant_content.strip()}
                if tool_calls:
                    message_content["tool_calls"] = tool_calls
                    if not assistant_content.strip():
                        message_content["content"] = None

                normalized_response = {
                    "id": f"gemini-{time.time_ns()}", "object": "chat.completion", "created": int(time.time()),
                    "model": current_model,
                    "choices": [{"index": 0, "message": message_content, "finish_reason": finish_reason}],
                    "usage": {
                        "prompt_tokens": response_data.get("usageMetadata", {}).get("promptTokenCount"),
                        "completion_tokens": response_data.get("usageMetadata", {}).get("candidatesTokenCount"),
                        "total_tokens": response_data.get("usageMetadata", {}).get("totalTokenCount")}
                }
                return normalized_response
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
    except requests.exceptions.HTTPError as e:
        _raise_chat_error_from_http("google", e)
    except Exception as e:  # ... error handling ...
        raise ChatProviderError(provider="google", message=f"Unexpected error: {e}")



# https://console.groq.com/docs/quickstart


def chat_with_qwen(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        maxp: Optional[float] = None,
        streaming: Optional[bool] = False,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    """OpenAI-compatible chat completions against the commercial Qwen API (DashScope)."""
    loaded_config_data = app_config or load_and_log_configs()
    qwen_config = loaded_config_data.get('qwen_api', {}) if loaded_config_data else {}
    final_api_key = api_key or qwen_config.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="qwen", message="Qwen API Key required.")
    base_url = (qwen_config.get('api_base_url') or 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1').rstrip('/')
    current_model = model or qwen_config.get('model', 'qwen-plus')
    current_temp = temp if temp is not None else _safe_cast(qwen_config.get('temperature'), float, 0.7)
    current_top_p = maxp if maxp is not None else _safe_cast(qwen_config.get('top_p'), float, 0.8)
    streaming_cfg = qwen_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else (
        str(streaming_cfg).lower() == 'true' if isinstance(streaming_cfg, str) else bool(streaming_cfg)
    )
    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(qwen_config.get('max_tokens'), int)
    api_timeout = _safe_cast(qwen_config.get('api_timeout'), float, 90.0)
    api_retries = _safe_cast(qwen_config.get('api_retries'), int, 3)
    retry_delay = _safe_cast(qwen_config.get('api_retry_delay'), float, 1.0)

    api_messages: List[Dict[str, Any]] = []
    if system_message and not any(msg.get("role") == "system" for msg in input_data):
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    headers = {
        'Authorization': f'Bearer {final_api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    payload: Dict[str, Any] = {"model": current_model, "messages": api_messages, "stream": current_streaming}
    if current_temp is not None:
        payload["temperature"] = current_temp
    if current_top_p is not None:
        payload["top_p"] = current_top_p
    if current_max_tokens is not None:
        payload["max_tokens"] = current_max_tokens
    if seed is not None:
        payload["seed"] = seed
    if stop is not None:
        payload["stop"] = stop
    if response_format is not None:
        payload["response_format"] = response_format
    if n is not None:
        payload["n"] = n
    if user is not None:
        payload["user"] = user
    if tools is not None:
        payload["tools"] = tools
    if tool_choice == "none":
        payload["tool_choice"] = "none"
    elif tool_choice is not None and tools is not None:
        payload["tool_choice"] = tool_choice
    if logit_bias is not None:
        payload["logit_bias"] = logit_bias
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if logprobs is not None:
        payload["logprobs"] = logprobs
    if top_logprobs is not None and payload.get("logprobs"):
        payload["top_logprobs"] = top_logprobs
    if custom_prompt_arg:
        logging.warning("Qwen: 'custom_prompt_arg' was provided but is unused when message payload is supplied.")

    api_url = f"{base_url}/chat/completions"
    payload_metadata = {k: v for k, v in payload.items() if k != "messages"}
    logging.debug(f"Qwen API request target: {api_url}")
    logging.debug(f"Qwen request payload metadata: {payload_metadata}")

    try:
        if current_streaming:
            session = create_session_with_retries(
                total=api_retries if api_retries is not None else 3,
                backoff_factor=retry_delay if retry_delay is not None else 1.0,
            )
            try:
                response = session.post(api_url, headers=headers, json=payload, stream=True, timeout=api_timeout or 120)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            def stream_generator():
                    done_sent = False
                    try:
                        for raw_line in response.iter_lines(decode_unicode=True):
                            if not raw_line:
                                continue
                            if is_done_line(raw_line):
                                done_sent = True
                            normalized = normalize_provider_line(raw_line)
                            if normalized is None:
                                continue
                            yield normalized
                        # Ensure final DONE sentinel only if not seen
                        if not done_sent:
                            done_sent = True
                            yield sse_done()
                    except requests.exceptions.ChunkedEncodingError as stream_err:
                        logging.error(f"Qwen: ChunkedEncodingError during stream: {stream_err}", exc_info=True)
                        yield sse_data({"error": {"message": f"Stream connection error: {stream_err}", "type": "qwen_stream_error"}})
                    except Exception as stream_err:
                        logging.error(f"Qwen: Error during stream iteration: {stream_err}", exc_info=True)
                        yield sse_data({"error": {"message": f"Stream iteration error: {stream_err}", "type": "qwen_stream_error"}})
                    finally:
                        try:
                            for tail in finalize_stream(response, done_already=done_sent):
                                yield tail
                        finally:
                            try:
                                session.close()
                            except Exception:
                                pass

            return stream_generator()
        else:
            session = create_session_with_retries(
                total=api_retries if api_retries is not None else 3,
                backoff_factor=retry_delay if retry_delay is not None else 1.0,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=payload, timeout=api_timeout or 90)
                response.raise_for_status()
                try:
                    return response.json()
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
            finally:
                session.close()
    except requests.exceptions.HTTPError as e:
        status_code = None
        message = ""
        if e.response is not None:
            status_code = e.response.status_code
            logging.error(f"Qwen error response (status {status_code}): {repr(e.response.text)}")
            try:
                err_json = e.response.json()
                message = err_json.get("error", {}).get("message") or err_json.get("message") or ""
            except Exception:
                message = e.response.text or str(e)
        else:
            logging.error(f"Qwen HTTPError without response: {e}")
            message = str(e)
        if not message:
            message = "Qwen API error"
        if status_code in (400, 404, 422):
            raise ChatBadRequestError(provider="qwen", message=message)
        if status_code in (401, 403):
            raise ChatAuthenticationError(provider="qwen", message=message)
        if status_code == 429:
            raise ChatRateLimitError(provider="qwen", message=message)
        if status_code in (500, 502, 503, 504):
            raise ChatProviderError(provider="qwen", message=message, status_code=status_code)
        raise ChatAPIError(provider="qwen", message=message, status_code=status_code or 500)
    except requests.exceptions.RequestException as e:
        logging.error(f"Qwen request exception: {e}", exc_info=True)
        raise ChatProviderError(provider="qwen", message=f"Network error: {e}", status_code=504)
    except Exception as e:
        logging.error(f"Qwen unexpected error: {e}", exc_info=True)
        raise ChatProviderError(provider="qwen", message=f"Unexpected error: {e}")

def chat_with_groq(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        maxp: Optional[float] = None,  # top_p
        streaming: Optional[bool] = False,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,  # user_identifier
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        custom_prompt_arg: Optional[str] = None,  # Legacy
        app_config: Optional[Dict[str, Any]] = None,
):
    loaded_config_data = app_config or load_and_log_configs()
    groq_config = loaded_config_data.get('groq_api', {})
    final_api_key = api_key or groq_config.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="groq", message="Groq API Key required.")

    # ... (logging key, model, temp, streaming setup as before) ...
    logging.debug("Groq: Using configured API key")

    current_model = model or groq_config.get('model', 'llama3-8b-8192')
    current_temp = temp if temp is not None else _safe_cast(groq_config.get('temperature'), float, 0.2)
    current_top_p = maxp  # Groq uses top_p
    current_streaming_cfg = groq_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else \
        (str(current_streaming_cfg).lower() == 'true' if isinstance(current_streaming_cfg, str) else bool(
            current_streaming_cfg))

    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(groq_config.get('max_tokens'), int)

    api_messages = []
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    headers = {'Authorization': f'Bearer {final_api_key}', 'Content-Type': 'application/json'}
    data = {
        "model": current_model, "messages": api_messages, "stream": current_streaming,
    }
    if current_temp is not None: data["temperature"] = current_temp
    if current_top_p is not None: data["top_p"] = current_top_p
    if current_max_tokens is not None: data["max_tokens"] = current_max_tokens
    if seed is not None: data["seed"] = seed
    if stop is not None: data["stop"] = stop
    if response_format is not None: data["response_format"] = response_format
    if n is not None: data["n"] = n
    if user is not None: data["user"] = user
    if tools is not None: data["tools"] = tools
    _apply_tool_choice(data, tools, tool_choice)
    if logit_bias is not None: data["logit_bias"] = logit_bias
    if presence_penalty is not None: data["presence_penalty"] = presence_penalty
    if frequency_penalty is not None: data["frequency_penalty"] = frequency_penalty
    if logprobs is not None: data["logprobs"] = logprobs
    if top_logprobs is not None and data.get("logprobs") is True: data["top_logprobs"] = top_logprobs

    api_url = groq_config.get('api_base_url', 'https://api.groq.com/openai/v1').rstrip('/') + '/chat/completions'
    data_metadata = _sanitize_payload_for_logging(data)
    logging.debug(f"Groq request metadata: {data_metadata}")
    try:
        if current_streaming:
            session = create_session_with_retries(
                total=_safe_cast(groq_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(groq_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            stream_timeout = _safe_cast(groq_config.get('api_timeout'), float, 90.0)
            try:
                response = session.post(api_url, headers=headers, json=data, stream=True, timeout=stream_timeout)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            session_handle = session
            response_handle = response

            def stream_generator():
                done_sent = False
                try:
                    for raw_line in response_handle.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        if is_done_line(raw_line):
                            done_sent = True
                        normalized = normalize_provider_line(raw_line)
                        if normalized is None:
                            continue
                        yield normalized
                    if not done_sent:
                        done_sent = True
                        yield sse_done()
                except GeneratorExit:
                    if response_handle:
                        response_handle.close()
                    raise
                except requests.exceptions.ChunkedEncodingError as e:
                    logging.error(f"Groq: ChunkedEncodingError: {e}", exc_info=True)
                    yield sse_data({'error': {'message': f'Stream error: {str(e)}', 'type': 'groq_stream_error'}})
                except Exception as e:
                    logging.error(f"Groq: Stream iteration error: {e}", exc_info=True)
                    yield sse_data({'error': {'message': f'Stream iteration error: {str(e)}', 'type': 'groq_stream_error'}})
                finally:
                    for tail in finalize_stream(response_handle, done_already=done_sent):
                        yield tail
                    try:
                        session_handle.close()
                    except Exception:
                        pass

            return stream_generator()
        else:
            session = create_session_with_retries(
                total=_safe_cast(groq_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(groq_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=data, timeout=120)
                response.raise_for_status()
                try:
                    return response.json()
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
            finally:
                session.close()
    except requests.exceptions.HTTPError as e:
        _raise_chat_error_from_http("groq", e)
    except Exception as e:  # ... error handling ...
        raise ChatProviderError(provider="groq", message=f"Unexpected error: {e}")


def chat_with_huggingface(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,  # This is the model_id like "Org/ModelName"
        api_key: Optional[str] = None,
        system_message: Optional[str] = None, # Renamed from system_prompt for clarity if it maps to HF system
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None, # Maps to max_new_tokens for some TGI, or max_tokens for OpenAI compatible
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        num_return_sequences: Optional[int] = None,  # Mapped from 'n'
        user: Optional[str] = None, # OpenAI compatible user field
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None, # OpenAI compatible
        presence_penalty: Optional[float] = None, # OpenAI compatible name
        frequency_penalty: Optional[float] = None, # OpenAI compatible name
        logprobs: Optional[bool] = None, # OpenAI compatible name
        top_logprobs: Optional[int] = None, # OpenAI compatible name
        custom_prompt_arg: Optional[str] = None,  # Legacy
        app_config: Optional[Dict[str, Any]] = None,
):
    logging.debug(f"HuggingFace Chat: Request process starting for model '{model}' (Streaming: {streaming})")
    loaded_config_data = app_config or load_and_log_configs()
    hf_config = loaded_config_data.get('huggingface_api', loaded_config_data.get('API', {}).get('huggingface', {}))

    final_api_key = api_key or hf_config.get('api_key')
    if final_api_key:
        logging.debug("HuggingFace: Using configured API key")
    else:
        logging.warning("HuggingFace: API key is missing. Public Inference API or unsecured TGI assumed.")

    headers = {"Content-Type": "application/json"}
    if final_api_key:
        headers["Authorization"] = f"Bearer {final_api_key}"

    final_model_for_payload = model or hf_config.get('model_id') or hf_config.get('model')
    if not final_model_for_payload:
        raise ChatConfigurationError(provider="huggingface",
                                     message="HuggingFace model ID is required (must be passed as 'model' or configured).")
    logging.info(f"HuggingFace: Using model_id for payload: {final_model_for_payload}")

    # --- URL Construction ---
    api_url: str
    use_router_url_format_str = str(hf_config.get('use_router_url_format', "False")).lower()

    if use_router_url_format_str == "true":
        # This format explicitly puts the model in the URL path.
        # User must ensure router_base_url and model_id result in a valid endpoint.
        router_base = hf_config.get('router_base_url', 'https://router.huggingface.co/hf-inference').rstrip('/')
        model_path_part = final_model_for_payload.strip('/')
        chat_path = hf_config.get('api_chat_path', 'v1/chat/completions').lstrip('/')
        # Constructs URL like: {router_base}/models/{model_path_part}/{chat_path}
        api_url = f"{router_base}/models/{model_path_part}/{chat_path}"
        logging.info(f"HuggingFace: Using explicit 'use_router_url_format=true'. Target URL: {api_url}")
    else: # use_router_url_format is false, standard URL construction
        configured_api_base_url = hf_config.get('api_base_url')
        # Default chat path can be just "chat/completions" if base_url includes /v1, or "v1/chat/completions" if not.
        # Let's make the default api_chat_path more flexible.
        # If using the public HF API, base is /v1 and path is chat/completions.
        default_chat_path = 'chat/completions' if (configured_api_base_url and 'api-inference.huggingface.co/v1' in configured_api_base_url) else 'v1/chat/completions'
        chat_completions_path = hf_config.get('api_chat_path', default_chat_path).lstrip('/')

        if configured_api_base_url:
            # If api_base_url is configured, use it directly and append the chat_completions_path.
            # The model is expected to be in the payload.
            # If the endpoint needs the model_id in the path, configured_api_base_url should include it fully.
            api_url = f"{configured_api_base_url.rstrip('/')}/{chat_completions_path}"
            logging.info(f"HuggingFace: Using configured 'api_base_url' ('{configured_api_base_url}') and 'api_chat_path' ('{chat_completions_path}'). Target URL: {api_url}. Model is in payload.")
        else:
            # Fallback if no api_base_url is configured.
            # Use the public Hugging Face Inference API endpoint for OpenAI-like chat completions.
            default_hf_api_base = 'https://api-inference.huggingface.co/v1' # Base includes /v1
            default_chat_path_for_api_inference = 'chat/completions' # Path relative to /v1 base
            api_url = f"{default_hf_api_base.rstrip('/')}/{default_chat_path_for_api_inference}"
            logging.warning(
                f"HuggingFace: 'api_base_url' not configured. Defaulting to public Inference API endpoint: {api_url}. Model is in payload."
            )
    # --- End URL Construction ---

    final_temp = temp if temp is not None else _safe_cast(hf_config.get('temperature'), float, 0.7)
    # Ensure final_streaming is a boolean for the payload
    hf_config_streaming = hf_config.get('streaming', False)
    final_streaming_payload_val = streaming if streaming is not None else \
        (str(hf_config_streaming).lower() == 'true' if isinstance(hf_config_streaming, str) else bool(hf_config_streaming))


    # TGI uses max_new_tokens. OpenAI compatible layers might expect max_tokens.
    # If max_tokens is provided, prefer it. Otherwise, check hf_config for max_new_tokens or max_tokens
    final_max_val = max_tokens
    if final_max_val is None:
        final_max_val = _safe_cast(hf_config.get('max_tokens', hf_config.get('max_new_tokens')), int)


    api_messages = []
    # Handle system message: TGI usually wants it as the first message if no dedicated 'system' field in payload root
    # For OpenAI compatible /v1/chat/completions, system message is standard.
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data) # input_data should be correctly formatted by caller

    payload: Dict[str, Any] = {
        "model": final_model_for_payload, # Model ID is crucial for endpoints that multiplex
        "messages": api_messages,
        "stream": final_streaming_payload_val, # Use the boolean value
    }

    if final_temp is not None: payload["temperature"] = final_temp
    if top_p is not None: payload["top_p"] = top_p
    if top_k is not None: payload["top_k"] = top_k
    if final_max_val is not None:
        # Use "max_tokens" for OpenAI compatibility, TGI might map this or use "max_new_tokens"
        # Sticking to "max_tokens" if the endpoint is /v1/chat/completions
        payload["max_tokens"] = final_max_val
    if seed is not None: payload["seed"] = seed
    if stop is not None: payload["stop_sequences"] = stop if isinstance(stop, list) else [stop] # TGI often uses stop_sequences
    if response_format is not None: payload["response_format"] = response_format # For OpenAI compatible JSON mode

    if num_return_sequences is not None and not final_streaming_payload_val : payload["n"] = num_return_sequences
    if user is not None: payload["user"] = user
    if tools is not None: payload["tools"] = tools
    if tool_choice == "none":
        payload["tool_choice"] = "none"
    elif tool_choice is not None and tools is not None:
        payload["tool_choice"] = tool_choice
    if logit_bias is not None: payload["logit_bias"] = logit_bias
    if presence_penalty is not None: payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None: payload["frequency_penalty"] = frequency_penalty
    if logprobs is not None: payload["logprobs"] = logprobs
    if top_logprobs is not None and payload.get("logprobs"): payload["top_logprobs"] = top_logprobs


    # Remove None values from payload before sending, common practice
    payload = {k: v for k, v in payload.items() if v is not None}

    logging.debug(f"HuggingFace Final Payload (excluding messages, tools): {{ {', '.join(f'{k}: {v}' for k, v in payload.items() if k not in ['messages', 'tools'])} }}")
    if 'tools' in payload: logging.debug(f"HuggingFace Tools: {payload['tools']}")
    # Avoid logging sensitive header values (mask Authorization)
    try:
        masked_headers = {k: ("***" if k.lower() == "authorization" else v) for k, v in headers.items()}
        logging.debug(f"HuggingFace Headers: {masked_headers}")
    except Exception:
        logging.debug(f"HuggingFace Headers present: {list(headers.keys())}")

    timeout_seconds = _safe_cast(hf_config.get('api_timeout'), float, 120.0)
    # For streaming, timeout applies to initial connection and pauses between data.
    # Consider a tuple timeout (connect_timeout, read_timeout) for more control if needed.

    try:
        if final_streaming_payload_val:  # Check the boolean intended for payload
            logging.debug(f"HuggingFace: Posting streaming request to {api_url}")
            session = create_session_with_retries(
                total=_safe_cast(hf_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(hf_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=payload, stream=True, timeout=timeout_seconds)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            session_handle = session
            response_handle = response

            def stream_generator_huggingface():
                try:
                    for chunk in iter_sse_lines_requests(response_handle, decode_unicode=True, provider="huggingface"):
                        yield chunk
                    for tail in finalize_stream(response_handle, done_already=False):
                        yield tail
                finally:
                    try:
                        session_handle.close()
                    except Exception:
                        pass

            return stream_generator_huggingface()
        else: # Non-streaming
            logging.debug(f"HuggingFace: Posting non-streaming request to {api_url}")
            session = create_session_with_retries(
                total=_safe_cast(hf_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(hf_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=payload, timeout=timeout_seconds)
                response.raise_for_status()
                try:
                    return response.json()  # This should be an OpenAI compatible JSON response
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
            finally:
                session.close()

    except requests.exceptions.HTTPError as e:
        status_code = getattr(e.response, 'status_code', 500)
        error_text = getattr(e.response, 'text', str(e))
        logging.error(f"HuggingFace API call failed to {api_url} with status {status_code}. Details: {repr(error_text[:500])}", exc_info=False)
        if status_code == 401:
            raise ChatAuthenticationError(provider="huggingface", message=f"Authentication failed. Detail: {error_text[:200]}")
        elif status_code == 404: # Specifically handle 404 for URL/model issues
            raise ChatBadRequestError(provider="huggingface", message=f"Endpoint or Model not found (404) at {api_url}. Detail: {error_text[:200]}")
        elif status_code == 429:
            raise ChatRateLimitError(provider="huggingface", message=f"Rate limit exceeded. Detail: {error_text[:200]}")
        elif 400 <= status_code < 500: # Other 4xx
            raise ChatBadRequestError(provider="huggingface", message=f"Bad request (Status {status_code}) to {api_url}. Detail: {error_text[:200]}")
        else: # 5xx
            raise ChatProviderError(provider="huggingface", message=f"Server error (Status {status_code}) from {api_url}. Detail: {error_text[:200]}", status_code=status_code)
    except requests.exceptions.RequestException as e: # Covers DNS, Connection, Timeout errors
        logging.error(f"HuggingFace API request failed to {api_url} (network error): {e}", exc_info=True)
        raise ChatProviderError(provider="huggingface", message=f"Network error connecting to {api_url}: {e}", status_code=504) # 504 for timeout/gateway like
    except Exception as e:
        logging.error(f"HuggingFace API call to {api_url}: Unexpected error: {e}", exc_info=True)
        if not isinstance(e, ChatAPIError): # Avoid re-wrapping known chat errors
            raise ChatAPIError(provider="huggingface", message=f"Unexpected error in HuggingFace API call: {e}")
        else:
            raise # Re-raise if it's already a ChatAPIError subtype


def chat_with_mistral(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        topp: Optional[float] = None,
        max_tokens: Optional[int] = None,
        random_seed: Optional[int] = None,
        top_k: Optional[int] = None,
        safe_prompt: Optional[bool] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, str]] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    loaded_config_data = app_config or load_and_log_configs()
    mistral_config = loaded_config_data.get('mistral_api', {})
    final_api_key = api_key or mistral_config.get('api_key')
    if not final_api_key:
        raise ChatConfigurationError(provider="mistral", message="Mistral API Key required.")

    # ... (logging key, model, temp, streaming, top_p setup) ...
    logging.debug("Mistral: Using configured API key")
    current_model = model or mistral_config.get('model', 'mistral-large-latest')  # or mistral-small, mistral-medium
    current_temp = temp if temp is not None else _safe_cast(
        mistral_config.get('temperature'), float, 0.1)  # Mistral defaults to 0.7
    current_top_p = topp  # Mistral uses top_p
    current_streaming_cfg = mistral_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else \
        (str(current_streaming_cfg).lower() == 'true' if isinstance(current_streaming_cfg, str) else bool(
            current_streaming_cfg))

    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(mistral_config.get('max_tokens'), int)
    current_safe_prompt = safe_prompt if safe_prompt is not None else bool(mistral_config.get('safe_prompt', False))

    api_messages = []
    # Mistral expects system message as the first message with role: system if provided
    # However, their latest guidance often shows it as part of the first user message or specific instructions.
    # For OpenAI compatibility, if system_message is given, and not already in input_data, prepend it.
    has_system_in_input = any(msg.get("role") == "system" for msg in input_data)
    if system_message and not has_system_in_input:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    headers = {'Authorization': f'Bearer {final_api_key}', 'Content-Type': 'application/json',
               'Accept': 'application/json'}
    data = {"model": current_model, "messages": api_messages, "stream": current_streaming}

    if current_temp is not None: data["temperature"] = current_temp
    if current_top_p is not None: data["top_p"] = current_top_p
    if current_max_tokens is not None: data["max_tokens"] = current_max_tokens
    if random_seed is not None: data["random_seed"] = random_seed  # Mistral uses random_seed
    if top_k is not None: data["top_k"] = top_k  # Mistral has top_k
    if current_safe_prompt is not None: data["safe_prompt"] = current_safe_prompt  # Mistral specific
    if tools is not None: data["tools"] = tools
    if tool_choice == "none":
        data["tool_choice"] = "none"
    elif tool_choice is not None and tools is not None:
        data["tool_choice"] = tool_choice  # "auto", "any", "none"
    if response_format is not None: data["response_format"] = response_format  # {"type": "json_object"}

    api_url = mistral_config.get('api_base_url', 'https://api.mistral.ai/v1').rstrip('/') + '/chat/completions'
    data_metadata = _sanitize_payload_for_logging(data)
    logging.debug(f"Mistral request metadata: {data_metadata}")

    try:
        if current_streaming:
            session = create_session_with_retries(
                total=_safe_cast(mistral_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(mistral_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                stream_timeout = _safe_cast(mistral_config.get('api_timeout'), float, 90.0)
                response = session.post(api_url, headers=headers, json=data, stream=True, timeout=stream_timeout)
                response.raise_for_status()
            except Exception:
                try:
                    session.close()
                except Exception:
                    pass
                raise

            session_handle = session
            response_handle = response

            def stream_generator():
                try:
                    for chunk in iter_sse_lines_requests(response_handle, decode_unicode=True, provider="mistral"):
                        yield chunk
                    # Finalize with single [DONE] and close objects
                    for tail in finalize_stream(response_handle, done_already=False):
                        yield tail
                finally:
                    try:
                        session_handle.close()
                    except Exception:
                        pass

            return stream_generator()
        else:
            session = create_session_with_retries(
                total=_safe_cast(mistral_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(mistral_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=data, timeout=120)
                response.raise_for_status()
                try:
                    return response.json()
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
            finally:
                try:
                    session.close()
                except Exception:
                    pass
    except requests.exceptions.HTTPError as e:
        _raise_chat_error_from_http("mistral", e)
    except Exception as e:  # ... error handling ...
        raise ChatProviderError(provider="mistral", message=f"Unexpected error: {e}")


def chat_with_openrouter(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        # OpenRouter specific names from your map
        top_p: Optional[float] = None,  # from generic topp
        top_k: Optional[int] = None,  # from generic topk
        min_p: Optional[float] = None,  # from generic minp (OpenRouter uses min_p not minp)
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,  # from user_identifier
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    loaded_config_data = app_config or load_and_log_configs()
    openrouter_config = loaded_config_data.get('openrouter_api', {})
    # ... (api key, model, temp, streaming setup) ...
    final_api_key = api_key or openrouter_config.get('api_key')
    if not final_api_key: raise ChatConfigurationError(provider='openrouter', message="OpenRouter API Key required.")
    current_model = model or openrouter_config.get('model', 'mistralai/mistral-7b-instruct:free')
    # ... other param resolutions ...
    current_streaming_cfg = openrouter_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else \
        (str(current_streaming_cfg).lower() == 'true' if isinstance(current_streaming_cfg, str) else bool(
            current_streaming_cfg))

    api_messages = []
    if system_message: api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    headers = {
        "Authorization": f"Bearer {final_api_key}", "Content-Type": "application/json",
        "HTTP-Referer": openrouter_config.get("site_url", "http://localhost"),  # OpenRouter specific
        "X-Title": openrouter_config.get("site_name", "TLDW-API"),  # OpenRouter specific
    }
    data = {"model": current_model, "messages": api_messages, "stream": current_streaming}
    # Add all other accepted parameters to data if they are not None
    if temp is not None: data["temperature"] = temp
    if top_p is not None: data["top_p"] = top_p
    if top_k is not None: data["top_k"] = top_k
    if min_p is not None: data["min_p"] = min_p  # OpenRouter uses min_p
    if max_tokens is not None: data["max_tokens"] = max_tokens
    if seed is not None: data["seed"] = seed
    if stop is not None: data["stop"] = stop
    if response_format is not None: data["response_format"] = response_format
    if n is not None: data["n"] = n
    if user is not None: data["user"] = user
    if tools is not None: data["tools"] = tools
    _apply_tool_choice(data, tools, tool_choice)
    if logit_bias is not None: data["logit_bias"] = logit_bias
    if presence_penalty is not None: data["presence_penalty"] = presence_penalty
    if frequency_penalty is not None: data["frequency_penalty"] = frequency_penalty
    if logprobs is not None: data["logprobs"] = logprobs
    if top_logprobs is not None and data.get("logprobs"): data["top_logprobs"] = top_logprobs

    api_url = openrouter_config.get('api_base_url', "https://openrouter.ai/api/v1").rstrip('/') + "/chat/completions"
    data_metadata = _sanitize_payload_for_logging(data)
    logging.debug(f"OpenRouter request metadata: {data_metadata}")

    try:
        if current_streaming:
            session = create_session_with_retries(
                total=_safe_cast(openrouter_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(openrouter_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            stream_timeout = _safe_cast(openrouter_config.get('api_timeout'), float, 90.0)
            try:
                response = session.post(api_url, headers=headers, json=data, stream=True, timeout=stream_timeout)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            def stream_generator():
                try:
                    for chunk in iter_sse_lines_requests(response, decode_unicode=True, provider="openrouter"):
                        yield chunk
                    for tail in finalize_stream(response, done_already=False):
                        yield tail
                finally:
                    try:
                        session.close()
                    except Exception:
                        pass
            return stream_generator()
        else:
            session = create_session_with_retries(
                total=_safe_cast(openrouter_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(openrouter_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=data, timeout=120)
                response.raise_for_status()
                try:
                    return response.json()  # OpenRouter usually returns OpenAI compatible JSON
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
            finally:
                try:
                    session.close()
                except Exception:
                    pass
    except requests.exceptions.HTTPError as e:
        _raise_chat_error_from_http("openrouter", e)
    except Exception as e:  # ... error handling ...
        raise ChatProviderError(provider="openrouter", message=f"Unexpected error: {e}")


def chat_with_moonshot(
        input_data: List[Dict[str, Any]],  # Mapped from 'messages_payload'
        model: Optional[str] = None,  # Mapped from 'model'
        api_key: Optional[str] = None,  # Mapped from 'api_key'
        system_message: Optional[str] = None,  # Mapped from 'system_message'
        temp: Optional[float] = None,  # Mapped from 'temp' (temperature)
        maxp: Optional[float] = None,  # Mapped from 'maxp' (top_p)
        streaming: Optional[bool] = False,  # Mapped from 'streaming'
        # Moonshot/OpenAI compatible parameters
        frequency_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,  # Number of completions
        presence_penalty: Optional[float] = None,
        response_format: Optional[Dict[str, str]] = None,  # e.g., {"type": "json_object"}
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        user: Optional[str] = None,  # User identifier
        custom_prompt_arg: Optional[str] = None,  # Legacy
        app_config: Optional[Dict[str, Any]] = None,
):
    """
    Sends a chat completion request to the Moonshot AI API.

    Moonshot AI provides an OpenAI-compatible API endpoint, supporting models:
    - kimi-latest: Latest Kimi model
    - kimi-thinking-preview: Kimi model with thinking capabilities
    - kimi-k2-0711-preview: Kimi K2 preview model
    - moonshot-v1-auto: Automatic model selection
    - moonshot-v1-8k: 8K context window
    - moonshot-v1-32k: 32K context window
    - moonshot-v1-128k: 128K context window
    - moonshot-v1-8k-vision-preview: 8K context with vision support
    - moonshot-v1-32k-vision-preview: 32K context with vision support
    - moonshot-v1-128k-vision-preview: 128K context with vision support

    Args:
        input_data: List of message objects (OpenAI format).
        model: ID of the model to use (moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k).
        api_key: Moonshot API key.
        system_message: Optional system message to prepend.
        temp: Sampling temperature (0-1).
        maxp: Top-p (nucleus) sampling parameter.
        streaming: Whether to stream the response.
        frequency_penalty: Penalizes new tokens based on their existing frequency.
        max_tokens: Maximum number of tokens to generate.
        n: How many chat completion choices to generate (Note: n>1 only works with temp>0.3).
        presence_penalty: Penalizes new tokens based on whether they appear in the text so far.
        response_format: An object specifying the format that the model must output.
        seed: If specified, the system will make a best effort to sample deterministically.
        stop: Up to 4 sequences where the API will stop generating further tokens.
        tools: A list of tools the model may call.
        tool_choice: Controls which (if any) function is called by the model (Note: "required" not supported).
        user: A unique identifier representing your end-user.
        custom_prompt_arg: Legacy, largely ignored.
    """
    loaded_config_data = app_config or load_and_log_configs()
    moonshot_config = loaded_config_data.get('moonshot_api', {})

    final_api_key = api_key or moonshot_config.get('api_key')
    if not final_api_key:
        logging.error("Moonshot: API key is missing.")
        raise ChatConfigurationError(provider="moonshot", message="Moonshot API Key is required but not found.")

    logging.debug("Moonshot: Using configured API key")

    # Resolve parameters: User-provided > Function arg default > Config default > Hardcoded default
    final_model = model if model is not None else moonshot_config.get('model', 'moonshot-v1-8k')
    final_temp = temp if temp is not None else _safe_cast(moonshot_config.get('temperature'), float, 0.7)
    final_top_p = maxp if maxp is not None else _safe_cast(moonshot_config.get('top_p'), float, 0.95)

    # Validate temperature for n>1 as per Moonshot documentation
    final_n = n if n is not None else 1
    if final_n > 1 and final_temp < 0.3:
        logging.warning(f"Moonshot: n={final_n} requested but temperature={final_temp} < 0.3. Setting n=1.")
        final_n = 1

    final_streaming_cfg = moonshot_config.get('streaming', False)
    final_streaming = streaming if streaming is not None else \
        (str(final_streaming_cfg).lower() == 'true' if isinstance(final_streaming_cfg, str) else bool(final_streaming_cfg))

    final_max_tokens = max_tokens if max_tokens is not None else _safe_cast(moonshot_config.get('max_tokens'), int)

    if custom_prompt_arg:
        logging.warning(
            "Moonshot: 'custom_prompt_arg' was provided but is generally ignored if 'input_data' and 'system_message' are used correctly.")

    # Construct messages for Moonshot API (OpenAI format)
    api_messages = []
    has_system_message_in_input = any(msg.get("role") == "system" for msg in input_data)
    if system_message and not has_system_message_in_input:
        api_messages.append({"role": "system", "content": system_message})

    # Process messages to ensure proper format
    is_vision_model = "vision" in final_model.lower()

    for msg in input_data:
        role = msg.get("role")
        content = msg.get("content")

        # Handle different content formats
        if isinstance(content, list):
            if is_vision_model:
                # For vision models, convert to Moonshot's expected format
                moonshot_content = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            moonshot_content.append({
                                "type": "text",
                                "text": part.get("text", "")
                            })
                        elif part.get("type") == "image_url":
                            image_url_obj = part.get("image_url", {})
                            url_str = image_url_obj.get("url", "")
                            # Parse data URL for vision models
                            parsed_image = _parse_data_url_for_multimodal(url_str)
                            if parsed_image:
                                mime_type, b64_data = parsed_image
                                moonshot_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": url_str  # Keep original data URL
                                    }
                                })
                            else:
                                # Regular URL
                                moonshot_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": url_str
                                    }
                                })
                    elif isinstance(part, str):
                        moonshot_content.append({
                            "type": "text",
                            "text": part
                        })

                # For vision models, keep structured content
                api_messages.append({"role": role, "content": moonshot_content})
            else:
                # For non-vision models, extract only text
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
                    logging.warning(f"Moonshot: Images found in messages but model {final_model} doesn't support vision. Images will be ignored.")

                combined_text = "\n".join(text_parts)
                api_messages.append({"role": role, "content": combined_text})
        else:
            # Simple string content
            api_messages.append({"role": role, "content": content})

    payload = {
        "model": final_model,
        "messages": api_messages,
        "stream": final_streaming,
    }

    # Add optional parameters if they have a value
    if final_temp is not None: payload["temperature"] = final_temp
    if final_top_p is not None: payload["top_p"] = final_top_p
    if final_max_tokens is not None: payload["max_tokens"] = final_max_tokens
    if frequency_penalty is not None: payload["frequency_penalty"] = frequency_penalty
    if final_n is not None and final_n != 1: payload["n"] = final_n
    if presence_penalty is not None: payload["presence_penalty"] = presence_penalty
    if response_format is not None: payload["response_format"] = response_format
    if seed is not None: payload["seed"] = seed
    if stop is not None: payload["stop"] = stop
    if tools is not None: payload["tools"] = tools
    _apply_tool_choice(payload, tools, tool_choice)
    if user is not None: payload["user"] = user

    headers = {
        'Authorization': f'Bearer {final_api_key}',
        'Content-Type': 'application/json'
    }

    api_base_url = moonshot_config.get('api_base_url', 'https://api.moonshot.cn/v1')
    api_url = api_base_url.rstrip('/') + '/chat/completions'

    payload_metadata = _sanitize_payload_for_logging(payload)
    logging.debug(f"Moonshot request metadata: {payload_metadata}")

    try:
        if final_streaming:
            logging.debug("Moonshot: Posting request (streaming)")
            session = create_session_with_retries(
                total=_safe_cast(moonshot_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(moonshot_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            stream_timeout = _safe_cast(moonshot_config.get('api_timeout'), float, 90.0)
            try:
                response = session.post(api_url, headers=headers, json=payload, stream=True, timeout=stream_timeout)
                response.raise_for_status()
            except Exception:
                session.close()
                raise

            def stream_generator():
                try:
                    for chunk in iter_sse_lines_requests(response, decode_unicode=True, provider="moonshot"):
                        yield chunk
                    for tail in finalize_stream(response, done_already=False):
                        yield tail
                finally:
                    try:
                        session.close()
                    except Exception:
                        pass
            return stream_generator()
        else:  # Non-streaming
            logging.debug("Moonshot: Posting request (non-streaming)")
            session = create_session_with_retries(
                total=_safe_cast(moonshot_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(moonshot_config.get('api_retry_delay'), float, 1.0),
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
                    try:
                        response.close()
                    except Exception:
                        pass
                logging.debug("Moonshot: Non-streaming request successful.")
                return response_data
            finally:
                try:
                    session.close()
                except Exception:
                    pass

    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            logging.error(f"Moonshot Full Error Response (status {e.response.status_code}): {e.response.text}")
        else:
            logging.error(f"Moonshot HTTPError with no response object: {e}")
        _raise_chat_error_from_http("moonshot", e)
    except requests.exceptions.RequestException as e:
        logging.error(f"Moonshot RequestException: {e}", exc_info=True)
        raise ChatProviderError(provider="moonshot", message=f"Network error: {e}", status_code=504)
    except Exception as e:
        logging.error(f"Moonshot: Unexpected error in chat_with_moonshot: {e}", exc_info=True)
        raise ChatProviderError(provider="moonshot", message=f"Unexpected error: {e}")


def chat_with_zai(
        input_data: List[Dict[str, Any]],  # Mapped from 'messages_payload'
        model: Optional[str] = None,  # Mapped from 'model'
        api_key: Optional[str] = None,  # Mapped from 'api_key'
        system_message: Optional[str] = None,  # Mapped from 'system_message'
        temp: Optional[float] = None,  # Mapped from 'temp' (temperature)
        maxp: Optional[float] = None,  # Mapped from 'maxp' (top_p)
        streaming: Optional[bool] = False,  # Mapped from 'streaming'
        # Z.AI specific parameters
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        do_sample: Optional[bool] = None,
        request_id: Optional[str] = None,
        custom_prompt_arg: Optional[str] = None,  # Legacy
        app_config: Optional[Dict[str, Any]] = None,
):
    """
    Sends a chat completion request to the Z.AI API.

    Z.AI provides GLM model access through an OpenAI-compatible API endpoint, supporting models:
    - glm-4.5: Standard GLM-4.5 model
    - glm-4.5-air: GLM-4.5 optimized for speed
    - glm-4.5-x: GLM-4.5 extended capabilities
    - glm-4.5-airx: GLM-4.5 air with extended features
    - glm-4.5-flash: Fast inference GLM-4.5 model
    - glm-4-32b-0414-128k: GLM-4 32B with 128K context

    Args:
        input_data: List of message objects (OpenAI format).
        model: ID of the model to use (e.g., glm-4.5-flash).
        api_key: Z.AI API key.
        system_message: Optional system message to prepend.
        temp: Sampling temperature (0-1).
        maxp: Top-p (nucleus) sampling parameter.
        streaming: Whether to stream the response.
        max_tokens: Maximum number of tokens to generate.
        tools: A list of tools the model may call.
        do_sample: Whether to use sampling (temperature/top_p).
        request_id: Optional request ID for tracking.
        custom_prompt_arg: Legacy, largely ignored.
    """
    loaded_config_data = app_config or load_and_log_configs()
    zai_config = loaded_config_data.get('zai_api', {})

    final_api_key = api_key or zai_config.get('api_key')
    if not final_api_key:
        logging.error("Z.AI: API key is missing.")
        raise ChatConfigurationError(provider="zai", message="Z.AI API Key is required but not found.")

    logging.debug("Z.AI: Using configured API key")

    # Resolve parameters
    current_model = model or zai_config.get('model', 'glm-4.5-flash')
    current_temp = temp if temp is not None else _safe_cast(zai_config.get('temperature'), float, 0.7)
    current_top_p = maxp if maxp is not None else _safe_cast(zai_config.get('top_p'), float, 0.95)
    current_streaming_cfg = zai_config.get('streaming', False)
    current_streaming = streaming if streaming is not None else \
        (str(current_streaming_cfg).lower() == 'true' if isinstance(current_streaming_cfg, str) else bool(
            current_streaming_cfg))
    current_max_tokens = max_tokens if max_tokens is not None else _safe_cast(zai_config.get('max_tokens'), int, 4096)

    # Build messages array
    api_messages = []
    if system_message:
        api_messages.append({"role": "system", "content": system_message})
    api_messages.extend(input_data)

    # Build request payload
    payload = {
        "model": current_model,
        "messages": api_messages,
        "stream": current_streaming,
    }

    # Add optional parameters
    if current_temp is not None:
        payload["temperature"] = current_temp
    if current_top_p is not None:
        payload["top_p"] = current_top_p
    if current_max_tokens is not None:
        payload["max_tokens"] = current_max_tokens
    if do_sample is not None:
        payload["do_sample"] = do_sample
    if tools is not None:
        payload["tools"] = tools
    if request_id is not None:
        payload["request_id"] = request_id

    headers = {
        'Authorization': f'Bearer {final_api_key}',
        'Content-Type': 'application/json'
    }

    api_base_url = zai_config.get('api_base_url', 'https://api.z.ai/api/paas/v4')
    api_url = api_base_url.rstrip('/') + '/chat/completions'

    payload_metadata = _sanitize_payload_for_logging(payload)
    logging.debug(f"Z.AI request metadata: {payload_metadata}")

    try:
        if current_streaming:
            logging.debug("Z.AI: Posting request (streaming)")
            session = create_session_with_retries(
                total=_safe_cast(zai_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(zai_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                stream_timeout = _safe_cast(zai_config.get('api_timeout'), float, 90.0)
                response = session.post(api_url, headers=headers, json=payload, stream=True, timeout=stream_timeout)
                response.raise_for_status()

                def stream_generator():
                    done_sent = False
                    skip_finalize = False
                    try:
                        for raw_line in response.iter_lines(decode_unicode=True):
                            if not raw_line:
                                continue
                            if is_done_line(raw_line):
                                done_sent = True
                            normalized = normalize_provider_line(raw_line)
                            if normalized is None:
                                continue
                            yield normalized
                        if not done_sent:
                            done_sent = True
                            yield sse_done()
                    except GeneratorExit:
                        skip_finalize = True
                        try:
                            if response:
                                response.close()
                        finally:
                            try:
                                session.close()
                            except Exception:
                                pass
                        raise
                    except requests.exceptions.ChunkedEncodingError as e_chunk:
                        logging.error(f"Z.AI: ChunkedEncodingError during stream: {e_chunk}", exc_info=True)
                        yield sse_data({"error": {"message": f"Stream connection error: {str(e_chunk)}", "type": "zai_stream_error"}})
                    except Exception as e_stream:
                        logging.error(f"Z.AI: Error during stream iteration: {e_stream}", exc_info=True)
                        yield sse_data({"error": {"message": f"Stream iteration error: {str(e_stream)}", "type": "zai_stream_error"}})
                    finally:
                        try:
                            if not skip_finalize:
                                for tail in finalize_stream(response, done_already=done_sent):
                                    yield tail
                        finally:
                            try:
                                session.close()
                            except Exception:
                                pass

                return stream_generator()
            except Exception:
                try:
                    session.close()
                except Exception:
                    pass
                raise

        else:  # Non-streaming
            logging.debug("Z.AI: Posting request (non-streaming)")
            session = create_session_with_retries(
                total=_safe_cast(zai_config.get('api_retries'), int, 3),
                backoff_factor=_safe_cast(zai_config.get('api_retry_delay'), float, 1.0),
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
            )
            try:
                response = session.post(api_url, headers=headers, json=payload, timeout=120)
                logging.debug(f"Z.AI: Full API response status: {response.status_code}")
                response.raise_for_status()
                try:
                    response_data = response.json()
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
                logging.debug("Z.AI: Non-streaming request successful.")
                return response_data
            finally:
                try:
                    session.close()
                except Exception:
                    pass

    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            logging.error(f"Z.AI Full Error Response (status {e.response.status_code}): {e.response.text}")
        else:
            logging.error(f"Z.AI HTTPError with no response object: {e}")
        _raise_chat_error_from_http("zai", e)
    except requests.exceptions.RequestException as e:
        logging.error(f"Z.AI RequestException: {e}", exc_info=True)
        raise ChatProviderError(provider="zai", message=f"Network error: {e}", status_code=504)
    except Exception as e:
        logging.error(f"Z.AI: Unexpected error in chat_with_zai: {e}", exc_info=True)
        raise ChatProviderError(provider="zai", message=f"Unexpected error: {e}")

#
#
#######################################################################################################################
