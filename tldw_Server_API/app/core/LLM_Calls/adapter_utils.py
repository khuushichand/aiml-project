from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
from tldw_Server_API.app.core.Chat.chat_service import resolve_provider_api_key
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.config import load_and_log_configs

_PROVIDER_SECTION_MAP: Dict[str, str] = {
    "openai": "openai_api",
    "anthropic": "anthropic_api",
    "cohere": "cohere_api",
    "groq": "groq_api",
    "deepseek": "deepseek_api",
    "mistral": "mistral_api",
    "openrouter": "openrouter_api",
    "huggingface": "huggingface_api",
    "google": "google_api",
    "qwen": "qwen_api",
    "custom-openai-api": "custom_openai_api",
    "custom-openai-api-2": "custom_openai_api_2",
    "moonshot": "moonshot_api",
    "zai": "zai_api",
    "llama.cpp": "llama_api",
    "kobold": "kobold_api",
    "ooba": "ooba_api",
    "tabbyapi": "tabby_api",
    "vllm": "vllm_api",
    "local-llm": "local_llm",
    "ollama": "ollama_api",
    "aphrodite": "aphrodite_api",
    "bedrock": "bedrock_api",
    "mlx": "mlx",
}


def normalize_provider(provider: Optional[str]) -> str:
    return (provider or "").strip().lower()


def resolve_provider_section(provider: str) -> str:
    normalized = normalize_provider(provider)
    if not normalized:
        return ""
    return _PROVIDER_SECTION_MAP.get(
        normalized,
        f"{normalized.replace('.', '_').replace('-', '_')}_api",
    )


def ensure_app_config(app_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return app_config or load_and_log_configs() or {}


def resolve_provider_model(provider: str, app_config: Dict[str, Any]) -> Optional[str]:
    normalized = normalize_provider(provider)
    section = resolve_provider_section(provider)
    if section:
        cfg = app_config.get(section) or {}
        model = cfg.get("model") or cfg.get("model_id")
        if model:
            return model
    if normalized == "mlx":
        env_val = (__import__("os").getenv("MLX_MODEL_PATH") or "").strip()
        if env_val:
            return env_val
        mlx_cfg = app_config.get("mlx") or {}
        model = mlx_cfg.get("model_path") or mlx_cfg.get("mlx_model_path") or mlx_cfg.get("model")
        if model:
            return model
    env_key = f"DEFAULT_MODEL_{normalized.replace('.', '_').replace('-', '_').upper()}"
    env_val = (env_key and __import__("os").getenv(env_key))  # avoid top-level os import
    if isinstance(env_val, str) and env_val.strip():
        return env_val.strip()
    return None


def resolve_provider_api_key_from_config(
    provider: str,
    app_config: Optional[Dict[str, Any]] = None,
    *,
    prefer_module_keys_in_tests: bool = True,
) -> Optional[str]:
    api_key, _debug = resolve_provider_api_key(
        provider,
        prefer_module_keys_in_tests=prefer_module_keys_in_tests,
    )
    if api_key:
        return api_key
    cfg = ensure_app_config(app_config)
    section = resolve_provider_section(provider)
    if section:
        api_key = (cfg.get(section) or {}).get("api_key")
    return api_key


def get_adapter_or_raise(provider: str):
    adapter = get_registry().get_adapter(normalize_provider(provider))
    if adapter is None:
        raise ChatConfigurationError(provider=provider, message="LLM adapter unavailable.")
    return adapter


def split_system_message(messages: List[Dict[str, Any]]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    system_message = None
    remaining: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "system" and system_message is None:
            system_message = msg.get("content")
            continue
        remaining.append(msg)
    return system_message, remaining
