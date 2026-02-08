from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_db_transaction,
)
from tldw_Server_API.app.api.v1.schemas.admin_rbac_schemas import (
    RateLimitResponse,
    RateLimitUpsertRequest,
)
from tldw_Server_API.app.api.v1.schemas.auth_schemas import MessageResponse
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal

router = APIRouter()


_RATE_LIMITS_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    asyncio.TimeoutError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    HTTPException,
)


async def _enforce_admin_user_scope(
    principal: AuthPrincipal,
    target_user_id: int,
    *,
    require_hierarchy: bool,
) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    await admin_mod._enforce_admin_user_scope(
        principal,
        target_user_id,
        require_hierarchy=require_hierarchy,
    )


def _get_is_postgres_backend_fn() -> Callable[[], Awaitable[bool]]:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    return admin_mod._is_postgres_backend

@router.post("/roles/{role_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_role_rate_limit(role_id: int, payload: RateLimitUpsertRequest, db=Depends(get_db_transaction)) -> RateLimitResponse:
    try:
        is_pg = await _get_is_postgres_backend_fn()()
        if is_pg:
            await db.execute(
                """
                INSERT INTO rbac_role_rate_limits (role_id, resource, limit_per_min, burst)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (role_id, resource) DO UPDATE SET
                    limit_per_min = EXCLUDED.limit_per_min,
                    burst = EXCLUDED.burst
                """,
                role_id, payload.resource, payload.limit_per_min, payload.burst,
            )
        else:
            await db.execute(
                """
                INSERT OR REPLACE INTO rbac_role_rate_limits (role_id, resource, limit_per_min, burst)
                VALUES (?, ?, ?, ?)
                """,
                (role_id, payload.resource, payload.limit_per_min, payload.burst),
            )
            await db.commit()
        return RateLimitResponse(scope="role", id=role_id, resource=payload.resource, limit_per_min=payload.limit_per_min, burst=payload.burst)
    except _RATE_LIMITS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Failed to upsert role rate limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert role rate limit") from e


@router.delete("/roles/{role_id}/rate-limits", response_model=MessageResponse)
async def clear_role_rate_limits(role_id: int, db=Depends(get_db_transaction)) -> MessageResponse:
    try:
        is_pg = await _get_is_postgres_backend_fn()()
        if is_pg:
            await db.execute("DELETE FROM rbac_role_rate_limits WHERE role_id = $1", role_id)
        else:
            await db.execute("DELETE FROM rbac_role_rate_limits WHERE role_id = ?", (role_id,))
            await db.commit()
        return MessageResponse(message="Role rate limits cleared", details={"role_id": role_id})
    except _RATE_LIMITS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Failed to clear role rate limits: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear role rate limits") from e


@router.post("/users/{user_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_user_rate_limit(
    user_id: int,
    payload: RateLimitUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RateLimitResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        is_pg = await _get_is_postgres_backend_fn()()
        if is_pg:
            await db.execute(
                """
                INSERT INTO rbac_user_rate_limits (user_id, resource, limit_per_min, burst)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, resource) DO UPDATE SET
                    limit_per_min = EXCLUDED.limit_per_min,
                    burst = EXCLUDED.burst
                """,
                user_id, payload.resource, payload.limit_per_min, payload.burst,
            )
        else:
            await db.execute(
                """
                INSERT OR REPLACE INTO rbac_user_rate_limits (user_id, resource, limit_per_min, burst)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, payload.resource, payload.limit_per_min, payload.burst),
            )
            await db.commit()
        return RateLimitResponse(scope="user", id=user_id, resource=payload.resource, limit_per_min=payload.limit_per_min, burst=payload.burst)
    except _RATE_LIMITS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Failed to upsert user rate limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert user rate limit") from e
