from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user
from tldw_Server_API.app.api.v1.schemas.user_keys import (
    ProviderKeyTestRequest,
    ProviderKeyTestResponse,
    UserProviderKeyUpsertRequest,
    UserProviderKeyResponse,
    UserProviderKeyStatusItem,
    UserProviderKeysResponse,
)
from tldw_Server_API.app.core.AuthNZ.byok_helpers import (
    is_byok_enabled,
    is_provider_allowlisted,
    resolve_byok_allowlist,
    resolve_server_default_key,
    validate_credential_fields,
)
from tldw_Server_API.app.core.AuthNZ.byok_testing import test_provider_credentials
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user
from tldw_Server_API.app.core.AuthNZ.repos.org_provider_secrets_repo import (
    AuthnzOrgProviderSecretsRepo,
)
from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import (
    AuthnzUserProviderSecretsRepo,
)
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAPIError
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    decrypt_byok_payload,
    encrypt_byok_payload,
    dumps_envelope,
    key_hint_for_api_key,
    loads_envelope,
    normalize_provider_name,
)


router = APIRouter(prefix="/users", tags=["users"])


async def _get_user_repo() -> AuthnzUserProviderSecretsRepo:
    pool = await get_db_pool()
    repo = AuthnzUserProviderSecretsRepo(pool)
    await repo.ensure_tables()
    return repo


async def _get_org_repo() -> AuthnzOrgProviderSecretsRepo:
    pool = await get_db_pool()
    repo = AuthnzOrgProviderSecretsRepo(pool)
    await repo.ensure_tables()
    return repo


def _require_byok_enabled() -> None:
    if not is_byok_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="BYOK is disabled in this deployment",
        )


async def _touch_user_last_used_if_match(
    repo: AuthnzUserProviderSecretsRepo,
    *,
    user_id: int,
    provider: str,
    api_key: str,
) -> None:
    row = await repo.fetch_secret_for_user(user_id, provider)
    if not row:
        return
    encrypted_blob = row.get("encrypted_blob")
    if not encrypted_blob:
        return
    try:
        payload = decrypt_byok_payload(loads_envelope(encrypted_blob))
    except Exception:
        return
    if payload.get("api_key") != api_key:
        return
    await repo.touch_last_used(user_id, provider, datetime.now(timezone.utc))


@router.post(
    "/keys",
    response_model=UserProviderKeyResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_user_provider_key(
    payload: UserProviderKeyUpsertRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> UserProviderKeyResponse:
    _require_byok_enabled()
    provider_norm = normalize_provider_name(payload.provider)
    if not is_provider_allowlisted(provider_norm):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider not allowed for BYOK",
        )

    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required",
        )

    try:
        credential_fields = validate_credential_fields(provider_norm, payload.credential_fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    secret_payload = build_secret_payload(api_key, credential_fields or None)
    try:
        envelope = encrypt_byok_payload(secret_payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BYOK encryption is not configured",
        ) from exc

    repo = await _get_user_repo()
    now = datetime.now(timezone.utc)
    row = await repo.upsert_secret(
        user_id=int(current_user["id"]),
        provider=provider_norm,
        encrypted_blob=dumps_envelope(envelope),
        key_hint=key_hint_for_api_key(api_key),
        metadata=payload.metadata,
        updated_at=now,
    )
    return UserProviderKeyResponse(
        provider=provider_norm,
        key_hint=row.get("key_hint") or key_hint_for_api_key(api_key),
        updated_at=row.get("updated_at") or now,
    )


@router.get("/keys", response_model=UserProviderKeysResponse)
async def list_user_provider_keys(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> UserProviderKeysResponse:
    _require_byok_enabled()
    user_id = int(current_user["id"])
    allowlist = resolve_byok_allowlist()

    user_repo = await _get_user_repo()
    org_repo = await _get_org_repo()

    user_rows = await user_repo.list_secrets_for_user(user_id)
    user_keys = {row.get("provider"): row for row in user_rows}

    memberships = await list_memberships_for_user(user_id)
    team_ids = sorted({m.get("team_id") for m in memberships if m.get("team_id") is not None})
    org_ids = sorted({m.get("org_id") for m in memberships if m.get("org_id") is not None})

    shared_keys: Dict[str, Dict[str, Any]] = {}
    for team_id in team_ids:
        rows = await org_repo.list_secrets(scope_type="team", scope_id=int(team_id))
        for row in rows:
            provider = row.get("provider")
            if provider and provider not in shared_keys:
                shared_keys[provider] = row
    for org_id in org_ids:
        rows = await org_repo.list_secrets(scope_type="org", scope_id=int(org_id))
        for row in rows:
            provider = row.get("provider")
            if provider and provider not in shared_keys:
                shared_keys[provider] = row

    providers = sorted(set(allowlist) | set(user_keys.keys()) | set(shared_keys.keys()))
    items: List[UserProviderKeyStatusItem] = []
    for provider in providers:
        allowed = provider in allowlist
        user_row = user_keys.get(provider)
        shared_row = shared_keys.get(provider)
        if not allowed and (user_row or shared_row):
            row = user_row or shared_row or {}
            items.append(
                UserProviderKeyStatusItem(
                    provider=provider,
                    has_key=bool(user_row),
                    source="disabled",
                    key_hint=row.get("key_hint"),
                    last_used_at=row.get("last_used_at"),
                )
            )
            continue

        if user_row:
            items.append(
                UserProviderKeyStatusItem(
                    provider=provider,
                    has_key=True,
                    source="user",
                    key_hint=user_row.get("key_hint"),
                    last_used_at=user_row.get("last_used_at"),
                )
            )
            continue

        if shared_row:
            items.append(
                UserProviderKeyStatusItem(
                    provider=provider,
                    has_key=False,
                    source="shared",
                    key_hint=shared_row.get("key_hint"),
                    last_used_at=shared_row.get("last_used_at"),
                )
            )
            continue

        if resolve_server_default_key(provider):
            items.append(
                UserProviderKeyStatusItem(
                    provider=provider,
                    has_key=False,
                    source="server_default",
                )
            )
            continue

        items.append(
            UserProviderKeyStatusItem(
                provider=provider,
                has_key=False,
                source="none",
            )
        )

    return UserProviderKeysResponse(items=items)


@router.post("/keys/test", response_model=ProviderKeyTestResponse)
async def test_user_provider_key(
    payload: ProviderKeyTestRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> ProviderKeyTestResponse:
    _require_byok_enabled()
    provider_norm = normalize_provider_name(payload.provider)
    if not is_provider_allowlisted(provider_norm):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider not allowed for BYOK",
        )

    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required",
        )

    try:
        credential_fields = validate_credential_fields(provider_norm, payload.credential_fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        model_used = await test_provider_credentials(
            provider=provider_norm,
            api_key=api_key,
            credential_fields=credential_fields,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ChatAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider test call failed",
        ) from exc

    repo = await _get_user_repo()
    await _touch_user_last_used_if_match(
        repo,
        user_id=int(current_user["id"]),
        provider=provider_norm,
        api_key=api_key,
    )

    return ProviderKeyTestResponse(provider=provider_norm, status="valid", model=model_used)


@router.delete("/keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_provider_key(
    provider: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> None:
    _require_byok_enabled()
    provider_norm = normalize_provider_name(provider)
    repo = await _get_user_repo()
    deleted = await repo.delete_secret(int(current_user["id"]), provider_norm)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
