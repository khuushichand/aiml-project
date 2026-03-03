from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.schemas.mcp_hub_schemas import (
    ACPProfileCreateRequest,
    ACPProfileResponse,
    ACPProfileUpdateRequest,
    ExternalSecretSetRequest,
    ExternalSecretSetResponse,
    ExternalServerCreateRequest,
    ExternalServerResponse,
    ExternalServerUpdateRequest,
    MCPHubDeleteResponse,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.services.mcp_hub_service import McpHubService

router = APIRouter(prefix="/mcp/hub", tags=["mcp-hub"])

_MCP_HUB_ADMIN_PERMISSIONS = frozenset({SYSTEM_CONFIGURE, "*"})


async def get_mcp_hub_service() -> McpHubService:
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    return McpHubService(repo)


def _load_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, ValueError):
            logger.debug("MCP hub payload JSON decode failed")
            return {}
    return {}


def _is_mutation_allowed(principal: AuthPrincipal) -> bool:
    roles = {
        str(role).strip().lower()
        for role in (principal.roles or [])
        if str(role).strip()
    }
    if "admin" in roles:
        return True
    permissions = {
        str(permission).strip().lower()
        for permission in (principal.permissions or [])
        if str(permission).strip()
    }
    required = {perm.lower() for perm in _MCP_HUB_ADMIN_PERMISSIONS}
    return bool(permissions & required)


def _require_mutation_permission(principal: AuthPrincipal) -> None:
    if _is_mutation_allowed(principal):
        return
    raise HTTPException(status_code=403, detail=f"{SYSTEM_CONFIGURE} permission required")


def _profile_row_to_response(row: dict[str, Any]) -> ACPProfileResponse:
    return ACPProfileResponse(
        id=int(row.get("id")),
        name=str(row.get("name") or ""),
        description=row.get("description"),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        profile=_load_json_object(row.get("profile_json")),
        is_active=bool(row.get("is_active")),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _external_row_to_response(row: dict[str, Any]) -> ExternalServerResponse:
    return ExternalServerResponse(
        id=str(row.get("id") or ""),
        name=str(row.get("name") or ""),
        enabled=bool(row.get("enabled")),
        owner_scope_type=str(row.get("owner_scope_type") or "global"),
        owner_scope_id=row.get("owner_scope_id"),
        transport=str(row.get("transport") or ""),
        config=_load_json_object(row.get("config_json")),
        secret_configured=bool(row.get("secret_configured")),
        key_hint=row.get("key_hint"),
        created_by=row.get("created_by"),
        updated_by=row.get("updated_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.get("/acp-profiles", response_model=list[ACPProfileResponse])
async def list_acp_profiles(
    owner_scope_type: str | None = None,
    owner_scope_id: int | None = None,
    _principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[ACPProfileResponse]:
    rows = await svc.list_acp_profiles(
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
    )
    return [_profile_row_to_response(row) for row in rows]


@router.post("/acp-profiles", response_model=ACPProfileResponse, status_code=201)
async def create_acp_profile(
    payload: ACPProfileCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ACPProfileResponse:
    _require_mutation_permission(principal)
    row = await svc.create_acp_profile(
        name=payload.name,
        description=payload.description,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        profile=payload.profile,
        is_active=payload.is_active,
        actor_id=principal.user_id,
    )
    return _profile_row_to_response(row)


@router.put("/acp-profiles/{profile_id}", response_model=ACPProfileResponse)
async def update_acp_profile(
    profile_id: int,
    payload: ACPProfileUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ACPProfileResponse:
    _require_mutation_permission(principal)
    row = await svc.update_acp_profile(
        profile_id,
        name=payload.name,
        description=payload.description,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        profile=payload.profile,
        is_active=payload.is_active,
        actor_id=principal.user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="ACP profile not found")
    return _profile_row_to_response(row)


@router.delete("/acp-profiles/{profile_id}", response_model=MCPHubDeleteResponse)
async def delete_acp_profile(
    profile_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    _require_mutation_permission(principal)
    deleted = await svc.delete_acp_profile(profile_id, actor_id=principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ACP profile not found")
    return MCPHubDeleteResponse(ok=True)


@router.get("/external-servers", response_model=list[ExternalServerResponse])
async def list_external_servers(
    owner_scope_type: str | None = None,
    owner_scope_id: int | None = None,
    _principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> list[ExternalServerResponse]:
    rows = await svc.list_external_servers(
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
    )
    return [_external_row_to_response(row) for row in rows]


@router.post("/external-servers", response_model=ExternalServerResponse, status_code=201)
async def create_external_server(
    payload: ExternalServerCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerResponse:
    _require_mutation_permission(principal)
    row = await svc.create_external_server(
        server_id=payload.server_id,
        name=payload.name,
        transport=payload.transport,
        config=payload.config,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        enabled=payload.enabled,
        actor_id=principal.user_id,
    )
    return _external_row_to_response(row)


@router.put("/external-servers/{server_id}", response_model=ExternalServerResponse)
async def update_external_server(
    server_id: str,
    payload: ExternalServerUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalServerResponse:
    _require_mutation_permission(principal)
    existing = await svc.repo.get_external_server(server_id)
    if not existing:
        raise HTTPException(status_code=404, detail="External server not found")
    row = await svc.create_external_server(
        server_id=server_id,
        name=payload.name if payload.name is not None else str(existing.get("name") or ""),
        transport=payload.transport if payload.transport is not None else str(existing.get("transport") or ""),
        config=payload.config if payload.config is not None else _load_json_object(existing.get("config_json")),
        owner_scope_type=payload.owner_scope_type if payload.owner_scope_type is not None else str(existing.get("owner_scope_type") or "global"),
        owner_scope_id=payload.owner_scope_id if payload.owner_scope_id is not None else existing.get("owner_scope_id"),
        enabled=payload.enabled if payload.enabled is not None else bool(existing.get("enabled")),
        actor_id=principal.user_id,
    )
    return _external_row_to_response(row)


@router.delete("/external-servers/{server_id}", response_model=MCPHubDeleteResponse)
async def delete_external_server(
    server_id: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> MCPHubDeleteResponse:
    _require_mutation_permission(principal)
    deleted = await svc.delete_external_server(server_id, actor_id=principal.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="External server not found")
    return MCPHubDeleteResponse(ok=True)


@router.post("/external-servers/{server_id}/secret", response_model=ExternalSecretSetResponse)
async def set_external_secret(
    server_id: str,
    payload: ExternalSecretSetRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    svc: McpHubService = Depends(get_mcp_hub_service),
) -> ExternalSecretSetResponse:
    _require_mutation_permission(principal)
    try:
        out = await svc.set_external_server_secret(
            server_id=server_id,
            secret_value=payload.secret,
            actor_id=principal.user_id,
        )
    except ValueError as exc:
        detail = str(exc) or "Invalid secret payload"
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return ExternalSecretSetResponse(**out)
