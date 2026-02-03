"""
Legacy local summarization helpers.

These wrappers now route through the adapter-backed summarization path in
Summarization_General_Lib to keep a single LLM call surface.
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Any, Union

from tldw_Server_API.app.core.LLM_Calls import Summarization_General_Lib as sgl
from tldw_Server_API.app.core.LLM_Calls.deprecation import log_legacy_once


def _log_legacy() -> None:
    log_legacy_once(
        "local_summarization_lib",
        "Local_Summarization_Lib is deprecated; use Summarization_General_Lib.analyze instead. "
        "Provider-specific overrides are ignored in favor of config.",
    )


def _warn_ignored_override(param_name: str, value: str | None, default: str | None = None) -> None:
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
    custom_prompt_arg: str | None,
    *,
    api_key: str | None = None,
    system_message: str | None = None,
    temp: float | None = None,
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
    custom_prompt_arg: str | None,
    temp: float | None,
    system_message: str | None = None,
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
    custom_prompt: str | None,
    api_key: str | None = None,
    temp: float | None = None,
    system_message: str | None = None,
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
    api_key: str | None,
    custom_prompt_input: str | None,
    system_message: str | None = None,
    temp: float | None = None,
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
    api_key: str | None,
    custom_prompt: str | None,
    system_message: str | None = None,
    temp: float | None = None,
    api_url: str | None = None,
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
    custom_prompt_input: str | None,
    system_message: str | None = None,
    api_key: str | None = None,
    temp: float | None = None,
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
    api_key: str | None,
    input_data: Any,
    custom_prompt_arg: str | None,
    temp: float | None = None,
    system_message: str | None = None,
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
    custom_prompt: str | None,
    api_url: str | None = None,
    api_key: str | None = None,
    temp: float | None = None,
    system_message: str | None = None,
    model: str | None = None,
    max_retries: int = 5,
    retry_delay: int = 20,
    streaming: bool = False,
    top_p: float | None = None,
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
    api_key: str | None,
    input_data: Any,
    custom_prompt_arg: str | None,
    temp: float | None = None,
    system_message: str | None = None,
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
    api_key: str | None,
    input_data: Any,
    custom_prompt_arg: str | None,
    temp: float | None = None,
    system_message: str | None = None,
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
