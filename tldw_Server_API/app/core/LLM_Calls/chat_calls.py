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
# Public chat_* entrypoints delegate to adapter-backed handlers; provider-
# specific implementations are retained under legacy_* names until further
# cleanup removes the legacy naming.
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
from tldw_Server_API.app.core.http_client import fetch, afetch_json, RetryPolicy

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
from tldw_Server_API.app.core.LLM_Calls.providers.base import apply_tool_choice as _apply_tool_choice_base

# -----------------------------------------------------------------------------
# Session shim for non-streaming POST calls
# - Preserves the public name `create_session_with_retries` so tests can
#   monkeypatch it, while centralizing non-streaming requests via http_client.
# - For streaming (stream=True), falls back to the legacy requests session
#   returned by http_helpers.create_session_with_retries to preserve
#   iter_lines() semantics used in streaming paths still on requests.
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

    - Under pytest, return a real requests.Session so tests can patch
      `requests.Session.post` directly.
    - In production, return a shim that routes non-streaming POSTs through
      the centralized HTTP client (egress policy, TLS pinning) and streaming
      through a legacy requests.Session for iter_lines semantics.
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
# Shared helper for consistent tool_choice gating across providers
def _apply_tool_choice(payload: Dict[str, Any], tools: Optional[List[Dict[str, Any]]], tool_choice: Optional[Union[str, Dict[str, Any]]]) -> None:
    """Back-compat wrapper around the shared helper in providers.base."""
    _apply_tool_choice_base(payload, tools, tool_choice)
#
#######################################################################################################################

# Adapter-backed wrappers (monolith cleanup):
# These preserve public entry points but route through adapter shims.
# True legacy implementations are kept under legacy_* names above to avoid
# recursion and for optional fallback paths.

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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openai_chat_handler
    return openai_chat_handler(
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


def legacy_chat_with_anthropic(
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
    # Adapter-backed wrapper retained for compatibility.
    return chat_with_anthropic(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import groq_chat_handler
    return groq_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openrouter_chat_handler
    return openrouter_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import google_chat_handler
    return google_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import mistral_chat_handler
    return mistral_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import qwen_chat_handler
    return qwen_chat_handler(
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


def legacy_chat_with_deepseek(
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
        # Accept OpenAI-style extras for compatibility with adapter callers
        response_format: Optional[Dict[str, Any]] = None,
        n: Optional[int] = None,
        user: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        custom_prompt_arg: Optional[str] = None,
        app_config: Optional[Dict[str, Any]] = None,
):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import deepseek_chat_handler
    return deepseek_chat_handler(
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


def chat_with_huggingface(
        input_data: List[Dict[str, Any]],
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        streaming: Optional[bool] = False,
        app_config: Optional[Dict[str, Any]] = None,
):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import huggingface_chat_handler
    return huggingface_chat_handler(
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        app_config=app_config,
    )


async def legacy_chat_with_openai_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openai_chat_handler_async
    return await openai_chat_handler_async(
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


async def legacy_chat_with_groq_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import groq_chat_handler_async
    return await groq_chat_handler_async(
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


async def legacy_chat_with_anthropic_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import anthropic_chat_handler
    if streaming:
        gen = await asyncio.to_thread(
            anthropic_chat_handler,
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

        async def _astream():
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

        return _astream()
    return await asyncio.to_thread(
        anthropic_chat_handler,
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


async def legacy_chat_with_openrouter_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openrouter_chat_handler_async
    return await openrouter_chat_handler_async(
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

def _raise_chat_error_from_http(provider: str, error: Exception) -> None:
    """Normalize HTTP status errors into project ChatAPIError subclasses."""
    status_code = get_http_status_from_exception(error)
    message: str = ""
    response = getattr(error, "response", None)

    if response is not None:
        try:
            response_text = repr(get_http_error_text(error))
        except Exception:
            response_text = "<unable to read response text>"
        logging.error(f"{provider.capitalize()} HTTP error response (status {status_code}): {response_text}")
        try:
            err_json = response.json()
            if isinstance(err_json, dict):
                message = (
                    err_json.get("error", {}).get("message")
                    or err_json.get("message")
                    or get_http_error_text(error)
                )
            else:
                message = get_http_error_text(error)
        except Exception:
            message = get_http_error_text(error)
    else:
        logging.error(f"{provider.capitalize()} HTTP error with no response payload: {error}")
        message = get_http_error_text(error)

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


def legacy_chat_with_openai(
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
    # Adapter era: delegate to adapter-backed shim; keep legacy body unreachable
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openai_chat_handler
    return openai_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openai_chat_handler_async
    return await openai_chat_handler_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import groq_chat_handler_async
    return await groq_chat_handler_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import anthropic_chat_handler_async
    return await anthropic_chat_handler_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openrouter_chat_handler_async
    return await openrouter_chat_handler_async(
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


def legacy_chat_with_bedrock(
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
    AWS Bedrock via OpenAI-compatible Chat Completions endpoint (legacy path).

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

    logging.debug(f"Bedrock(legacy): POST {api_url} (stream={current_streaming})")

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
                except Exception as e_stream:
                    if is_chunked_encoding_error(e_stream):
                        logging.error(f"Bedrock(legacy) stream chunked encoding error: {e_stream}")
                        yield sse_data({"error": {"message": f"Stream connection error: {str(e_stream)}", "type": "bedrock_stream_error"}})
                    else:
                        logging.error(f"Bedrock(legacy) stream iteration error: {e_stream}", exc_info=True)
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
            logging.debug(f"Bedrock(legacy): status={response.status_code}")
            response.raise_for_status()
            try:
                return response.json()
            finally:
                try:
                    response.close()
                except Exception:
                    pass
    except Exception as e:
        if is_http_status_error(e):
            status_code = get_http_status_from_exception(e)
            error_text = get_http_error_text(e)
            logging.error(f"Bedrock(legacy) HTTPError {status_code}: {repr(error_text[:500])}")
            if status_code in (400, 404, 422):
                raise ChatBadRequestError(provider="bedrock", message=error_text)
            if status_code in (401, 403):
                raise ChatAuthenticationError(provider="bedrock", message=error_text)
            if status_code == 429:
                raise ChatRateLimitError(provider="bedrock", message=error_text)
            if status_code in (500, 502, 503, 504):
                raise ChatProviderError(provider="bedrock", message=error_text, status_code=status_code)
            raise ChatAPIError(provider="bedrock", message=error_text, status_code=(status_code or 500))
        if is_network_error(e):
            logging.error(f"Bedrock(legacy) RequestException: {e}", exc_info=True)
            raise ChatProviderError(provider="bedrock", message=f"Network error: {e}", status_code=504)
        logging.error(f"Bedrock(legacy) unexpected error: {e}", exc_info=True)
        raise ChatProviderError(provider="bedrock", message=f"Unexpected error: {e}")
    finally:
        if session is not None:
            session.close()


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
    """Uniform adapter-backed Bedrock entry point (prod) with test-friendly fallbacks.

    Delegates to adapter_calls.bedrock_chat_handler which uses the Bedrock adapter
    by default and falls back to the legacy implementation only if the adapter is
    unavailable (e.g., missing dependency).
    """
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import bedrock_chat_handler
    return bedrock_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import bedrock_chat_handler_async
    return await bedrock_chat_handler_async(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import anthropic_chat_handler
    return anthropic_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import cohere_chat_handler
    return cohere_chat_handler(
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


def legacy_chat_with_cohere(
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

    api_base_url = cohere_config.get('api_base_url', 'https://api.cohere.ai').rstrip('/')
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

                except Exception as e_stream:
                    if is_chunked_encoding_error(e_stream):
                        logging.warning(f"Cohere stream: ChunkedEncodingError: {e_stream}")
                        yield sse_data({"error": {"message": f"Stream connection error: {str(e_stream)}", "type": "cohere_stream_error"}})
                    else:
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

    except Exception as e:
        if is_http_status_error(e):
            status_code = get_http_status_from_exception(e) or 500
            error_text = get_http_error_text(e)
            logging.error(
                f"Cohere API call HTTPError to {COHERE_CHAT_URL} status {status_code}. Details: {repr(error_text[:500])}",
                exc_info=False,
            )
            if status_code == 401:
                raise ChatAuthenticationError(provider="cohere", message=f"Authentication failed. Detail: {error_text[:200]}")
            if status_code == 429:
                raise ChatRateLimitError(provider="cohere", message=f"Rate limit exceeded. Detail: {error_text[:200]}")
            if 400 <= status_code < 500:
                raise ChatBadRequestError(provider="cohere", message=f"Bad request (Status {status_code}). Detail: {error_text[:200]}")
            # 5xx
            raise ChatProviderError(
                provider="cohere",
                message=f"Server error (Status {status_code}). Detail: {error_text[:200]}",
                status_code=status_code,
            )
        if is_network_error(e):
            logging.error(f"Cohere API request failed (network error) for {COHERE_CHAT_URL}: {e}", exc_info=True)
            # This will catch the ReadTimeout after retries are exhausted
            raise ChatProviderError(provider="cohere", message=f"Network error after retries: {e}", status_code=504)
        raise
    except KeyError as e:
        # Surface clearer configuration error if payload/response shape assumptions break
        raise ChatBadRequestError(provider="cohere", message=f"Key error while preparing or parsing Cohere payload/response: {e}")
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import deepseek_chat_handler
    return deepseek_chat_handler(
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


def legacy_chat_with_google(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import google_chat_handler
    return google_chat_handler(
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



# https://console.groq.com/docs/quickstart


def legacy_chat_with_qwen(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import qwen_chat_handler
    return qwen_chat_handler(
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


def legacy_chat_with_groq(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import groq_chat_handler
    return groq_chat_handler(
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


def legacy_chat_with_huggingface(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import huggingface_chat_handler
    return huggingface_chat_handler(
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        top_p=top_p,
        top_k=top_k,
        max_tokens=max_tokens,
        seed=seed,
        stop=stop,
        response_format=response_format,
        num_return_sequences=num_return_sequences,
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

def legacy_chat_with_mistral(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import mistral_chat_handler
    return mistral_chat_handler(
        input_data=input_data,
        model=model,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
        topp=topp,
        max_tokens=max_tokens,
        random_seed=random_seed,
        top_k=top_k,
        safe_prompt=safe_prompt,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        custom_prompt_arg=custom_prompt_arg,
        app_config=app_config,
    )

def legacy_chat_with_openrouter(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openrouter_chat_handler
    return openrouter_chat_handler(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import moonshot_chat_handler
    return moonshot_chat_handler(
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


def legacy_chat_with_moonshot(
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
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import zai_chat_handler
    return zai_chat_handler(
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


def legacy_chat_with_zai(
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
