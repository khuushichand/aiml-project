"""
Legacy local summarization helpers.

These wrappers now route through the adapter-backed summarization path in
Summarization_General_Lib to keep a single LLM call surface.
"""
from __future__ import annotations

from typing import Any, Generator, Optional, Union

from tldw_Server_API.app.core.LLM_Calls import Summarization_General_Lib as sgl
from tldw_Server_API.app.core.LLM_Calls.deprecation import log_legacy_once


def _log_legacy() -> None:
    log_legacy_once(
        "local_summarization_lib",
        "Local_Summarization_Lib is deprecated; use Summarization_General_Lib.analyze instead. "
        "Provider-specific overrides are ignored in favor of config.",
    )


def _warn_ignored_override(param_name: str, value: Optional[str], default: Optional[str] = None) -> None:
    if value is None:
        return
    if default is not None and str(value).strip() == str(default).strip():
        return
    log_legacy_once(
        f"local_summarization_ignore_{param_name}",
        f"{param_name} overrides are ignored; local provider URLs are config-only.",
    )


def _summarize(
    api_name: str,
    input_data: Any,
    custom_prompt_arg: Optional[str],
    *,
    api_key: Optional[str] = None,
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    _log_legacy()
    return sgl.analyze(
        api_name=api_name,
        input_data=input_data,
        custom_prompt_arg=custom_prompt_arg,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_local_llm(
    input_data: Any,
    custom_prompt_arg: Optional[str],
    temp: Optional[float],
    system_message: Optional[str] = None,
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    return _summarize(
        "local-llm",
        input_data,
        custom_prompt_arg,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_llama(
    input_data: Any,
    custom_prompt: Optional[str],
    api_key: Optional[str] = None,
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    return _summarize(
        "llama.cpp",
        input_data,
        custom_prompt,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_kobold(
    input_data: Any,
    api_key: Optional[str],
    custom_prompt_input: Optional[str],
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    kobold_api_ip: str = "http://127.0.0.1:5001/api/v1/generate",
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    _warn_ignored_override("kobold_api_ip", kobold_api_ip, "http://127.0.0.1:5001/api/v1/generate")
    return _summarize(
        "kobold",
        input_data,
        custom_prompt_input,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_oobabooga(
    input_data: Any,
    api_key: Optional[str],
    custom_prompt: Optional[str],
    system_message: Optional[str] = None,
    temp: Optional[float] = None,
    api_url: Optional[str] = None,
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    _warn_ignored_override("api_url", api_url)
    return _summarize(
        "ooba",
        input_data,
        custom_prompt,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_tabbyapi(
    input_data: Any,
    custom_prompt_input: Optional[str],
    system_message: Optional[str] = None,
    api_key: Optional[str] = None,
    temp: Optional[float] = None,
    api_IP: str = "http://127.0.0.1:5000/v1/chat/completions",
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    _warn_ignored_override("api_IP", api_IP, "http://127.0.0.1:5000/v1/chat/completions")
    return _summarize(
        "tabbyapi",
        input_data,
        custom_prompt_input,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_vllm(
    api_key: Optional[str],
    input_data: Any,
    custom_prompt_arg: Optional[str],
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    return _summarize(
        "vllm",
        input_data,
        custom_prompt_arg,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_ollama(
    input_data: Any,
    custom_prompt: Optional[str],
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: int = 5,
    retry_delay: int = 20,
    streaming: bool = False,
    top_p: Optional[float] = None,
) -> Union[str, Generator[str, None, None]]:
    _warn_ignored_override("api_url", api_url)
    return _summarize(
        "ollama",
        input_data,
        custom_prompt,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_custom_openai(
    api_key: Optional[str],
    input_data: Any,
    custom_prompt_arg: Optional[str],
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    return _summarize(
        "custom-openai-api",
        input_data,
        custom_prompt_arg,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )


def summarize_with_custom_openai_2(
    api_key: Optional[str],
    input_data: Any,
    custom_prompt_arg: Optional[str],
    temp: Optional[float] = None,
    system_message: Optional[str] = None,
    streaming: bool = False,
) -> Union[str, Generator[str, None, None]]:
    return _summarize(
        "custom-openai-api-2",
        input_data,
        custom_prompt_arg,
        api_key=api_key,
        system_message=system_message,
        temp=temp,
        streaming=streaming,
    )
