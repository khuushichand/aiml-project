from __future__ import annotations

from typing import Any, Dict, List

from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry


PROVIDER_REQUIRES_KEY: Dict[str, bool] = {
    "openai": True,
    "bedrock": True,
    "anthropic": True,
    "cohere": True,
    "groq": True,
    "qwen": True,
    "openrouter": True,
    "deepseek": True,
    "mistral": True,
    "google": True,
    "huggingface": True,
    "moonshot": True,
    "zai": True,
    "llama.cpp": False,
    "kobold": False,
    "ooba": False,
    "tabbyapi": False,
    "vllm": False,
    "local-llm": False,
    "ollama": False,
    "aphrodite": False,
    "mlx": False,
    "custom-openai-api": True,
    "custom-openai-api-2": True,
}

PROVIDER_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "openai": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 60,
        "max_output_tokens_default": 4096,
    },
    "anthropic": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 60,
        "max_output_tokens_default": 8192,
    },
    "google": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 90,
        "max_output_tokens_default": None,
    },
    "mistral": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 60,
        "max_output_tokens_default": 8192,
    },
    "cohere": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 60,
        "max_output_tokens_default": 4096,
    },
    "groq": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 60,
        "max_output_tokens_default": 4096,
    },
    "openrouter": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 90,
        "max_output_tokens_default": 8192,
    },
    "qwen": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 90,
        "max_output_tokens_default": 8192,
    },
    "deepseek": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 90,
        "max_output_tokens_default": 8192,
    },
    "huggingface": {
        "supports_streaming": True,
        "supports_tools": False,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "bedrock": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 8192,
    },
    "custom-openai-api": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 60,
        "max_output_tokens_default": 4096,
    },
    "custom-openai-api-2": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 60,
        "max_output_tokens_default": 4096,
    },
    "mlx": {
        "supports_streaming": True,
        "supports_tools": False,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": None,
    },
    "llama.cpp": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "kobold": {
        "supports_streaming": True,
        "supports_tools": False,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "ooba": {
        "supports_streaming": True,
        "supports_tools": False,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "tabbyapi": {
        "supports_streaming": True,
        "supports_tools": False,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "vllm": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 8192,
    },
    "local-llm": {
        "supports_streaming": True,
        "supports_tools": False,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "ollama": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "aphrodite": {
        "supports_streaming": True,
        "supports_tools": False,
        "default_timeout_seconds": 120,
        "max_output_tokens_default": 2048,
    },
    "moonshot": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 90,
        "max_output_tokens_default": 8192,
    },
    "zai": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 90,
        "max_output_tokens_default": 8192,
    },
}


def list_registered_providers() -> List[str]:
    return get_registry().list_providers()
