from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal, require_roles
from tldw_Server_API.app.api.v1.endpoints.discord_support import (
    _discord_policy_for_guild,
    _set_discord_policy,
)
from tldw_Server_API.app.api.v1.endpoints.slack_support import (
    _set_slack_policy,
    _slack_policy_for_workspace,
)
from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    TelegramScope,
    _resolve_shared_scope,
    telegram_admin_get_bot_impl,
    telegram_admin_list_linked_actors_impl,
    telegram_admin_put_bot_impl,
    telegram_admin_revoke_linked_actor_impl,
    telegram_admin_start_link_impl,
)
from tldw_Server_API.app.api.v1.schemas.integrations_control_plane_schemas import (
    DiscordWorkspacePolicy,
    DiscordWorkspacePolicyResponse,
    DiscordWorkspacePolicyUpdate,
    IntegrationOverviewResponse,
    SlackWorkspacePolicy,
    SlackWorkspacePolicyResponse,
    SlackWorkspacePolicyUpdate,
)
from tldw_Server_API.app.api.v1.schemas.telegram_schemas import (
    TelegramBotConfigResponse,
    TelegramBotConfigUpdate,
    TelegramLinkedActorListResponse,
    TelegramLinkedActorRevokeResponse,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos import get_workspace_provider_installations_repo
from tldw_Server_API.app.core.AuthNZ.repos.org_provider_secrets_repo import AuthnzOrgProviderSecretsRepo
from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import AuthnzUserProviderSecretsRepo
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.services.integrations_control_plane_service import IntegrationsControlPlaneService

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _collect_scope_ids(*value_lists: Any) -> list[int]:
    values: set[int] = set()
    for raw_list in value_lists:
        if not isinstance(raw_list, (list, tuple, set)):
            continue
        for raw in raw_list:
            coerced = _coerce_int(raw)
            if coerced is not None:
                values.add(coerced)
    return sorted(values)


def _normalize_installation_ids(rows: list[dict[str, Any]]) -> list[str]:
    installation_ids: list[str] = []
    for row in rows:
        external_id = str((row or {}).get("external_id") or "").strip()
        if external_id and external_id not in installation_ids:
            installation_ids.append(external_id)
    return installation_ids


def _policies_are_uniform(policies: list[dict[str, Any]]) -> bool:
    if not policies:
        return True
    baseline = dict(policies[0])
    return all(dict(candidate) == baseline for candidate in policies[1:])


def _resolve_workspace_org_id(principal: AuthPrincipal, request: Request | None = None) -> int:
    request_active_org_id = _coerce_int(getattr(request.state, "active_org_id", None)) if request else None
    principal_active_org_id = _coerce_int(principal.active_org_id)
    org_ids = _collect_scope_ids(getattr(request.state, "org_ids", None) if request else None, principal.org_ids)

    for candidate in (request_active_org_id, principal_active_org_id):
        if candidate is not None and (not org_ids or candidate in org_ids):
            return candidate

    if len(org_ids) == 1:
        return org_ids[0]

    if get_settings().auth_mode == "single_user":
        return 1

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="An active org scope is required",
    )


def _resolve_workspace_telegram_scope(principal: AuthPrincipal, request: Request | None, *, org_id: int) -> TelegramScope:
    try:
        return _resolve_shared_scope(principal=principal, request=request)
    except HTTPException:
        if get_settings().auth_mode == "single_user":
            return TelegramScope(scope_type="org", scope_id=int(org_id))
        raise


async def get_integrations_control_plane_service() -> IntegrationsControlPlaneService:
    pool = await get_db_pool()
    user_repo = AuthnzUserProviderSecretsRepo(pool)
    await user_repo.ensure_tables()
    org_repo = AuthnzOrgProviderSecretsRepo(pool)
    await org_repo.ensure_tables()
    workspace_repo = await get_workspace_provider_installations_repo()
    return IntegrationsControlPlaneService(
        user_provider_secrets_repo=user_repo,
        org_provider_secrets_repo=org_repo,
        workspace_installations_repo=workspace_repo,
    )


async def _list_workspace_installation_ids(
    *,
    workspace_repo: Any,
    org_id: int,
    provider: str,
) -> list[str]:
    rows = await workspace_repo.list_installations(org_id=org_id, provider=provider, include_disabled=True)
    return _normalize_installation_ids(rows)


async def _build_slack_workspace_policy_response(
    *,
    workspace_repo: Any,
    org_id: int,
) -> SlackWorkspacePolicyResponse:
    installation_ids = await _list_workspace_installation_ids(workspace_repo=workspace_repo, org_id=org_id, provider="slack")
    policies = [_slack_policy_for_workspace(installation_id) for installation_id in installation_ids]
    if not policies:
        policies = [_slack_policy_for_workspace(None)]
    return SlackWorkspacePolicyResponse(
        installation_ids=installation_ids,
        uniform=_policies_are_uniform(policies),
        policy=SlackWorkspacePolicy.model_validate(policies[0]),
    )


async def _update_slack_workspace_policy(
    *,
    workspace_repo: Any,
    org_id: int,
    payload: SlackWorkspacePolicyUpdate,
) -> SlackWorkspacePolicyResponse:
    installation_ids = await _list_workspace_installation_ids(workspace_repo=workspace_repo, org_id=org_id, provider="slack")
    update_payload = payload.model_dump(exclude_none=True)
    applied_policies: list[dict[str, Any]] = []
    if installation_ids:
        for installation_id in installation_ids:
            _, applied_policy = _set_slack_policy(installation_id, update_payload)
            applied_policies.append(applied_policy)
    else:
        _, applied_policy = _set_slack_policy(None, update_payload)
        applied_policies.append(applied_policy)
    return SlackWorkspacePolicyResponse(
        installation_ids=installation_ids,
        uniform=_policies_are_uniform(applied_policies),
        policy=SlackWorkspacePolicy.model_validate(applied_policies[0]),
    )


async def _build_discord_workspace_policy_response(
    *,
    workspace_repo: Any,
    org_id: int,
) -> DiscordWorkspacePolicyResponse:
    installation_ids = await _list_workspace_installation_ids(
        workspace_repo=workspace_repo,
        org_id=org_id,
        provider="discord",
    )
    policies = [_discord_policy_for_guild(installation_id) for installation_id in installation_ids]
    if not policies:
        policies = [_discord_policy_for_guild(None)]
    return DiscordWorkspacePolicyResponse(
        installation_ids=installation_ids,
        uniform=_policies_are_uniform(policies),
        policy=DiscordWorkspacePolicy.model_validate(policies[0]),
    )


async def _update_discord_workspace_policy(
    *,
    workspace_repo: Any,
    org_id: int,
    payload: DiscordWorkspacePolicyUpdate,
) -> DiscordWorkspacePolicyResponse:
    installation_ids = await _list_workspace_installation_ids(
        workspace_repo=workspace_repo,
        org_id=org_id,
        provider="discord",
    )
    update_payload = payload.model_dump(exclude_none=True)
    applied_policies: list[dict[str, Any]] = []
    if installation_ids:
        for installation_id in installation_ids:
            _, applied_policy = _set_discord_policy(installation_id, update_payload)
            applied_policies.append(applied_policy)
    else:
        _, applied_policy = _set_discord_policy(None, update_payload)
        applied_policies.append(applied_policy)
    return DiscordWorkspacePolicyResponse(
        installation_ids=installation_ids,
        uniform=_policies_are_uniform(applied_policies),
        policy=DiscordWorkspacePolicy.model_validate(applied_policies[0]),
    )


@router.get("/personal", response_model=IntegrationOverviewResponse)
async def list_personal_integrations(
    principal: AuthPrincipal = Depends(get_auth_principal),
    service: IntegrationsControlPlaneService = Depends(get_integrations_control_plane_service),
) -> IntegrationOverviewResponse:
    user_id = _coerce_int(principal.user_id)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authenticated user id is required")
    return await service.build_personal_overview(user_id=user_id)


@router.get("/workspace", dependencies=[Depends(require_roles("admin"))], response_model=IntegrationOverviewResponse)
async def list_workspace_integrations(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    service: IntegrationsControlPlaneService = Depends(get_integrations_control_plane_service),
) -> IntegrationOverviewResponse:
    org_id = _resolve_workspace_org_id(principal, request)
    telegram_scope = _resolve_workspace_telegram_scope(principal, request, org_id=org_id)
    return await service.build_workspace_overview(
        org_id=org_id,
        scope_type=telegram_scope.scope_type,
        scope_id=telegram_scope.scope_id,
    )


@router.get(
    "/workspace/slack/policy",
    dependencies=[Depends(require_roles("admin"))],
    response_model=SlackWorkspacePolicyResponse,
)
async def get_workspace_slack_policy(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    workspace_repo=Depends(get_workspace_provider_installations_repo),
) -> SlackWorkspacePolicyResponse:
    org_id = _resolve_workspace_org_id(principal, request)
    return await _build_slack_workspace_policy_response(workspace_repo=workspace_repo, org_id=org_id)


@router.put(
    "/workspace/slack/policy",
    dependencies=[Depends(require_roles("admin"))],
    response_model=SlackWorkspacePolicyResponse,
)
async def put_workspace_slack_policy(
    request: Request,
    payload: SlackWorkspacePolicyUpdate,
    principal: AuthPrincipal = Depends(get_auth_principal),
    workspace_repo=Depends(get_workspace_provider_installations_repo),
) -> SlackWorkspacePolicyResponse:
    org_id = _resolve_workspace_org_id(principal, request)
    return await _update_slack_workspace_policy(workspace_repo=workspace_repo, org_id=org_id, payload=payload)


@router.get(
    "/workspace/discord/policy",
    dependencies=[Depends(require_roles("admin"))],
    response_model=DiscordWorkspacePolicyResponse,
)
async def get_workspace_discord_policy(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    workspace_repo=Depends(get_workspace_provider_installations_repo),
) -> DiscordWorkspacePolicyResponse:
    org_id = _resolve_workspace_org_id(principal, request)
    return await _build_discord_workspace_policy_response(workspace_repo=workspace_repo, org_id=org_id)


@router.put(
    "/workspace/discord/policy",
    dependencies=[Depends(require_roles("admin"))],
    response_model=DiscordWorkspacePolicyResponse,
)
async def put_workspace_discord_policy(
    request: Request,
    payload: DiscordWorkspacePolicyUpdate,
    principal: AuthPrincipal = Depends(get_auth_principal),
    workspace_repo=Depends(get_workspace_provider_installations_repo),
) -> DiscordWorkspacePolicyResponse:
    org_id = _resolve_workspace_org_id(principal, request)
    return await _update_discord_workspace_policy(workspace_repo=workspace_repo, org_id=org_id, payload=payload)


@router.get(
    "/workspace/telegram/bot",
    dependencies=[Depends(require_roles("admin"))],
    response_model=TelegramBotConfigResponse,
)
async def get_workspace_telegram_bot(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TelegramBotConfigResponse:
    return await telegram_admin_get_bot_impl(principal=principal, request=request)


@router.put(
    "/workspace/telegram/bot",
    dependencies=[Depends(require_roles("admin"))],
    response_model=TelegramBotConfigResponse,
)
async def put_workspace_telegram_bot(
    request: Request,
    payload: TelegramBotConfigUpdate,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TelegramBotConfigResponse:
    return await telegram_admin_put_bot_impl(principal=principal, payload=payload, request=request)


@router.post("/workspace/telegram/pairing-code", dependencies=[Depends(require_roles("admin"))])
async def create_workspace_telegram_pairing_code(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    return await telegram_admin_start_link_impl(principal=principal, request=request)


@router.get(
    "/workspace/telegram/linked-actors",
    dependencies=[Depends(require_roles("admin"))],
    response_model=TelegramLinkedActorListResponse,
)
async def list_workspace_telegram_linked_actors(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TelegramLinkedActorListResponse:
    return await telegram_admin_list_linked_actors_impl(principal=principal, request=request)


@router.delete(
    "/workspace/telegram/linked-actors/{actor_id}",
    dependencies=[Depends(require_roles("admin"))],
    response_model=TelegramLinkedActorRevokeResponse,
)
async def revoke_workspace_telegram_linked_actor(
    actor_id: int,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TelegramLinkedActorRevokeResponse:
    return await telegram_admin_revoke_linked_actor_impl(link_id=actor_id, principal=principal, request=request)
