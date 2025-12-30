from __future__ import annotations

from typing import Any, Dict, Optional, Set
import os

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import normalize_provider_name
from tldw_Server_API.app.core.config import load_and_log_configs


DEFAULT_BYOK_ALLOWED_PROVIDERS: Set[str] = {
    "anthropic",
    "bedrock",
    "cohere",
    "custom-openai-api",
    "custom-openai-api-2",
    "deepseek",
    "elevenlabs",
    "google",
    "groq",
    "huggingface",
    "mistral",
    "moonshot",
    "openai",
    "openrouter",
    "qwen",
    "voyage",
    "zai",
}

DEFAULT_ALLOWED_CREDENTIAL_FIELDS: Set[str] = {"org_id", "project_id"}


def resolve_byok_base_url_allowlist() -> Set[str]:
    settings = get_settings()
    raw = getattr(settings, "BYOK_ALLOWED_BASE_URL_PROVIDERS", []) or []
    allowed = {normalize_provider_name(p) for p in raw if str(p).strip()}
    return allowed


def is_byok_enabled() -> bool:
    settings = get_settings()
    return settings.AUTH_MODE == "multi_user" and bool(settings.BYOK_ENABLED)


def resolve_byok_allowlist() -> Set[str]:
    settings = get_settings()
    raw = getattr(settings, "BYOK_ALLOWED_PROVIDERS", []) or []
    allowed = {normalize_provider_name(p) for p in raw if str(p).strip()}
    return allowed or set(DEFAULT_BYOK_ALLOWED_PROVIDERS)


def is_provider_allowlisted(provider: str) -> bool:
    provider_norm = normalize_provider_name(provider)
    return provider_norm in resolve_byok_allowlist()


def validate_credential_fields(
    provider: str,
    credential_fields: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if credential_fields is None:
        return {}
    if not isinstance(credential_fields, dict):
        raise ValueError("credential_fields must be an object")

    provider_norm = normalize_provider_name(provider)
    allowed_keys = set(DEFAULT_ALLOWED_CREDENTIAL_FIELDS)
    if provider_norm in resolve_byok_base_url_allowlist():
        allowed_keys.add("base_url")
    cleaned: Dict[str, Any] = {}
    for key, value in credential_fields.items():
        if key not in allowed_keys:
            raise ValueError(f"Unsupported credential field: {key}")
        if isinstance(value, str) and value.strip() == "":
            raise ValueError(f"Credential field '{key}' cannot be empty")
        cleaned[key] = value
    return cleaned


def _provider_env_key(provider: str) -> str:
    normalized = provider.upper().replace(".", "_").replace("-", "_")
    if normalized.endswith("_API"):
        normalized = normalized[: -len("_API")]
    return f"{normalized}_API_KEY"


def resolve_server_default_key(provider: str) -> Optional[str]:
    provider_norm = normalize_provider_name(provider)
    try:
        from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import get_llm_provider_override

        override = get_llm_provider_override(provider_norm)
        if override and override.api_key:
            return override.api_key
    except Exception:
        pass
    env_key = _provider_env_key(provider_norm)
    env_val = os.getenv(env_key)
    if env_val is not None:
        return env_val

    try:
        config = load_and_log_configs() or {}
    except Exception:
        config = {}

    section_key = f"{provider_norm}_api"
    section = config.get(section_key)
    if isinstance(section, dict):
        api_key = section.get("api_key")
        if api_key:
            return api_key

    return None
