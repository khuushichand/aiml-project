from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, get_auth_principal
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
    dependencies=[Depends(check_rate_limit)],
)
async def admin_list_user_byok_keys(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminUserKeysResponse:
    return await admin_byok_service.list_user_keys(principal, user_id)


@router.delete(
    "/keys/users/{user_id}/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_revoke_user_byok_key(
    user_id: int,
    provider: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    await admin_byok_service.revoke_user_key(principal, user_id, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/keys/shared",
    response_model=SharedProviderKeyResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_upsert_shared_byok_key(
    payload: SharedProviderKeyUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> SharedProviderKeyResponse:
    return await admin_byok_service.upsert_shared_key(principal, payload)


@router.post(
    "/keys/shared/test",
    response_model=SharedProviderKeyTestResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_test_shared_byok_key(
    payload: SharedProviderKeyTestRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> SharedProviderKeyTestResponse:
    return await admin_byok_service.test_shared_key(principal, payload)


@router.get(
    "/keys/shared",
    response_model=SharedProviderKeysResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_list_shared_byok_keys(
    principal: AuthPrincipal = Depends(get_auth_principal),
    scope_type: str | None = Query(None),
    scope_id: int | None = Query(None),
    provider: str | None = Query(None),
) -> SharedProviderKeysResponse:
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
    dependencies=[Depends(check_rate_limit)],
)
async def admin_delete_shared_byok_key(
    scope_type: str,
    scope_id: int,
    provider: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    await admin_byok_service.delete_shared_key(principal, scope_type, scope_id, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
