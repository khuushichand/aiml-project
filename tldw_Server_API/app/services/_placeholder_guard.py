"""Shared guardrails for legacy placeholder services.

These services are retained only for local development/test scaffolding and
must never run in production-like environments.
"""

from __future__ import annotations

import os

from fastapi import HTTPException
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.testing import is_production_like_env, is_truthy


def ensure_placeholder_service_enabled(service_name: str) -> None:
    """Enforce strict runtime gating for placeholder services."""
    settings = get_settings()
    enabled = bool(getattr(settings, "PLACEHOLDER_SERVICES_ENABLED", False)) or is_truthy(
        os.getenv("PLACEHOLDER_SERVICES_ENABLED")
    )

    if not enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{service_name} placeholder service is disabled. "
                "Set PLACEHOLDER_SERVICES_ENABLED=1 only in non-production environments."
            ),
        )

    if is_production_like_env():
        logger.error(
            "Blocked placeholder service '{}' in production-like environment",
            service_name,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                f"{service_name} placeholder service cannot run in production environments. "
                "Disable PLACEHOLDER_SERVICES_ENABLED and use production implementations."
            ),
        )
