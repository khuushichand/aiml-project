"""Routing policy resolution for model='auto' requests."""

from __future__ import annotations

import os
from typing import Optional

from tldw_Server_API.app.core.config import load_and_log_configs

from .models import RoutingOverride, RoutingPolicy


def _normalize_provider(provider: Optional[str]) -> Optional[str]:
    if not isinstance(provider, str):
        return None
    candidate = provider.strip().lower()
    return candidate or None


def _load_server_default_provider() -> str:
    for env_key in ("DEFAULT_LLM_PROVIDER", "DEFAULT_PROVIDER", "DEFAULT_API"):
        env_value = _normalize_provider(os.getenv(env_key))
        if env_value:
            return env_value

    config = load_and_log_configs() or {}
    for key in ("default_api", "default_provider"):
        value = _normalize_provider(config.get(key)) if isinstance(config, dict) else None
        if value:
            return value

    api_section = config.get("API") if isinstance(config, dict) else None
    if isinstance(api_section, dict):
        for key in ("default_provider", "default_api"):
            value = _normalize_provider(api_section.get(key))
            if value:
                return value

    return "openai"


def resolve_routing_policy(
    *,
    request_model: str,
    explicit_provider: Optional[str],
    routing_override: Optional[RoutingOverride] = None,
    server_default_provider: Optional[str] = None,
) -> RoutingPolicy:
    """Resolve routing defaults plus request overrides into a concrete policy."""

    override = routing_override or RoutingOverride()
    normalized_provider = _normalize_provider(explicit_provider)
    resolved_default_provider = _normalize_provider(server_default_provider) or _load_server_default_provider()
    cross_provider = bool(override.cross_provider) if override.cross_provider is not None else False

    if cross_provider:
        boundary_mode = "cross_provider"
    elif normalized_provider:
        boundary_mode = "pinned_provider"
    else:
        boundary_mode = "server_default_provider"

    return RoutingPolicy(
        request_model=request_model,
        server_default_provider=resolved_default_provider,
        boundary_mode=boundary_mode,
        pinned_provider=normalized_provider,
        strategy=override.strategy or "llm_router",
        fallback_strategy="rules_router",
        objective=override.objective or "highest_quality",
        mode=override.mode or "per_turn",
        cross_provider=cross_provider,
        failure_mode=override.failure_mode or "fallback_then_error",
    )
