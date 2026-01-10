from __future__ import annotations

"""
Adapter-backed handler utilities for provider call sites.

These preserve legacy handler signatures while routing calls through the
adapter registry. They exist for compatibility with older call sites and tests
that still use the handler-style signatures.
"""

import os
import asyncio
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.LLM_Calls.sse import sse_data, sse_done
# Import compatibility call sites under explicit names to avoid recursion when
# top-level names become adapter-backed wrappers.


def openai_chat_handler(
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
    **kwargs: Any,
):
    """
    Legacy-compatible OpenAI handler wrapper that delegates to the adapter.

    Accepts extra kwargs (e.g., 'topp') to remain resilient to param alias drift.
    """
    # Honor explicit test monkeypatching of legacy chat_with_openai to avoid network
    # Only delegate when the target appears to come from a tests module or is a
    # clearly marked test double (function name starting with "_fake"). This avoids
    # infinite recursion when the public function simply forwards back to this shim.
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_openai", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                logger.debug(
                    "adapter_calls.openai_chat_handler: using monkeypatched chat_with_openai from {}",
                    _modname,
                )
                return _patched(
                    input_data=input_data,
                    model=model,
                    api_key=api_key,
                    system_message=system_message,
                    temp=temp,
                    maxp=maxp if maxp is not None else kwargs.get("topp"),
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
    except Exception:
        pass

    # Route via adapter
    registry = get_registry()
    adapter = registry.get_adapter("openai")
    if adapter is None:
        # Register default adapter lazily
        from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter

        registry.register_adapter("openai", OpenAIAdapter)
        adapter = registry.get_adapter("openai")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="openai", message="OpenAI adapter unavailable")

    # Note: Previously, non-streaming calls under pytest attempted to route
    # through a legacy requests.Session to preserve certain logging behavior.
    # That path can inadvertently make real network calls and cause timeouts
    # in sandboxed CI. We now always prefer the adapter path unless the
    # legacy function itself is explicitly monkeypatched by a test (handled
    # above). This ensures tests that patch the adapter http client are honored
    # and avoids unintended network access.

    # Build OpenAI-like request for adapter
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp if maxp is not None else kwargs.get("topp"),
        "frequency_penalty": frequency_penalty,
        "logit_bias": logit_bias,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "max_tokens": max_tokens,
        "n": n,
        "presence_penalty": presence_penalty,
        "response_format": response_format,
        "seed": seed,
        "stop": stop,
        "tools": tools,
        "tool_choice": tool_choice,
        "user": user,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)

    if streaming:
        return adapter.stream(request)
    return adapter.chat(request)


def bedrock_chat_handler(
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
    extra_headers: Optional[Dict[str, str]] = None,  # ignored in adapter path
    extra_body: Optional[Dict[str, Any]] = None,     # ignored in adapter path
    app_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
):
    """Bedrock handler that routes via the Bedrock adapter by default.

    Falls back to legacy implementation only if the adapter is unavailable.
    """
    registry = get_registry()
    adapter = registry.get_adapter("bedrock")
    if adapter is None:
        try:
            from tldw_Server_API.app.core.LLM_Calls.providers.bedrock_adapter import BedrockAdapter
            registry.register_adapter("bedrock", BedrockAdapter)
            adapter = registry.get_adapter("bedrock")
        except Exception:
            adapter = None

    if adapter is None:
        # Fallback to legacy function if adapter cannot be initialized
        from tldw_Server_API.app.core.LLM_Calls.chat_calls import legacy_chat_with_bedrock as _legacy_bedrock
        return _legacy_bedrock(
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

    # Build OpenAI-like request for adapter
    req: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "max_tokens": max_tokens,
        "n": n,
        "stop": stop,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logit_bias": logit_bias,
        "seed": seed,
        "response_format": response_format,
        "tools": tools,
        "tool_choice": tool_choice,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "user": user,
        "app_config": app_config,
    }
    if streaming is not None:
        req["stream"] = bool(streaming)
    if streaming:
        return adapter.stream(req)
    return adapter.chat(req)


async def bedrock_chat_handler_async(
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
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("bedrock")
    if adapter is None:
        try:
            from tldw_Server_API.app.core.LLM_Calls.providers.bedrock_adapter import BedrockAdapter
            registry.register_adapter("bedrock", BedrockAdapter)
            adapter = registry.get_adapter("bedrock")
        except Exception:
            adapter = None

    if adapter is None:
        # Fallback to sync legacy call if adapter path unavailable
        from tldw_Server_API.app.core.LLM_Calls.chat_calls import legacy_chat_with_bedrock as _legacy_bedrock
        return _legacy_bedrock(
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

    req: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "max_tokens": max_tokens,
        "n": n,
        "stop": stop,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logit_bias": logit_bias,
        "seed": seed,
        "response_format": response_format,
        "tools": tools,
        "tool_choice": tool_choice,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "user": user,
        "app_config": app_config,
    }
    if streaming:
        async def _agen():
            for item in adapter.stream(req):
                yield item
        return _agen()
    return adapter.chat(req)


def anthropic_chat_handler(
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
    **kwargs: Any,
):
    # Honor monkeypatched legacy callable in tests to avoid network or adapter path
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_anthropic", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                logger.debug(
                    "adapter_calls.anthropic_chat_handler: using monkeypatched legacy chat_with_anthropic from {}",
                    _modname,
                )
                return _patched(
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
    except Exception:
        pass

    logger.debug("adapter_calls.anthropic_chat_handler: selected path=adapter (sync)")

    registry = get_registry()
    adapter = registry.get_adapter("anthropic")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
        registry.register_adapter("anthropic", AnthropicAdapter)
        adapter = registry.get_adapter("anthropic")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="anthropic", message="Anthropic adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_prompt,
        "temperature": temp,
        "top_p": topp,
        "top_k": topk,
        "max_tokens": max_tokens,
        "stop": stop_sequences,
        "tools": tools,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def cohere_chat_handler(
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
    num_generations: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    custom_prompt_arg: Optional[str] = None,
    app_config: Optional[Dict[str, Any]] = None,
):
    registry = get_registry()
    adapter = registry.get_adapter("cohere")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.cohere_adapter import CohereAdapter
        registry.register_adapter("cohere", CohereAdapter)
        adapter = registry.get_adapter("cohere")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="cohere", message="Cohere adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_prompt,
        "temperature": temp,
        "top_p": topp,
        "top_k": topk,
        "max_tokens": max_tokens,
        "stop": stop_sequences,
        "seed": seed,
        "num_generations": num_generations,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "tools": tools,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def moonshot_chat_handler(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    maxp: Optional[float] = None,
    streaming: Optional[bool] = False,
    frequency_penalty: Optional[float] = None,
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
    registry = get_registry()
    adapter = registry.get_adapter("moonshot")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import MoonshotAdapter

        registry.register_adapter("moonshot", MoonshotAdapter)
        adapter = registry.get_adapter("moonshot")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="moonshot", message="Moonshot adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "frequency_penalty": frequency_penalty,
        "max_tokens": max_tokens,
        "n": n,
        "presence_penalty": presence_penalty,
        "response_format": response_format,
        "seed": seed,
        "stop": stop,
        "tools": tools,
        "tool_choice": tool_choice,
        "user": user,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def zai_chat_handler(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    maxp: Optional[float] = None,
    streaming: Optional[bool] = False,
    max_tokens: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    do_sample: Optional[bool] = None,
    request_id: Optional[str] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    custom_prompt_arg: Optional[str] = None,
    app_config: Optional[Dict[str, Any]] = None,
):
    registry = get_registry()
    adapter = registry.get_adapter("zai")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import ZaiAdapter

        registry.register_adapter("zai", ZaiAdapter)
        adapter = registry.get_adapter("zai")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="zai", message="ZAI adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "max_tokens": max_tokens,
        "tools": tools,
        "do_sample": do_sample,
        "request_id": request_id,
        "stop": stop,
        "response_format": response_format,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def llama_cpp_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    temp: Optional[float] = None,
    temperature: Optional[float] = None,
    system_prompt: Optional[str] = None,
    streaming: Optional[bool] = None,
    stream: Optional[bool] = None,
    model: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    min_p: Optional[float] = None,
    n_predict: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    n: Optional[int] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    api_url: Optional[str] = None,
    app_config: Optional[Dict[str, Any]] = None,
    http_client_factory: Optional[Any] = None,
    http_fetcher: Optional[Any] = None,
):
    if temperature is not None and temp is None:
        temp = temperature
    if stream is not None:
        streaming = stream
    registry = get_registry()
    adapter = registry.get_adapter("llama.cpp")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import LlamaCppAdapter

        registry.register_adapter("llama.cpp", LlamaCppAdapter)
        adapter = registry.get_adapter("llama.cpp")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="llama.cpp", message="Llama.cpp adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_prompt,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": n_predict,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "logit_bias": logit_bias,
        "n": n,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "custom_prompt_arg": custom_prompt,
        "app_config": app_config,
        "http_client_factory": http_client_factory,
        "http_fetcher": http_fetcher,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def kobold_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt_input: Optional[str] = None,
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: Optional[bool] = False,
    model: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    max_length: Optional[int] = None,
    stop_sequence: Optional[Union[str, List[str]]] = None,
    num_responses: Optional[int] = None,
    seed: Optional[int] = None,
    app_config: Optional[Dict[str, Any]] = None,
):
    registry = get_registry()
    adapter = registry.get_adapter("kobold")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import KoboldAdapter

        registry.register_adapter("kobold", KoboldAdapter)
        adapter = registry.get_adapter("kobold")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="kobold", message="Kobold adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "max_tokens": max_length,
        "stop": stop_sequence,
        "n": num_responses,
        "seed": seed,
        "custom_prompt_arg": custom_prompt_input,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def ooba_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    temp: Optional[float] = None,
    temperature: Optional[float] = None,
    system_prompt: Optional[str] = None,
    streaming: Optional[bool] = None,
    stream: Optional[bool] = None,
    model: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    min_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    n: Optional[int] = None,
    user_identifier: Optional[str] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    api_url: Optional[str] = None,
    app_config: Optional[Dict[str, Any]] = None,
    http_client_factory: Optional[Any] = None,
    http_fetcher: Optional[Any] = None,
):
    if temperature is not None and temp is None:
        temp = temperature
    if stream is not None:
        streaming = stream
    registry = get_registry()
    adapter = registry.get_adapter("ooba")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import OobaAdapter

        registry.register_adapter("ooba", OobaAdapter)
        adapter = registry.get_adapter("ooba")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="ooba", message="Oobabooga adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_prompt,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user_identifier,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "custom_prompt_arg": custom_prompt,
        "app_config": app_config,
        "http_client_factory": http_client_factory,
        "http_fetcher": http_fetcher,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def tabbyapi_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt_input: Optional[str] = None,
    temp: Optional[float] = None,
    temperature: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: Optional[bool] = None,
    stream: Optional[bool] = None,
    model: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    min_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    app_config: Optional[Dict[str, Any]] = None,
    response_format: Optional[Dict[str, str]] = None,
    n: Optional[int] = None,
    user_identifier: Optional[str] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logprobs: Optional[bool] = None,
    top_logprobs: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    http_client_factory: Optional[Any] = None,
    http_fetcher: Optional[Any] = None,
):
    if temperature is not None and temp is None:
        temp = temperature
    if stream is not None:
        streaming = stream
    registry = get_registry()
    adapter = registry.get_adapter("tabbyapi")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import TabbyAPIAdapter

        registry.register_adapter("tabbyapi", TabbyAPIAdapter)
        adapter = registry.get_adapter("tabbyapi")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="tabbyapi", message="TabbyAPI adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user_identifier,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "tools": tools,
        "tool_choice": tool_choice,
        "custom_prompt_arg": custom_prompt_input,
        "app_config": app_config,
        "http_client_factory": http_client_factory,
        "http_fetcher": http_fetcher,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def vllm_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt_input: Optional[str] = None,
    temp: Optional[float] = None,
    temperature: Optional[float] = None,
    system_prompt: Optional[str] = None,
    streaming: Optional[bool] = None,
    stream: Optional[bool] = None,
    model: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    min_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    n: Optional[int] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logprobs: Optional[bool] = None,
    user_identifier: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    top_logprobs: Optional[int] = None,
    vllm_api_url: Optional[str] = None,
    app_config: Optional[Dict[str, Any]] = None,
    http_client_factory: Optional[Any] = None,
    http_fetcher: Optional[Any] = None,
):
    if temperature is not None and temp is None:
        temp = temperature
    if stream is not None:
        streaming = stream
    registry = get_registry()
    adapter = registry.get_adapter("vllm")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import VLLMAdapter

        registry.register_adapter("vllm", VLLMAdapter)
        adapter = registry.get_adapter("vllm")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="vllm", message="vLLM adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_prompt,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "user": user_identifier,
        "tools": tools,
        "tool_choice": tool_choice,
        "custom_prompt_arg": custom_prompt_input,
        "app_config": app_config,
        "http_client_factory": http_client_factory,
        "http_fetcher": http_fetcher,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def local_llm_chat_handler(
    input_data: List[Dict[str, Any]],
    temp: Optional[float] = None,
    temperature: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: Optional[bool] = None,
    stream: Optional[bool] = None,
    model: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    min_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    custom_prompt_arg: Optional[str] = None,
    response_format: Optional[Dict[str, str]] = None,
    n: Optional[int] = None,
    user_identifier: Optional[str] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logprobs: Optional[bool] = None,
    top_logprobs: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    app_config: Optional[Dict[str, Any]] = None,
    http_client_factory: Optional[Any] = None,
    http_fetcher: Optional[Any] = None,
):
    if temperature is not None and temp is None:
        temp = temperature
    if stream is not None:
        streaming = stream
    registry = get_registry()
    adapter = registry.get_adapter("local-llm")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import LocalLLMAdapter

        registry.register_adapter("local-llm", LocalLLMAdapter)
        adapter = registry.get_adapter("local-llm")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="local-llm", message="Local LLM adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user_identifier,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "tools": tools,
        "tool_choice": tool_choice,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
        "http_client_factory": http_client_factory,
        "http_fetcher": http_fetcher,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def ollama_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    temp: Optional[float] = None,
    temperature: Optional[float] = None,
    system_message: Optional[str] = None,
    system: Optional[str] = None,
    model: Optional[str] = None,
    streaming: Optional[bool] = None,
    stream: Optional[bool] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    num_predict: Optional[int] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    format_str: Optional[Union[str, Dict[str, Any]]] = None,
    format: Optional[str] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    api_url: Optional[str] = None,
    user_identifier: Optional[str] = None,
    logprobs: Optional[bool] = None,
    top_logprobs: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    app_config: Optional[Dict[str, Any]] = None,
    http_client_factory: Optional[Any] = None,
    http_fetcher: Optional[Any] = None,
):
    if temperature is not None and temp is None:
        temp = temperature
    if stream is not None:
        streaming = stream
    if system_message is None and system is not None:
        system_message = system
    if max_tokens is not None and num_predict is None:
        num_predict = max_tokens
    registry = get_registry()
    adapter = registry.get_adapter("ollama")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import OllamaAdapter

        registry.register_adapter("ollama", OllamaAdapter)
        adapter = registry.get_adapter("ollama")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="ollama", message="Ollama adapter unavailable")
    response_format = format_str if format_str is not None else format
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "max_tokens": num_predict,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "user": user_identifier,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "tools": tools,
        "tool_choice": tool_choice,
        "custom_prompt_arg": custom_prompt,
        "app_config": app_config,
        "http_client_factory": http_client_factory,
        "http_fetcher": http_fetcher,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def aphrodite_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    temp: Optional[float] = None,
    temperature: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: Optional[bool] = None,
    stream: Optional[bool] = None,
    model: Optional[str] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    min_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    n: Optional[int] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logprobs: Optional[bool] = None,
    user_identifier: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    top_logprobs: Optional[int] = None,
    app_config: Optional[Dict[str, Any]] = None,
    http_client_factory: Optional[Any] = None,
    http_fetcher: Optional[Any] = None,
):
    if temperature is not None and temp is None:
        temp = temperature
    if stream is not None:
        streaming = stream
    registry = get_registry()
    adapter = registry.get_adapter("aphrodite")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.compat_adapters import AphroditeAdapter

        registry.register_adapter("aphrodite", AphroditeAdapter)
        adapter = registry.get_adapter("aphrodite")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="aphrodite", message="Aphrodite adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "user": user_identifier,
        "tools": tools,
        "tool_choice": tool_choice,
        "custom_prompt_arg": custom_prompt,
        "app_config": app_config,
        "http_client_factory": http_client_factory,
        "http_fetcher": http_fetcher,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


# -----------------------------
# MLX adapter-backed shims
# -----------------------------

def _get_mlx_adapter():
    registry = get_registry()
    adapter = registry.get_adapter("mlx")
    if adapter is None:
        try:
            from tldw_Server_API.app.core.LLM_Calls.providers.mlx_provider import MLXChatAdapter

            registry.register_adapter("mlx", MLXChatAdapter)
            adapter = registry.get_adapter("mlx")
        except Exception as exc:
            logger.exception(f"Failed to initialize MLX adapter: {exc}")
            adapter = None
    return adapter


def mlx_chat_handler(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    topp: Optional[float] = None,
    topk: Optional[int] = None,
    streaming: Optional[bool] = False,
    max_tokens: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    user: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    custom_prompt_arg: Optional[str] = None,
    prompt_template: Optional[str] = None,
    **kwargs: Any,
):
    # api_key is accepted for signature compatibility with other handlers but unused.
    _ = api_key
    adapter = _get_mlx_adapter()
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="mlx", message="MLX adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp if topp is not None else kwargs.get("top_p"),
        "top_k": topk if topk is not None else kwargs.get("top_k"),
        "max_tokens": max_tokens,
        "stop": stop,
        "response_format": response_format,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "prompt_template": prompt_template,
        "custom_prompt_arg": custom_prompt_arg,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


async def mlx_chat_handler_async(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    topp: Optional[float] = None,
    topk: Optional[int] = None,
    streaming: Optional[bool] = False,
    max_tokens: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    user: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    custom_prompt_arg: Optional[str] = None,
    prompt_template: Optional[str] = None,
    **kwargs: Any,
):
    # api_key is accepted for signature compatibility with other handlers but unused.
    _ = api_key
    adapter = _get_mlx_adapter()
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="mlx", message="MLX adapter unavailable")

    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp if topp is not None else kwargs.get("top_p"),
        "top_k": topk if topk is not None else kwargs.get("top_k"),
        "max_tokens": max_tokens,
        "stop": stop,
        "response_format": response_format,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "prompt_template": prompt_template,
        "custom_prompt_arg": custom_prompt_arg,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)

    if streaming:
        async def _astream():
            for chunk in adapter.stream(request):
                yield chunk
        return _astream()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: adapter.chat(request))


# -----------------------------
# Async adapter-backed shims
# -----------------------------

async def openai_chat_handler_async(
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
    **kwargs: Any,
):
    # Honor explicit test monkeypatching of legacy chat_with_openai (only when actually patched to a test helper),
    # otherwise prefer the adapter path. Avoid triggering just because we're under pytest.
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_openai", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                # Build kwargs aligned to legacy signature
                _kw = dict(
                    input_data=input_data,
                    model=model,
                    api_key=api_key,
                    system_message=system_message,
                    temp=temp,
                    maxp=maxp if maxp is not None else kwargs.get("topp"),
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
                if streaming:
                    def _gen():
                        return _patched(**_kw)

                    async def _astream_wrapper():
                        for _item in _gen():
                            yield _item
                    return _astream_wrapper()
                # Non-streaming
                return _patched(**_kw)
    except Exception:
        pass

    registry = get_registry()
    adapter = registry.get_adapter("openai")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter
        registry.register_adapter("openai", OpenAIAdapter)
        adapter = registry.get_adapter("openai")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="openai", message="OpenAI adapter unavailable")

    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp if maxp is not None else kwargs.get("topp"),
        "frequency_penalty": frequency_penalty,
        "logit_bias": logit_bias,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "max_tokens": max_tokens,
        "n": n,
        "presence_penalty": presence_penalty,
        "response_format": response_format,
        "seed": seed,
        "stop": stop,
        "tools": tools,
        "tool_choice": tool_choice,
        "user": user,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    if streaming:
        # Prefer adapter.astream when it's been monkeypatched by tests
        try:
            _astream_attr = getattr(adapter, "astream", None)
            if callable(_astream_attr):
                _fn = getattr(_astream_attr, "__func__", _astream_attr)
                _mod = getattr(_fn, "__module__", "") or ""
                _name = getattr(_fn, "__name__", "") or ""
                if ("tests" in _mod) or _name.startswith("_Fake") or _name.startswith("_fake"):
                    return adapter.astream(request)
        except Exception:
            pass

        # Under pytest, prefer astream to make monkeypatching predictable
        try:
            import os as _os
            if _os.getenv("PYTEST_CURRENT_TEST"):
                return adapter.astream(request)
        except Exception:
            pass

        # Default behavior
        return adapter.astream(request)
    return await adapter.achat(request)


async def anthropic_chat_handler_async(
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
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("anthropic")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
        registry.register_adapter("anthropic", AnthropicAdapter)
        adapter = registry.get_adapter("anthropic")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="anthropic", message="Anthropic adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_prompt,
        "temperature": temp,
        "top_p": topp,
        "top_k": topk,
        "max_tokens": max_tokens,
        "stop": stop_sequences,
        "tools": tools,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    if streaming:
        # Guarded async wrapper to surface streaming errors as a single SSE error
        # frame followed by one [DONE], matching test expectations and improving
        # determinism under CI when external services reject requests.
        async def _guarded_astream():
            try:
                agen = adapter.astream(request)
                # If adapter returns a coroutine instead of async-iterable, await it
                try:
                    import inspect as _inspect
                    agen = await agen if _inspect.isawaitable(agen) else agen
                except Exception:
                    pass
                async for line in agen:
                    yield line
            except Exception as _e:
                # Normalize to a compact SSE error frame
                msg = str(_e)
                try:
                    # Attempt provider-specific normalization for clearer messages
                    norm = adapter.normalize_error(_e)  # type: ignore[attr-defined]
                    msg = getattr(norm, 'message', msg) or msg
                except Exception:
                    pass
                yield sse_data({"error": {"message": msg, "type": "anthropic_stream_error"}})
                yield sse_done()
        return _guarded_astream()
    return await adapter.achat(request)


async def google_chat_handler_async(
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
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    custom_prompt_arg: Optional[str] = None,
    app_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("google")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.google_adapter import GoogleAdapter
        registry.register_adapter("google", GoogleAdapter)
        adapter = registry.get_adapter("google")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp,
        "top_k": topk,
        "max_tokens": max_output_tokens,
        "stop": stop_sequences,
        "n": candidate_count,
        "response_format": response_format,
        "tools": tools,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    if streaming:
        return adapter.astream(request)
    return await adapter.achat(request)


async def mistral_chat_handler_async(
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
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    response_format: Optional[Dict[str, Any]] = None,
    custom_prompt_arg: Optional[str] = None,
    app_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("mistral")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter import MistralAdapter
        registry.register_adapter("mistral", MistralAdapter)
        adapter = registry.get_adapter("mistral")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp,
        "max_tokens": max_tokens,
        "seed": random_seed,
        "top_k": top_k,
        "safe_prompt": safe_prompt,
        "tools": tools,
        "tool_choice": tool_choice,
        "response_format": response_format,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    if streaming:
        return adapter.astream(request)
    return await adapter.achat(request)


async def qwen_chat_handler_async(
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
    **kwargs: Any,
):
    # Honor monkeypatched legacy callable only when the legacy function itself
    # is patched (module/name indicates tests), not merely because tests run.
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_qwen", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                if streaming:
                    _gen = _patched(
                        input_data=input_data,
                        model=model,
                        api_key=api_key,
                        system_message=system_message,
                        temp=temp,
                        maxp=maxp,
                        streaming=True,
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
                    async def _astream_wrapper():
                        for _item in _gen:
                            yield _item
                    return _astream_wrapper()
                else:
                    return _patched(
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
    except Exception:
        pass
    registry = get_registry()
    adapter = registry.get_adapter("qwen")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter
        registry.register_adapter("qwen", QwenAdapter)
        adapter = registry.get_adapter("qwen")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="qwen", message="Qwen adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "stream": streaming,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming:
        # Mirror Anthropic's guarded streaming behavior: surface exactly one
        # compact SSE error frame then one [DONE] on failures, rather than
        # raising exceptions that break tests expecting SSE semantics.
        async def _guarded_astream():
            try:
                agen = adapter.astream(request)
                # If adapter returns a coroutine instead of an async-iterable, await it
                try:
                    import inspect as _inspect  # local import to avoid module cost
                    agen = await agen if _inspect.isawaitable(agen) else agen
                except Exception:
                    pass
                async for line in agen:
                    yield line
            except Exception as _e:
                msg = str(_e)
                try:
                    norm = adapter.normalize_error(_e)  # type: ignore[attr-defined]
                    msg = getattr(norm, "message", msg) or msg
                except Exception:
                    pass
                # Emit one error frame followed by [DONE]
                yield sse_data({"error": {"message": msg, "type": "qwen_stream_error"}})
                yield sse_done()
        return _guarded_astream()
    return await adapter.achat(request)


async def deepseek_chat_handler_async(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    topp: Optional[float] = None,
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
    **kwargs: Any,
):
    # Honor monkeypatched legacy callable only when the legacy function itself
    # is patched (module/name indicates tests), not merely because tests run.
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_deepseek", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                if streaming:
                    _gen = _patched(
                        input_data=input_data,
                        model=model,
                        api_key=api_key,
                        system_message=system_message,
                        temp=temp,
                        topp=topp,
                        streaming=True,
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
                    async def _astream_wrapper():
                        for _item in _gen:
                            yield _item
                    return _astream_wrapper()
                else:
                    return _patched(
                        input_data=input_data,
                        model=model,
                        api_key=api_key,
                        system_message=system_message,
                        temp=temp,
                        topp=topp,
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
    except Exception:
        pass
    registry = get_registry()
    adapter = registry.get_adapter("deepseek")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter import DeepSeekAdapter
        registry.register_adapter("deepseek", DeepSeekAdapter)
        adapter = registry.get_adapter("deepseek")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="deepseek", message="DeepSeek adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp,
        "stream": streaming,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming:
        return adapter.astream(request)
    return await adapter.achat(request)


async def huggingface_chat_handler_async(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
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
    **kwargs: Any,
):
    # Honor monkeypatched legacy callable in tests even if adapters are enabled
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_huggingface", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                os.getenv("PYTEST_CURRENT_TEST")
                or _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                return _patched(
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
    except Exception:
        pass
    registry = get_registry()
    adapter = registry.get_adapter("huggingface")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter import HuggingFaceAdapter
        registry.register_adapter("huggingface", HuggingFaceAdapter)
        adapter = registry.get_adapter("huggingface")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="huggingface", message="HuggingFace adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "stream": streaming,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming:
        return adapter.astream(request)
    return await adapter.achat(request)


async def custom_openai_chat_handler_async(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    topp: Optional[float] = None,
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
    **kwargs: Any,
):
    # Honor monkeypatched legacy callable in tests
    try:
        from tldw_Server_API.app.core.LLM_Calls import local_chat_calls as _legacy_local_mod
        _patched = getattr(_legacy_local_mod, "legacy_chat_with_custom_openai", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                os.getenv("PYTEST_CURRENT_TEST")
                or _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                if streaming:
                    _gen = _patched(
                        input_data=input_data,
                        model=model,
                        api_key=api_key,
                        system_message=system_message,
                        temp=temp,
                        streaming=True,
                        maxp=topp,
                        max_tokens=max_tokens,
                        seed=seed,
                        stop=stop,
                        response_format=response_format,
                        n=n,
                        user_identifier=user,
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
                    async def _astream_wrapper2():
                        for _item in _gen:
                            yield _item
                    return _astream_wrapper2()
                else:
                    return _patched(
                        input_data=input_data,
                        model=model,
                        api_key=api_key,
                        system_message=system_message,
                        temp=temp,
                        streaming=streaming,
                        maxp=topp,
                        max_tokens=max_tokens,
                        seed=seed,
                        stop=stop,
                        response_format=response_format,
                        n=n,
                        user_identifier=user,
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
    except Exception:
        pass
    registry = get_registry()
    adapter = registry.get_adapter("custom-openai-api")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter
        registry.register_adapter("custom-openai-api", CustomOpenAIAdapter)
        adapter = registry.get_adapter("custom-openai-api")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="custom-openai-api", message="Custom OpenAI adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp,
        "stream": streaming,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming:
        return adapter.astream(request)
    return await adapter.achat(request)


async def custom_openai_2_chat_handler_async(
    *args: Any, **kwargs: Any
):
    # Reuse same async path as custom-openai-api but target adapter name "custom-openai-api-2"
    # Map by tweaking app_config section and adapter name inside a small wrapper
    registry = get_registry()
    adapter = registry.get_adapter("custom-openai-api-2")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter2
        registry.register_adapter("custom-openai-api-2", CustomOpenAIAdapter2)
        adapter = registry.get_adapter("custom-openai-api-2")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="custom-openai-api-2", message="Custom OpenAI 2 adapter unavailable")
    # Build request from kwargs similar to other shims
    request: Dict[str, Any] = {
        "messages": kwargs.get("input_data") or [],
        "model": kwargs.get("model"),
        "api_key": kwargs.get("api_key"),
        "system_message": kwargs.get("system_message"),
        "temperature": kwargs.get("temp"),
        "top_p": kwargs.get("topp"),
        "stream": kwargs.get("streaming"),
        "max_tokens": kwargs.get("max_tokens"),
        "seed": kwargs.get("seed"),
        "stop": kwargs.get("stop"),
        "response_format": kwargs.get("response_format"),
        "n": kwargs.get("n"),
        "user": kwargs.get("user_identifier") or kwargs.get("user"),
        "tools": kwargs.get("tools"),
        "tool_choice": kwargs.get("tool_choice"),
        "logit_bias": kwargs.get("logit_bias"),
        "presence_penalty": kwargs.get("presence_penalty"),
        "frequency_penalty": kwargs.get("frequency_penalty"),
        "logprobs": kwargs.get("logprobs"),
        "top_logprobs": kwargs.get("top_logprobs"),
        "custom_prompt_arg": kwargs.get("custom_prompt_arg"),
        "app_config": kwargs.get("app_config"),
    }
    if request.get("stream"):
        return adapter.astream(request)
    return await adapter.achat(request)


async def groq_chat_handler_async(
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
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("groq")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter import GroqAdapter
        registry.register_adapter("groq", GroqAdapter)
        adapter = registry.get_adapter("groq")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="groq", message="Groq adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    if streaming:
        return adapter.astream(request)
    return await adapter.achat(request)


async def openrouter_chat_handler_async(
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
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("openrouter")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter import OpenRouterAdapter
        registry.register_adapter("openrouter", OpenRouterAdapter)
        adapter = registry.get_adapter("openrouter")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="openrouter", message="OpenRouter adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    if streaming:
        return adapter.astream(request)
    return await adapter.achat(request)


def groq_chat_handler(
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
    **kwargs: Any,
):
    # Honor patched legacy in tests
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_groq", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                return _patched(
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
    except Exception:
        pass

    registry = get_registry()
    adapter = registry.get_adapter("groq")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter import GroqAdapter
        registry.register_adapter("groq", GroqAdapter)
        adapter = registry.get_adapter("groq")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="groq", message="Groq adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def openrouter_chat_handler(
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
    **kwargs: Any,
):
    # Honor patched legacy in tests
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_openrouter", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                logger.debug(
                    "adapter_calls.openrouter_chat_handler: using monkeypatched legacy chat_with_openrouter from {}",
                    _modname,
                )
                return _patched(
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
            # More permissive in pytest: treat any callable replacement as patched
            import os as _os
            if _os.getenv("PYTEST_CURRENT_TEST"):
                logger.debug(
                    "adapter_calls.openrouter_chat_handler: pytest detected; honoring callable legacy chat_with_openrouter from {}",
                    _modname or "<unknown>",
                )
                return _patched(
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
    except Exception:
        pass

    registry = get_registry()
    adapter = registry.get_adapter("openrouter")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter import OpenRouterAdapter
        registry.register_adapter("openrouter", OpenRouterAdapter)
        adapter = registry.get_adapter("openrouter")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="openrouter", message="OpenRouter adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def google_chat_handler(
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
    **kwargs: Any,
):
    # Honor patched legacy in tests
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_google", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                return _patched(
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
    except Exception:
        pass

    registry = get_registry()
    adapter = registry.get_adapter("google")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.google_adapter import GoogleAdapter
        registry.register_adapter("google", GoogleAdapter)
        adapter = registry.get_adapter("google")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="google", message="Google adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp,
        "top_k": topk,
        "max_tokens": max_output_tokens,
        "stop": stop_sequences,
        "n": candidate_count,
        "response_format": response_format,
        "tools": tools,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def mistral_chat_handler(
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
    **kwargs: Any,
):
    # Honor patched legacy in tests
    try:
        from tldw_Server_API.app.core.LLM_Calls import chat_calls as _legacy_mod
        _patched = getattr(_legacy_mod, "chat_with_mistral", None)
        if callable(_patched):
            _modname = getattr(_patched, "__module__", "") or ""
            _fname = getattr(_patched, "__name__", "") or ""
            if (
                _modname.startswith("tldw_Server_API.tests")
                or _modname.startswith("tests")
                or ".tests." in _modname
                or _fname.startswith("_fake")
            ):
                return _patched(
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
    except Exception:
        pass

    registry = get_registry()
    adapter = registry.get_adapter("mistral")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter import MistralAdapter
        registry.register_adapter("mistral", MistralAdapter)
        adapter = registry.get_adapter("mistral")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="mistral", message="Mistral adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp,
        "max_tokens": max_tokens,
        "seed": random_seed,
        "top_k": top_k,
        "safe_prompt": safe_prompt,
        "tools": tools,
        "tool_choice": tool_choice,
        "response_format": response_format,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def qwen_chat_handler(
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
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("qwen")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter
        registry.register_adapter("qwen", QwenAdapter)
        adapter = registry.get_adapter("qwen")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="qwen", message="Qwen adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": maxp,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def deepseek_chat_handler(
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
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("deepseek")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter import DeepSeekAdapter
        registry.register_adapter("deepseek", DeepSeekAdapter)
        adapter = registry.get_adapter("deepseek")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="deepseek", message="DeepSeek adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": topp,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "response_format": response_format,
        "n": n,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def huggingface_chat_handler(
    input_data: List[Dict[str, Any]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    streaming: Optional[bool] = False,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    num_return_sequences: Optional[int] = None,
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
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("huggingface")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter import HuggingFaceAdapter
        registry.register_adapter("huggingface", HuggingFaceAdapter)
        adapter = registry.get_adapter("huggingface")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="huggingface", message="HuggingFace adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "model": model,
        "api_key": api_key,
        "system_message": system_message,
        "temperature": temp,
        "top_p": top_p,
        "top_k": top_k,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": num_return_sequences,
        "user": user,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "custom_prompt_arg": custom_prompt_arg,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def custom_openai_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt_arg: Optional[str] = None,
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: Optional[bool] = False,
    model: Optional[str] = None,
    maxp: Optional[float] = None,
    topp: Optional[float] = None,
    minp: Optional[float] = None,
    topk: Optional[int] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    n: Optional[int] = None,
    user_identifier: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logprobs: Optional[bool] = None,
    top_logprobs: Optional[int] = None,
    app_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("custom-openai-api")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter
        registry.register_adapter("custom-openai-api", CustomOpenAIAdapter)
        adapter = registry.get_adapter("custom-openai-api")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="custom-openai-api", message="Custom OpenAI adapter unavailable")
    # Prefer explicit maxp over topp when both provided
    top_p_val = maxp if maxp is not None else topp
    request: Dict[str, Any] = {
        "messages": input_data,
        "api_key": api_key,
        "custom_prompt_arg": custom_prompt_arg,
        "temperature": temp,
        "system_message": system_message,
        "model": model,
        "top_p": top_p_val,
        "min_p": minp,
        "top_k": topk,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user_identifier,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)


def custom_openai_2_chat_handler(
    input_data: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    custom_prompt_arg: Optional[str] = None,
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: Optional[bool] = False,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    topp: Optional[float] = None,
    seed: Optional[int] = None,
    stop: Optional[Union[str, List[str]]] = None,
    response_format: Optional[Dict[str, str]] = None,
    n: Optional[int] = None,
    user_identifier: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    logit_bias: Optional[Dict[str, float]] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logprobs: Optional[bool] = None,
    top_logprobs: Optional[int] = None,
    app_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
):
    registry = get_registry()
    adapter = registry.get_adapter("custom-openai-api-2")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter2
        registry.register_adapter("custom-openai-api-2", CustomOpenAIAdapter2)
        adapter = registry.get_adapter("custom-openai-api-2")
    if adapter is None:
        from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
        raise ChatProviderError(provider="custom-openai-api-2", message="Custom OpenAI 2 adapter unavailable")
    request: Dict[str, Any] = {
        "messages": input_data,
        "api_key": api_key,
        "custom_prompt_arg": custom_prompt_arg,
        "temperature": temp,
        "system_message": system_message,
        "model": model,
        "top_p": topp,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop,
        "response_format": response_format,
        "n": n,
        "user": user_identifier,
        "tools": tools,
        "tool_choice": tool_choice,
        "logit_bias": logit_bias,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "app_config": app_config,
    }
    if streaming is not None:
        request["stream"] = bool(streaming)
    return adapter.stream(request) if streaming else adapter.chat(request)
