"""
chat_calls
Commercial-provider LLM calling utilities (adapter-backed compatibility layer).

This module implements provider-specific chat/embeddings helpers while returning
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
# Commercial LLM API calling utilities.
# Public chat_* entrypoints delegate to adapter-backed handlers and keep
# the compatibility surface stable for call sites.
#
# Import necessary libraries
import asyncio
import threading
import json
import os
import time
from typing import List, Any, Optional, Tuple, Dict, Union, Iterable
#
# Import 3rd-Party Libraries
from tldw_Server_API.app.core.http_client import fetch, RetryPolicy

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAPIError
from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call, perform_chat_api_call_async
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
from tldw_Server_API.app.core.LLM_Calls.http_helpers import create_session_with_retries as _legacy_create_session_with_retries
from tldw_Server_API.app.core.LLM_Calls.streaming import (
    iter_sse_lines_requests,
)
from tldw_Server_API.app.core.LLM_Calls.error_utils import (
    get_http_error_text,
    get_http_status_from_exception,
    is_chunked_encoding_error,
    is_http_status_error,
    is_network_error,
)

# -----------------------------------------------------------------------------
# Session shim for non-streaming POST calls
# - Preserves the public name `create_session_with_retries` so tests can
#   monkeypatch it, while centralizing non-streaming requests via http_client.
# - For streaming (stream=True), falls back to the legacy session facade
#   returned by http_helpers.create_session_with_retries to preserve
#   iter_lines() semantics used in streaming paths.
# -----------------------------------------------------------------------------

class _SessionShim:
    def __init__(
        self,
        *,
        total: int = 3,
        backoff_factor: float = 1.0,
        status_forcelist: Optional[list[int]] = None,
        allowed_methods: Optional[list[str]] = None,
    ) -> None:
        attempts = max(1, int(total)) + 0
        self._retry = RetryPolicy(
            attempts=attempts,
            backoff_base_ms=int(float(backoff_factor) * 1000),
            retry_on_status=tuple(status_forcelist or (408, 429, 500, 502, 503, 504)),
        )
        self._delegate_session = None

    def post(self, url, *, headers=None, json=None, stream: bool = False, timeout=None, **kwargs):
        if stream:
            # For streaming, use legacy requests session to preserve iter_lines semantics
            self._delegate_session = _legacy_create_session_with_retries(
                total=self._retry.attempts,
                backoff_factor=self._retry.backoff_base_ms / 1000.0,
                status_forcelist=list(self._retry.retry_on_status),
                allowed_methods=["POST"],
            )
            return self._delegate_session.post(url, headers=headers, json=json, stream=True, timeout=timeout)
        # Non-streaming via centralized http client (egress/pinning)
        resp = fetch(
            method="POST",
            url=url,
            headers=headers,
            json=json,
            timeout=timeout,
            retry=self._retry,
        )
        return resp

    def close(self):
        try:
            if self._delegate_session is not None:
                self._delegate_session.close()
        except Exception:
            pass


def create_session_with_retries(
    *,
    total: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: Optional[list[int]] = None,
    allowed_methods: Optional[list[str]] = None,
):
    """Return a session object.

    - Under pytest, return the legacy session facade so tests can patch
      `create_session_with_retries` directly.
    - In production, return a shim that routes non-streaming POSTs through
      the centralized HTTP client (egress policy, TLS pinning) and streaming
      through the legacy session facade for iter_lines semantics.
    """
    import os as _os
    if _os.getenv("PYTEST_CURRENT_TEST"):
        return _legacy_create_session_with_retries(
            total=total,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=allowed_methods,
        )
    return _SessionShim(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
    )
#
def _call_adapter(
        provider: str,
        *,
        input_data: List[Dict[str, Any]],
        app_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
) -> Any:
    return perform_chat_api_call(
        api_provider=provider,
        messages=input_data,
        app_config=app_config,
        **kwargs,
    )


async def _call_adapter_async(
        provider: str,
        *,
        input_data: List[Dict[str, Any]],
        app_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
) -> Any:
    return await perform_chat_api_call_async(
        api_provider=provider,
        messages=input_data,
        app_config=app_config,
        **kwargs,
    )
#
#######################################################################################################################

# Adapter-backed wrappers (monolith cleanup):
# These preserve public entry points but route through adapter shims.
# Provider-specific implementations live under `providers/`.

def chat_with_openai(
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
    return _call_adapter(
        "openai",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        maxp=maxp,
        streaming=streaming,
        frequency_penalty=frequency_penalty,
        logit_bias=logit_bias,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        max_tokens=max_tokens,
        n=n,
        presence_penalty=presence_penalty,
        response_format=response_format,
        seed=seed,
        stop=stop,
        tools=tools,
        tool_choice=tool_choice,
        user=user,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


def chat_with_groq(
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
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "groq",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        maxp=maxp,
        streaming=streaming,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        response_format=response_format,
        n=n,
        user=user,
        tools=tools,
        tool_choice=tool_choice,
        logit_bias=logit_bias,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


def chat_with_openrouter(
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
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "openrouter",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        response_format=response_format,
        n=n,
        user=user,
        tools=tools,
        tool_choice=tool_choice,
        logit_bias=logit_bias,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


def chat_with_google(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        topp: Optional[float] = None,
        topk: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        candidate_count: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "google",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        topp=topp,
        topk=topk,
        max_output_tokens=max_output_tokens,
        stop_sequences=stop_sequences,
        candidate_count=candidate_count,
        response_format=response_format,
        tools=tools,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


def chat_with_mistral(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        topp: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        random_seed: Optional[int] = None,
        top_k: Optional[int] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "mistral",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        topp=topp,
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=max_tokens,
        random_seed=random_seed,
        top_k=top_k,
        app_config=app_config,
    )


def chat_with_qwen(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        maxp: Optional[float] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "qwen",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        maxp=maxp,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        logit_bias=logit_bias,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        response_format=response_format,
        n=n,
        user=user,
        tools=tools,
        tool_choice=tool_choice,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


def chat_with_huggingface(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "huggingface",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        app_config=app_config,
    )


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

def get_openai_embeddings(
    input_data: str,
    model: str,
    app_config: Optional[Dict[str, Any]] = None,
    dimensions: Optional[int] = None,
) -> List[float]:
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
    if dimensions is not None:
        try:
            dim = int(dimensions)
        except Exception:
            dim = None
        if dim and dim > 0:
            request_data["dimensions"] = dim
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
    except Exception as e:
        if is_http_status_error(e):
            logging.error(
                "OpenAI Embeddings (single): HTTP request failed with status %s, Response: %s",
                get_http_status_from_exception(e),
                get_http_error_text(e),
                exc_info=True,
            )
            raise
        if is_network_error(e):
            logging.error(f"OpenAI Embeddings (single): Error making API request: {str(e)}", exc_info=True)
            raise ValueError(
                f"OpenAI Embeddings (single): Error making API request: {str(e)}"
            )
        logging.error(f"OpenAI Embeddings (single): Unexpected error: {str(e)}", exc_info=True)
        raise ValueError(f"OpenAI Embeddings (single): Unexpected error occurred: {str(e)}")


# NEW BATCH FUNCTION
def get_openai_embeddings_batch(
    texts: List[str],
    model: str,
    app_config: Optional[Dict[str, Any]] = None,
    dimensions: Optional[int] = None,
) -> List[List[float]]:
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
    if dimensions is not None:
        try:
            dim = int(dimensions)
        except Exception:
            dim = None
        if dim and dim > 0:
            request_data["dimensions"] = dim
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

    except Exception as e:
        if is_http_status_error(e):
            # Log the detailed error including the response text for better debugging
            error_message = (
                f"OpenAI Embeddings (batch): HTTP request failed with status {get_http_status_from_exception(e)}."
            )
            try:
                resp = getattr(e, "response", None)
                error_body = resp.json() if resp is not None else None
                if isinstance(error_body, dict):
                    error_message += f" Error details: {error_body.get('error', {}).get('message', get_http_error_text(e))}"
                else:
                    error_message += f" Response: {get_http_error_text(e)}"
            except Exception:
                error_message += f" Response: {get_http_error_text(e)}"
            logging.error(error_message, exc_info=True)
            raise
        if is_network_error(e):
            # Propagate request exceptions so upstream retry logic can handle transient failures
            logging.error(f"OpenAI Embeddings (batch): RequestException: {str(e)}", exc_info=True)
            raise
        logging.error(f"OpenAI Embeddings (batch): Unexpected error: {str(e)}", exc_info=True)
        raise ValueError(f"OpenAI Embeddings (batch): Unexpected error occurred: {str(e)}")


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
    return await _call_adapter_async(
        "openai",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        maxp=maxp,
        streaming=streaming,
        frequency_penalty=frequency_penalty,
        logit_bias=logit_bias,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        max_tokens=max_tokens,
        n=n,
        presence_penalty=presence_penalty,
        response_format=response_format,
        seed=seed,
        stop=stop,
        tools=tools,
        tool_choice=tool_choice,
        user=user,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


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
    return await _call_adapter_async(
        "groq",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        maxp=maxp,
        streaming=streaming,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        response_format=response_format,
        n=n,
        user=user,
        tools=tools,
        tool_choice=tool_choice,
        logit_bias=logit_bias,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        app_config=app_config,
    )


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
    return await _call_adapter_async(
        "anthropic",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_prompt=system_prompt,
        temp=temp,
        topp=topp,
        topk=topk,
        streaming=streaming,
        max_tokens=max_tokens,
        stop_sequences=stop_sequences,
        tools=tools,
        app_config=app_config,
    )


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
    return await _call_adapter_async(
        "openrouter",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        response_format=response_format,
        n=n,
        user=user,
        tools=tools,
        tool_choice=tool_choice,
        logit_bias=logit_bias,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        app_config=app_config,
    )


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
    """Uniform adapter-backed Bedrock entry point (prod)."""
    return _call_adapter(
        "bedrock",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        maxp=maxp,
        max_tokens=max_tokens,
        n=n,
        stop=stop,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        logit_bias=logit_bias,
        seed=seed,
        response_format=response_format,
        tools=tools,
        tool_choice=tool_choice,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        user=user,
        extra_headers=extra_headers,
        extra_body=extra_body,
        app_config=app_config,
    )


async def chat_with_bedrock_async(
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
    return await _call_adapter_async(
        "bedrock",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        maxp=maxp,
        max_tokens=max_tokens,
        n=n,
        stop=stop,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        logit_bias=logit_bias,
        seed=seed,
        response_format=response_format,
        tools=tools,
        tool_choice=tool_choice,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        user=user,
        extra_headers=extra_headers,
        extra_body=extra_body,
        app_config=app_config,
    )


def chat_with_anthropic(
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
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "anthropic",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_prompt=system_prompt,
        temp=temp,
        topp=topp,
        topk=topk,
        streaming=streaming,
        max_tokens=max_tokens,
        stop_sequences=stop_sequences,
        tools=tools,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


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
    return _call_adapter(
        "cohere",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_prompt=system_prompt,
        temp=temp,
        streaming=streaming,
        topp=topp,
        topk=topk,
        max_tokens=max_tokens,
        stop_sequences=stop_sequences,
        seed=seed,
        num_generations=num_generations,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        tools=tools,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


def chat_with_deepseek(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        topp: Optional[float] = None,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        response_format: Optional[Dict[str, str]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    return _call_adapter(
        "deepseek",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        topp=topp,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        response_format=response_format,
        n=n,
        user=user,
        tools=tools,
        tool_choice=tool_choice,
        logit_bias=logit_bias,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


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
    return _call_adapter(
        "moonshot",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        maxp=maxp,
        streaming=streaming,
        frequency_penalty=frequency_penalty,
        max_tokens=max_tokens,
        n=n,
        presence_penalty=presence_penalty,
        response_format=response_format,
        seed=seed,
        stop=stop,
        tools=tools,
        tool_choice=tool_choice,
        user=user,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )


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
    return _call_adapter(
        "zai",
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        maxp=maxp,
        streaming=streaming,
        max_tokens=max_tokens,
        tools=tools,
        do_sample=do_sample,
        request_id=request_id,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )
