"""Shared dependencies and guards for enterprise federation endpoints."""

from __future__ import annotations

from fastapi import HTTPException, status

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.federation.oidc_service import OIDCFederationService
from tldw_Server_API.app.core.AuthNZ.federation.provisioning_service import (
    FederationProvisioningService,
)
from tldw_Server_API.app.core.AuthNZ.repos.identity_provider_repo import (
    IdentityProviderRepo,
)
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


def enterprise_federation_available() -> bool:
    """Return whether enterprise federation is enabled and supported here."""
    settings = get_settings()
    return bool(
        getattr(settings, "AUTH_FEDERATION_ENABLED", False)
        and getattr(settings, "enterprise_federation_supported", False)
    )


def require_enterprise_federation() -> None:
    """Raise a 409 response when enterprise federation is unavailable."""
    if not enterprise_federation_available():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Enterprise federation is not enabled for this deployment",
        )


async def get_identity_provider_repo_dep() -> IdentityProviderRepo:
    """Return an identity provider repository bound to the current DB pool."""
    return IdentityProviderRepo(db_pool=await get_db_pool())


def get_oidc_federation_service_dep() -> OIDCFederationService:
    """Return the OIDC federation service."""
    return OIDCFederationService()


async def get_federation_provisioning_service_dep() -> FederationProvisioningService:
    """Return the federation provisioning service bound to the current DB pool."""
    return FederationProvisioningService(db_pool=await get_db_pool())
