from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry

PROVIDER_REQUIRES_KEY: dict[str, bool] = {
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

DEFAULT_BYOK_ALLOWED_FIELDS: set[str] = {"org_id", "project_id"}

BYOK_CREDENTIAL_FIELDS: dict[str, dict[str, set[str]]] = {
    "openai": {"allowed": {"org_id", "project_id"}, "required": set()},
    "openrouter": {"allowed": {"org_id", "project_id"}, "required": set()},
    "custom-openai-api": {"allowed": {"org_id", "project_id"}, "required": set()},
    "custom-openai-api-2": {"allowed": {"org_id", "project_id"}, "required": set()},
}


def provider_requires_api_key(provider: str) -> bool:
    provider_norm = (provider or "").strip().lower()
    if not provider_norm:
        return True
    return PROVIDER_REQUIRES_KEY.get(provider_norm, True)


def get_byok_credential_policy(provider: str) -> tuple[set[str], set[str]]:
    provider_norm = (provider or "").strip().lower()
    policy = BYOK_CREDENTIAL_FIELDS.get(provider_norm, {})
    allowed = set(policy.get("allowed", DEFAULT_BYOK_ALLOWED_FIELDS))
    required = set(policy.get("required", set()))
    if required and not required.issubset(allowed):
        allowed |= required
    return allowed or set(DEFAULT_BYOK_ALLOWED_FIELDS), required

PROVIDER_CAPABILITIES: dict[str, dict[str, Any]] = {
    "openai": {
        "supports_streaming": True,
        "supports_tools": True,
        "default_timeout_seconds": 90,
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
        "default_timeout_seconds": 90,
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


def list_registered_providers() -> list[str]:
    return get_registry().list_providers()
