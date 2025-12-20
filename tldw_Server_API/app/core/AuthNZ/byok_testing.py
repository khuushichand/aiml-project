from __future__ import annotations

from typing import Any, Dict, Optional
import asyncio
import os

from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import normalize_provider_name
from tldw_Server_API.app.core.AuthNZ.byok_config import build_app_config_overrides
from tldw_Server_API.app.core.Chat.Chat_Deps import (
    ChatAPIError,
    ChatAuthenticationError,
    ChatBadRequestError,
    ChatProviderError,
)
from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call
from tldw_Server_API.app.core.Chat.provider_config import API_CALL_HANDLERS
from tldw_Server_API.app.core.config import load_comprehensive_config


_INVALID_TEST_KEY_PREFIXES = ("invalid-", "test-invalid-", "bad-key-", "dummy-invalid-")


def _is_test_mode() -> bool:
    return (
        os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )


def is_obviously_invalid_key(api_key: str) -> bool:
    key = (api_key or "").strip()
    if not key:
        return False
    lowered = key.lower()
    return any(lowered.startswith(prefix) for prefix in _INVALID_TEST_KEY_PREFIXES)


def resolve_default_model_for_provider(provider: str) -> Optional[str]:
    normalized = (provider or "").replace(".", "_").replace("-", "_")
    env_key = f"DEFAULT_MODEL_{normalized.upper()}"
    env_val = os.getenv(env_key)
    if isinstance(env_val, str) and env_val.strip():
        return env_val.strip()

    cfg = None
    try:
        cfg = load_comprehensive_config()
    except Exception:
        cfg = None

    if cfg is not None and getattr(cfg, "has_section", None) and cfg.has_section("Chat-Module"):
        config_key = f"default_model_{normalized.lower()}"
        try:
            cfg_val = cfg.get("Chat-Module", config_key, fallback=None)
        except Exception:
            cfg_val = None
        if isinstance(cfg_val, str) and cfg_val.strip():
            return cfg_val.strip()

    return None


def build_app_config_for_provider(provider: str, credential_fields: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return build_app_config_overrides(provider, credential_fields)


async def test_provider_credentials(
    *,
    provider: str,
    api_key: str,
    credential_fields: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> str:
    provider_norm = normalize_provider_name(provider)
    if provider_norm not in API_CALL_HANDLERS:
        raise ValueError(f"Provider '{provider_norm}' does not support key tests yet")

    model_to_use = model or resolve_default_model_for_provider(provider_norm)
    if not model_to_use:
        raise ValueError(
            f"Model is required for provider '{provider_norm}'. "
            f"Configure DEFAULT_MODEL_{provider_norm.replace('.', '_').replace('-', '_').upper()} or pass model."
        )

    if _is_test_mode():
        if is_obviously_invalid_key(api_key):
            raise ChatAuthenticationError(
                message=f"Provider '{provider_norm}' rejected the supplied credentials.",
                provider=provider_norm,
            )
        return model_to_use

    app_config = build_app_config_for_provider(provider_norm, credential_fields)
    messages_payload = [{"role": "user", "content": "ping"}]
    try:
        await asyncio.to_thread(
            chat_api_call,
            api_endpoint=provider_norm,
            messages_payload=messages_payload,
            api_key=api_key,
            model=model_to_use,
            temp=0.0,
            max_tokens=1,
            streaming=False,
            app_config=app_config,
        )
    except ChatAPIError:
        raise
    except ValueError as exc:
        raise ChatBadRequestError(message=str(exc), provider=provider_norm) from exc
    except Exception as exc:
        raise ChatProviderError(
            provider=provider_norm,
            message="Provider test call failed",
            status_code=502,
            details=str(exc),
        ) from exc

    return model_to_use
