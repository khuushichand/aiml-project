from __future__ import annotations

"""
Adapter-backed handler shims for provider_config dispatch tables.

These preserve legacy handler signatures while optionally routing calls
through the adapter registry when enabled by feature flags.
"""

import os
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import (
    chat_with_openai as _legacy_chat_with_openai,
    chat_with_anthropic as _legacy_chat_with_anthropic,
    chat_with_groq as _legacy_chat_with_groq,
    chat_with_openrouter as _legacy_chat_with_openrouter,
    chat_with_google as _legacy_chat_with_google,
    chat_with_mistral as _legacy_chat_with_mistral,
    chat_with_qwen as _legacy_chat_with_qwen,
    chat_with_deepseek as _legacy_chat_with_deepseek,
    chat_with_huggingface as _legacy_chat_with_huggingface,
)
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls_Local import (
    chat_with_custom_openai as _legacy_chat_with_custom_openai,
    chat_with_custom_openai_2 as _legacy_chat_with_custom_openai_2,
)


def _flag_enabled(*names: str) -> bool:
    for n in names:
        v = os.getenv(n)
        if v and v.lower() in {"1", "true", "yes", "on"}:
            return True
    return False


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
    Legacy-compatible OpenAI handler shim that optionally delegates to the adapter.

    Accepts extra kwargs (e.g., 'topp') to remain resilient to PROVIDER_PARAM_MAP drift.
    """
    use_adapter = _flag_enabled("LLM_ADAPTERS_OPENAI", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_openai(
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

    # Route via adapter
    registry = get_registry()
    adapter = registry.get_adapter("openai")
    if adapter is None:
        # Register default adapter lazily
        from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter

        registry.register_adapter("openai", OpenAIAdapter)
        adapter = registry.get_adapter("openai")

    if adapter is None:
        logger.warning("OpenAI adapter unavailable; falling back to legacy handler")
        return _legacy_chat_with_openai(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_ANTHROPIC", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_anthropic(
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

    registry = get_registry()
    adapter = registry.get_adapter("anthropic")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
        registry.register_adapter("anthropic", AnthropicAdapter)
        adapter = registry.get_adapter("anthropic")
    if adapter is None:
        return _legacy_chat_with_anthropic(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_GROQ", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_groq(
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
    registry = get_registry()
    adapter = registry.get_adapter("groq")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter import GroqAdapter
        registry.register_adapter("groq", GroqAdapter)
        adapter = registry.get_adapter("groq")
    if adapter is None:
        return _legacy_chat_with_groq(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_OPENROUTER", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_openrouter(
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
    registry = get_registry()
    adapter = registry.get_adapter("openrouter")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter import OpenRouterAdapter
        registry.register_adapter("openrouter", OpenRouterAdapter)
        adapter = registry.get_adapter("openrouter")
    if adapter is None:
        return _legacy_chat_with_openrouter(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_GOOGLE", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_google(
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
    registry = get_registry()
    adapter = registry.get_adapter("google")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.google_adapter import GoogleAdapter
        registry.register_adapter("google", GoogleAdapter)
        adapter = registry.get_adapter("google")
    if adapter is None:
        return _legacy_chat_with_google(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_MISTRAL", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_mistral(
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
    registry = get_registry()
    adapter = registry.get_adapter("mistral")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter import MistralAdapter
        registry.register_adapter("mistral", MistralAdapter)
        adapter = registry.get_adapter("mistral")
    if adapter is None:
        return _legacy_chat_with_mistral(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_QWEN", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_qwen(
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

    registry = get_registry()
    adapter = registry.get_adapter("qwen")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.qwen_adapter import QwenAdapter
        registry.register_adapter("qwen", QwenAdapter)
        adapter = registry.get_adapter("qwen")
    if adapter is None:
        return _legacy_chat_with_qwen(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_DEEPSEEK", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_deepseek(
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

    registry = get_registry()
    adapter = registry.get_adapter("deepseek")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.deepseek_adapter import DeepSeekAdapter
        registry.register_adapter("deepseek", DeepSeekAdapter)
        adapter = registry.get_adapter("deepseek")
    if adapter is None:
        return _legacy_chat_with_deepseek(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_HUGGINGFACE", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_huggingface(
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
    registry = get_registry()
    adapter = registry.get_adapter("huggingface")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.huggingface_adapter import HuggingFaceAdapter
        registry.register_adapter("huggingface", HuggingFaceAdapter)
        adapter = registry.get_adapter("huggingface")
    if adapter is None:
        return _legacy_chat_with_huggingface(
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_CUSTOM_OPENAI", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_custom_openai(
            input_data=input_data,
            api_key=api_key,
            custom_prompt_arg=custom_prompt_arg,
            temp=temp,
            system_message=system_message,
            streaming=streaming,
            model=model,
            maxp=maxp,
            topp=topp,
            minp=minp,
            topk=topk,
            max_tokens=max_tokens,
            seed=seed,
            stop=stop,
            response_format=response_format,
            n=n,
            user_identifier=user_identifier,
            tools=tools,
            tool_choice=tool_choice,
            logit_bias=logit_bias,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            app_config=app_config,
        )
    registry = get_registry()
    adapter = registry.get_adapter("custom-openai-api")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter
        registry.register_adapter("custom-openai-api", CustomOpenAIAdapter)
        adapter = registry.get_adapter("custom-openai-api")
    if adapter is None:
        return _legacy_chat_with_custom_openai(
            input_data=input_data,
            api_key=api_key,
            custom_prompt_arg=custom_prompt_arg,
            temp=temp,
            system_message=system_message,
            streaming=streaming,
            model=model,
            maxp=maxp,
            topp=topp,
            minp=minp,
            topk=topk,
            max_tokens=max_tokens,
            seed=seed,
            stop=stop,
            response_format=response_format,
            n=n,
            user_identifier=user_identifier,
            tools=tools,
            tool_choice=tool_choice,
            logit_bias=logit_bias,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            app_config=app_config,
        )
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
    use_adapter = _flag_enabled("LLM_ADAPTERS_CUSTOM_OPENAI_2", "LLM_ADAPTERS_ENABLED")
    if not use_adapter:
        return _legacy_chat_with_custom_openai_2(
            input_data=input_data,
            api_key=api_key,
            custom_prompt_arg=custom_prompt_arg,
            temp=temp,
            system_message=system_message,
            streaming=streaming,
            model=model,
            max_tokens=max_tokens,
            topp=topp,
            seed=seed,
            stop=stop,
            response_format=response_format,
            n=n,
            user_identifier=user_identifier,
            tools=tools,
            tool_choice=tool_choice,
            logit_bias=logit_bias,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            app_config=app_config,
        )
    registry = get_registry()
    adapter = registry.get_adapter("custom-openai-api-2")
    if adapter is None:
        from tldw_Server_API.app.core.LLM_Calls.providers.custom_openai_adapter import CustomOpenAIAdapter2
        registry.register_adapter("custom-openai-api-2", CustomOpenAIAdapter2)
        adapter = registry.get_adapter("custom-openai-api-2")
    if adapter is None:
        return _legacy_chat_with_custom_openai_2(
            input_data=input_data,
            api_key=api_key,
            custom_prompt_arg=custom_prompt_arg,
            temp=temp,
            system_message=system_message,
            streaming=streaming,
            model=model,
            max_tokens=max_tokens,
            topp=topp,
            seed=seed,
            stop=stop,
            response_format=response_format,
            n=n,
            user_identifier=user_identifier,
            tools=tools,
            tool_choice=tool_choice,
            logit_bias=logit_bias,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            app_config=app_config,
        )
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
