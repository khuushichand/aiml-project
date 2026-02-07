"""Admin BYOK endpoints for managing user and shared provider keys."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    check_rate_limit,
    get_auth_principal,
    require_roles,
)
from tldw_Server_API.app.api.v1.schemas.user_keys import (
    AdminUserKeysResponse,
    SharedProviderKeyResponse,
    SharedProviderKeysResponse,
    SharedProviderKeyTestRequest,
    SharedProviderKeyTestResponse,
    SharedProviderKeyUpsertRequest,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_byok_service

router = APIRouter()


@router.get(
    "/keys/users/{user_id}",
    response_model=AdminUserKeysResponse,
    dependencies=[Depends(require_roles("admin")), Depends(check_rate_limit)],
)
async def admin_list_user_byok_keys(
    user_id: int,
    principal: Annotated[AuthPrincipal, Depends(get_auth_principal)],
) -> AdminUserKeysResponse:
    """List BYOK keys for a given user."""
    return await admin_byok_service.list_user_keys(principal, user_id)


@router.delete(
    "/keys/users/{user_id}/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_roles("admin")), Depends(check_rate_limit)],
)
async def admin_revoke_user_byok_key(
    user_id: int,
    provider: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    """Revoke a specific BYOK key for a user."""
    await admin_byok_service.revoke_user_key(principal, user_id, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/keys/shared",
    response_model=SharedProviderKeyResponse,
    dependencies=[Depends(require_roles("admin")), Depends(check_rate_limit)],
)
async def admin_upsert_shared_byok_key(
    payload: SharedProviderKeyUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> SharedProviderKeyResponse:
    """Create or update a shared BYOK provider key."""
    return await admin_byok_service.upsert_shared_key(principal, payload)


@router.post(
    "/keys/shared/test",
    response_model=SharedProviderKeyTestResponse,
    dependencies=[Depends(require_roles("admin")), Depends(check_rate_limit)],
)
async def admin_test_shared_byok_key(
    payload: SharedProviderKeyTestRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> SharedProviderKeyTestResponse:
    """Test a shared BYOK provider key and return connectivity results."""
    return await admin_byok_service.test_shared_key(principal, payload)


@router.get(
    "/keys/shared",
    response_model=SharedProviderKeysResponse,
    dependencies=[Depends(require_roles("admin")), Depends(check_rate_limit)],
)
async def admin_list_shared_byok_keys(
    principal: AuthPrincipal = Depends(get_auth_principal),
    scope_type: Literal["org", "team"] | None = Query(None),
    scope_id: int | None = Query(None),
    provider: str | None = Query(None),
) -> SharedProviderKeysResponse:
    """List shared BYOK keys filtered by scope or provider."""
    return await admin_byok_service.list_shared_keys(
        principal,
        scope_type=scope_type,
        scope_id=scope_id,
        provider=provider,
    )


@router.delete(
    "/keys/shared/{scope_type}/{scope_id}/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_roles("admin")), Depends(check_rate_limit)],
)
async def admin_delete_shared_byok_key(
    scope_type: Literal["org", "team"],
    scope_id: int,
    provider: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    """Delete a shared BYOK key for a given scope and provider."""
    await admin_byok_service.delete_shared_key(principal, scope_type, scope_id, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
