from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user
from tldw_Server_API.app.api.v1.schemas.user_keys import (
    ProviderKeyTestRequest,
    ProviderKeyTestResponse,
    UserProviderKeyResponse,
    UserProviderKeysResponse,
    UserProviderKeyStatusItem,
    UserProviderKeyUpsertRequest,
)
from tldw_Server_API.app.core.AuthNZ.byok_helpers import (
    is_byok_enabled,
    is_provider_allowlisted,
    is_trusted_base_url_request,
    resolve_byok_allowlist,
    resolve_server_default_key,
    validate_base_url_override,
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
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    decrypt_byok_payload,
    dumps_envelope,
    encrypt_byok_payload,
    key_hint_for_api_key,
    loads_envelope,
    normalize_provider_name,
)
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAPIError

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
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_active_user),
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

    allow_base_url = is_trusted_base_url_request(request, user=current_user)
    raw_fields = payload.credential_fields or {}
    if isinstance(raw_fields, dict) and "base_url" in raw_fields and not allow_base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="base_url override requires admin or service principal",
        )

    try:
        credential_fields = validate_credential_fields(
            provider_norm,
            payload.credential_fields,
            allow_base_url=allow_base_url,
        )
        if "base_url" in credential_fields:
            credential_fields["base_url"] = validate_base_url_override(
                credential_fields["base_url"]
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        await test_provider_credentials(
            provider=provider_norm,
            api_key=api_key,
            credential_fields=credential_fields,
            model=None,
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
        created_by=int(current_user["id"]),
        updated_by=int(current_user["id"]),
    )
    return UserProviderKeyResponse(
        provider=provider_norm,
        key_hint=row.get("key_hint") or key_hint_for_api_key(api_key),
        updated_at=row.get("updated_at") or now,
    )


@router.get("/keys", response_model=UserProviderKeysResponse)
async def list_user_provider_keys(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_active_user),
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

    def _filter_scopes(ids: list[int], active_id: Any) -> list[int]:
        if not ids:
            return []
        if active_id is None:
            return ids if len(ids) == 1 else []
        try:
            active = int(active_id)
        except (TypeError, ValueError):
            return []
        return [active] if active in ids else []

    active_team_id = getattr(request.state, "active_team_id", None)
    active_org_id = getattr(request.state, "active_org_id", None)
    team_scope_ids = _filter_scopes(team_ids, active_team_id)
    org_scope_ids = _filter_scopes(org_ids, active_org_id)

    shared_keys: dict[str, dict[str, Any]] = {}
    shared_sources: dict[str, str] = {}
    for team_id in team_scope_ids:
        rows = await org_repo.list_secrets(scope_type="team", scope_id=int(team_id))
        for row in rows:
            provider = row.get("provider")
            if provider and provider not in shared_keys:
                shared_keys[provider] = row
                shared_sources[provider] = "team"
    for org_id in org_scope_ids:
        rows = await org_repo.list_secrets(scope_type="org", scope_id=int(org_id))
        for row in rows:
            provider = row.get("provider")
            if provider and provider not in shared_keys:
                shared_keys[provider] = row
                shared_sources[provider] = "org"

    providers = sorted(set(allowlist) | set(user_keys.keys()) | set(shared_keys.keys()))
    items: list[UserProviderKeyStatusItem] = []
    for provider in providers:
        allowed = provider in allowlist
        user_row = user_keys.get(provider)
        shared_row = shared_keys.get(provider)
        if not allowed and (user_row or shared_row):
            items.append(
                UserProviderKeyStatusItem(
                    provider=provider,
                    has_key=bool(user_row),
                    source="disabled",
                    last_used_at=(user_row or shared_row or {}).get("last_used_at"),
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
                    source=shared_sources.get(provider, "org"),
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
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_active_user),
) -> ProviderKeyTestResponse:
    _require_byok_enabled()
    provider_norm = normalize_provider_name(payload.provider)
    if not is_provider_allowlisted(provider_norm):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider not allowed for BYOK",
        )

    repo = await _get_user_repo()
    row = await repo.fetch_secret_for_user(int(current_user["id"]), provider_norm)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    encrypted_blob = row.get("encrypted_blob")
    if not encrypted_blob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    try:
        stored_payload = decrypt_byok_payload(loads_envelope(encrypted_blob))
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    api_key = (stored_payload.get("api_key") or "").strip()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    allow_base_url = is_trusted_base_url_request(request, user=current_user)
    credential_fields_raw = stored_payload.get("credential_fields") or {}
    if isinstance(credential_fields_raw, dict) and "base_url" in credential_fields_raw and not allow_base_url:
        credential_fields_raw = dict(credential_fields_raw)
        credential_fields_raw.pop("base_url", None)

    try:
        credential_fields = validate_credential_fields(
            provider_norm,
            credential_fields_raw,
            allow_base_url=allow_base_url,
        )
        if "base_url" in credential_fields:
            credential_fields["base_url"] = validate_base_url_override(
                credential_fields["base_url"]
            )
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

    await _touch_user_last_used_if_match(
        repo,
        user_id=int(current_user["id"]),
        provider=provider_norm,
        api_key=api_key,
    )

    return ProviderKeyTestResponse(provider=provider_norm, status="valid", model=model_used)


@router.delete(
    "/keys/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_user_provider_key(
    provider: str,
    current_user: dict[str, Any] = Depends(get_current_active_user),
) -> Response:
    _require_byok_enabled()
    provider_norm = normalize_provider_name(provider)
    repo = await _get_user_repo()
    deleted = await repo.delete_secret(
        int(current_user["id"]),
        provider_norm,
        revoked_by=int(current_user["id"]),
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
