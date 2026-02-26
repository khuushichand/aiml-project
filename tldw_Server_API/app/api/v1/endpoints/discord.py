from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_roles
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import key_hint_for_api_key
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter

from tldw_Server_API.app.api.v1.endpoints.discord_support import (
    _INTERACTION_RECEIPTS,
    _RATE_LIMITER,
    _coerce_nonempty_string,
    _decrypt_discord_payload,
    _dedupe_ttl_seconds,
    _discord_response_mode,
    _discord_oauth_token_exchange,
    _discord_policy_for_guild,
    _encrypt_discord_payload,
    _error_response,
    _evaluate_discord_policy,
    _get_job_manager,
    _get_oauth_state_repo,
    _get_user_secret_repo,
    _ingress_rate_limit_per_minute,
    _interaction_dedupe_key,
    _normalize_installations_payload,
    _oauth_auth_url,
    _oauth_client_id,
    _oauth_client_secret,
    _oauth_permissions,
    _oauth_redirect_uri,
    _oauth_scope,
    _oauth_state_ttl_seconds,
    _oauth_token_url,
    _parse_discord_interaction_command,
    _public_installation_record,
    _rate_limit_key,
    _reset_discord_state_for_tests,
    _resolve_discord_actor_id,
    _safe_int,
    _set_discord_policy,
    _verify_discord_signature,
)

router = APIRouter(prefix="/discord", tags=["discord"])


def _metric_labels(**labels: Any) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in labels.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def _emit_discord_counter(metric_name: str, **labels: Any) -> None:
    try:
        log_counter(metric_name, labels=_metric_labels(**labels))
    except Exception as exc:
        logger.debug("Failed to emit Discord metric {}: {}", metric_name, exc)


def _discord_policy_error_response(policy_error: dict[str, Any], *, guild_id: str | None, action: str | None) -> JSONResponse:
    status_code = int(policy_error.get("status_code") or status.HTTP_403_FORBIDDEN)
    response_payload = {k: v for k, v in policy_error.items() if k != "status_code"}
    headers: dict[str, str] = {}
    retry_after = _safe_int(policy_error.get("retry_after_seconds"))
    if retry_after is not None and retry_after > 0:
        headers["Retry-After"] = str(retry_after)
        _emit_discord_counter(
            "discord_policy_quota_rejections_total",
            guild_id=guild_id or "na",
            action=action or "na",
            error=response_payload.get("error"),
        )
    else:
        _emit_discord_counter(
            "discord_policy_denied_total",
            guild_id=guild_id or "na",
            action=action or "na",
            error=response_payload.get("error"),
        )
    logger.warning(
        "Discord policy denied request: guild_id={} action={} error={}",
        guild_id or "na",
        action or "na",
        response_payload.get("error"),
    )
    return JSONResponse(status_code=status_code, headers=headers, content={"ok": False, **response_payload})


def _enqueue_discord_job(
    *,
    payload: dict[str, Any],
    parsed_command: dict[str, Any],
    owner_user_id: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jm = _get_job_manager()
    request_id = _coerce_nonempty_string(payload.get("id")) or secrets.token_urlsafe(12)
    owner = _coerce_nonempty_string(owner_user_id)
    if not owner and isinstance(payload.get("member"), dict):
        owner = _coerce_nonempty_string(payload.get("member", {}).get("user", {}).get("id"))
    response_mode = _discord_response_mode(payload, policy)
    action = str(parsed_command.get("action") or "ask")
    job = jm.create_job(
        domain="discord",
        queue="default",
        job_type=f"discord_{action}",
        payload={
            "request_id": request_id,
            "application_id": _coerce_nonempty_string(payload.get("application_id")),
            "guild_id": _coerce_nonempty_string(payload.get("guild_id")),
            "channel_id": _coerce_nonempty_string(payload.get("channel_id")),
            "command": parsed_command,
            "response_mode": response_mode,
        },
        owner_user_id=owner,
        request_id=request_id,
    )
    job_id = _safe_int(job.get("id"))
    return {
        "job_id": job_id,
        "request_id": request_id,
        "response_mode": response_mode,
        "job_status": str(job.get("status") or "queued"),
    }


@router.post("/interactions")
async def discord_interactions(request: Request) -> JSONResponse:
    raw_body = await request.body()
    ok, error = _verify_discord_signature(
        raw_body,
        request.headers.get("x-signature-timestamp"),
        request.headers.get("x-signature-ed25519"),
    )
    if not ok:
        status = 503 if error == "public_key_not_configured" else 401
        _emit_discord_counter(
            "discord_signature_failures_total",
            endpoint="interactions",
            reason=error or "unknown",
        )
        return _error_response(status, str(error or "invalid_request"), "Discord request verification failed")

    try:
        payload = await request.json()
    except Exception:
        return _error_response(400, "invalid_json", "Invalid JSON payload")

    if not isinstance(payload, dict):
        return _error_response(400, "invalid_payload", "Payload must be a JSON object")

    allowed, retry_after = _RATE_LIMITER.allow(
        _rate_limit_key(payload, request),
        _ingress_rate_limit_per_minute(),
    )
    if not allowed:
        _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="rate_limited")
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"ok": False, "error": "rate_limited", "retry_after_seconds": retry_after},
        )

    interaction_type = payload.get("type")
    if interaction_type == 1:
        _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="accepted", action="ping")
        return JSONResponse(status_code=200, content={"type": 1})

    dedupe_key = _interaction_dedupe_key(payload, raw_body)
    is_duplicate = _INTERACTION_RECEIPTS.seen_or_store(dedupe_key, _dedupe_ttl_seconds())
    if is_duplicate:
        _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="duplicate")
        return JSONResponse(status_code=200, content={"ok": True, "status": "duplicate"})

    if interaction_type == 2:
        parsed_command, parse_error = _parse_discord_interaction_command(payload)
        if parse_error:
            _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="invalid_command")
            return JSONResponse(status_code=400, content={"ok": False, **parse_error})
        action = str(parsed_command.get("action") or "")
        guild_id = _coerce_nonempty_string(payload.get("guild_id"))
        channel_id = _coerce_nonempty_string(payload.get("channel_id"))
        member = payload.get("member") if isinstance(payload.get("member"), dict) else {}
        request_user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
        discord_user_id = _coerce_nonempty_string(
            member.get("user", {}).get("id") if isinstance(member.get("user"), dict) else None
        ) or _coerce_nonempty_string(request_user.get("id"))
        policy = _discord_policy_for_guild(guild_id)
        actor_user_id, mapping_error = _resolve_discord_actor_id(policy, discord_user_id)
        if mapping_error:
            return _discord_policy_error_response(mapping_error, guild_id=guild_id, action=action)

        policy_error = _evaluate_discord_policy(
            policy=policy,
            guild_id=guild_id,
            channel_id=channel_id,
            actor_user_id=actor_user_id,
            action=action,
        )
        if policy_error:
            return _discord_policy_error_response(policy_error, guild_id=guild_id, action=action)

        logger.bind(
            integration="discord",
            guild_id=guild_id or "na",
            channel_id=channel_id or "na",
            command=action or "na",
            interaction_id=_coerce_nonempty_string(payload.get("id")) or "na",
            actor_user_id=actor_user_id or "na",
        ).info("Discord interaction accepted")

        if action in {"ask", "rag", "summarize"} and not bool(parsed_command.get("inferred")):
            enqueued = _enqueue_discord_job(
                payload=payload,
                parsed_command=parsed_command,
                owner_user_id=actor_user_id,
                policy=policy,
            )
            _emit_discord_counter("discord_jobs_enqueued_total", action=action, guild_id=guild_id or "na")
            _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="queued", action=action)
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "status": "queued",
                    "parsed": parsed_command,
                    **enqueued,
                },
            )

        if action == "status":
            jm = _get_job_manager()
            requested_job_id = _safe_int(parsed_command.get("input"))
            if requested_job_id is None:
                _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="invalid_status_query")
                return JSONResponse(
                    status_code=400,
                    content={
                        "ok": False,
                        "error": "invalid_status_query",
                        "message": "Status command requires a numeric job id. Example: status 42",
                    },
                )
            job = jm.get_job(requested_job_id)
            job_payload = job.get("payload") if isinstance(job, dict) and isinstance(job.get("payload"), dict) else {}
            job_guild_id = _coerce_nonempty_string(job_payload.get("guild_id"))
            owner_user_id = _coerce_nonempty_string(job.get("owner_user_id")) if isinstance(job, dict) else None
            status_scope = str(policy.get("status_scope") or "guild").strip().lower()
            wrong_guild = bool(job_guild_id and guild_id and job_guild_id != guild_id)
            wrong_user_scope = bool(
                status_scope == "guild_and_user"
                and actor_user_id
                and owner_user_id
                and actor_user_id != owner_user_id
            )
            if not job or wrong_guild or wrong_user_scope:
                _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="status_denied")
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "error": "job_not_found", "job_id": requested_job_id},
                )
            _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="accepted", action=action)
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "status": "accepted",
                    "parsed": parsed_command,
                    "job": {
                        "id": requested_job_id,
                        "status": job.get("status"),
                        "domain": job.get("domain"),
                        "queue": job.get("queue"),
                        "job_type": job.get("job_type"),
                    },
                },
            )

        _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="accepted", action=action or "na")
        return JSONResponse(status_code=200, content={"ok": True, "status": "accepted", "parsed": parsed_command})

    _emit_discord_counter("discord_requests_total", endpoint="interactions", outcome="accepted")
    return JSONResponse(status_code=200, content={"ok": True, "status": "accepted"})


@router.get("/jobs/{job_id}")
async def discord_job_status(
    job_id: int,
):
    jm = _get_job_manager()
    job = jm.get_job(int(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    if str(job.get("domain") or "").strip().lower() != "discord":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return {
        "ok": True,
        "job": {
            "id": int(job.get("id") or job_id),
            "status": job.get("status"),
            "domain": job.get("domain"),
            "queue": job.get("queue"),
            "job_type": job.get("job_type"),
        },
    }


@router.post("/oauth/start")
async def discord_oauth_start(
    user: User = Depends(get_request_user),
):
    client_id = _oauth_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="DISCORD_CLIENT_ID is not configured",
        )
    redirect_uri = _oauth_redirect_uri()
    state = secrets.token_urlsafe(32)
    auth_session_id = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=max(1, _oauth_state_ttl_seconds()))

    state_repo = await _get_oauth_state_repo()
    state_secret = _encrypt_discord_payload({"nonce": secrets.token_urlsafe(24)})
    await state_repo.create_state(
        state=state,
        user_id=int(user.id),
        provider="discord",
        auth_session_id=auth_session_id,
        redirect_uri=redirect_uri,
        pkce_verifier_encrypted=state_secret,
        expires_at=expires_at,
        created_at=now,
    )

    query: dict[str, str] = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": _oauth_scope(),
        "state": state,
    }
    permissions = _oauth_permissions()
    if permissions:
        query["permissions"] = permissions
    auth_url = f"{_oauth_auth_url()}?{urlencode(query)}"
    return {
        "ok": True,
        "status": "ready",
        "auth_url": auth_url,
        "auth_session_id": auth_session_id,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/oauth/callback")
async def discord_oauth_callback(
    code: str,
    state: str,
    guild_id: str | None = Query(default=None),
    guild_name: str | None = Query(default=None),
):
    code_value = _coerce_nonempty_string(code)
    state_value = _coerce_nonempty_string(state)
    if not code_value or not state_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth callback parameters",
        )

    state_repo = await _get_oauth_state_repo()
    state_record = await state_repo.consume_state(
        state=state_value,
        provider="discord",
    )
    if not state_record:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired OAuth state",
        )

    redirect_uri = _coerce_nonempty_string(state_record.get("redirect_uri"))
    if not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state is missing redirect metadata",
        )
    user_id_raw = state_record.get("user_id")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state user context is invalid",
        ) from exc

    client_id = _oauth_client_id()
    client_secret = _oauth_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Discord OAuth client credentials are not configured",
        )

    token_payload = await _discord_oauth_token_exchange(
        token_url=_oauth_token_url(),
        form_data={
            "grant_type": "authorization_code",
            "code": code_value,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
    )
    access_token = _coerce_nonempty_string(token_payload.get("access_token"))
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Discord OAuth response missing access_token",
        )

    payload_guild = token_payload.get("guild")
    resolved_guild_id = (
        _coerce_nonempty_string(payload_guild.get("id")) if isinstance(payload_guild, dict) else None
    ) or _coerce_nonempty_string(guild_id)
    resolved_guild_name = (
        _coerce_nonempty_string(payload_guild.get("name")) if isinstance(payload_guild, dict) else None
    ) or _coerce_nonempty_string(guild_name)
    if not resolved_guild_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord OAuth callback is missing guild_id",
        )

    user_repo = await _get_user_secret_repo()
    existing_row = await user_repo.fetch_secret_for_user(user_id, "discord")
    existing_payload = _decrypt_discord_payload(existing_row.get("encrypted_blob")) if existing_row else None
    merged_payload = _normalize_installations_payload(existing_payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
        merged_payload["installations"] = installations

    now = datetime.now(timezone.utc)
    installations[resolved_guild_id] = {
        "guild_id": resolved_guild_id,
        "guild_name": resolved_guild_name,
        "access_token": access_token,
        "refresh_token": _coerce_nonempty_string(token_payload.get("refresh_token")),
        "scope": _coerce_nonempty_string(token_payload.get("scope")),
        "installed_at": now.isoformat(),
        "installed_by": user_id,
        "disabled": False,
    }

    encrypted_blob = _encrypt_discord_payload(merged_payload)
    await user_repo.upsert_secret(
        user_id=user_id,
        provider="discord",
        encrypted_blob=encrypted_blob,
        key_hint=key_hint_for_api_key(access_token),
        metadata={"installation_count": len(installations)},
        updated_at=now,
        created_by=user_id,
        updated_by=user_id,
    )
    return {
        "ok": True,
        "status": "installed",
        "guild_id": resolved_guild_id,
        "guild_name": resolved_guild_name,
    }


@router.get(
    "/admin/policy",
    dependencies=[Depends(require_roles("admin"))],
)
async def discord_admin_get_policy(
    guild_id: str | None = Query(default=None),
):
    cleaned_guild_id = _coerce_nonempty_string(guild_id)
    policy = _discord_policy_for_guild(cleaned_guild_id)
    return {
        "ok": True,
        "guild_id": cleaned_guild_id,
        "policy": policy,
    }


@router.put(
    "/admin/policy",
    dependencies=[Depends(require_roles("admin"))],
)
async def discord_admin_set_policy(
    payload: dict[str, Any] | None = None,
):
    body = dict(payload or {})
    cleaned_guild_id = _coerce_nonempty_string(body.pop("guild_id", None))
    scope = "guild" if cleaned_guild_id else "default"
    guild_id, policy = _set_discord_policy(cleaned_guild_id, body)
    _emit_discord_counter("discord_policy_updates_total", scope=scope)
    return {
        "ok": True,
        "status": "updated",
        "guild_id": guild_id,
        "policy": policy,
    }


@router.get("/admin/installations")
async def discord_admin_list_installations(
    user: User = Depends(get_request_user),
):
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(int(user.id), "discord")
    payload = _decrypt_discord_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
    results = []
    for guild_id_key, installation in installations.items():
        if not isinstance(installation, dict):
            continue
        record = _public_installation_record(installation)
        record["guild_id"] = record.get("guild_id") or guild_id_key
        results.append(record)
    results.sort(key=lambda item: str(item.get("guild_id") or ""))
    return {"ok": True, "installations": results}


@router.delete("/admin/installations/{guild_id}")
async def discord_admin_delete_installation(
    guild_id: str,
    user: User = Depends(get_request_user),
):
    cleaned_guild_id = _coerce_nonempty_string(guild_id)
    if not cleaned_guild_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="guild_id is required")
    user_id = int(user.id)
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(user_id, "discord")
    payload = _decrypt_discord_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict) or cleaned_guild_id not in installations:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="installation_not_found")

    installations.pop(cleaned_guild_id, None)
    now = datetime.now(timezone.utc)
    if not installations:
        await user_repo.delete_secret(
            user_id=user_id,
            provider="discord",
            revoked_by=user_id,
            revoked_at=now,
        )
    else:
        replacement_token: str | None = None
        for remaining in installations.values():
            if isinstance(remaining, dict):
                replacement_token = _coerce_nonempty_string(remaining.get("access_token"))
                if replacement_token:
                    break
        await user_repo.upsert_secret(
            user_id=user_id,
            provider="discord",
            encrypted_blob=_encrypt_discord_payload(merged_payload),
            key_hint=key_hint_for_api_key(replacement_token) if replacement_token else None,
            metadata={"installation_count": len(installations)},
            updated_at=now,
            created_by=user_id,
            updated_by=user_id,
        )
    return {"ok": True, "status": "deleted", "guild_id": cleaned_guild_id}


@router.put("/admin/installations/{guild_id}")
async def discord_admin_set_installation_state(
    guild_id: str,
    payload: dict[str, Any] | None = None,
    user: User = Depends(get_request_user),
):
    cleaned_guild_id = _coerce_nonempty_string(guild_id)
    if not cleaned_guild_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="guild_id is required")

    disabled = bool((payload or {}).get("disabled"))
    user_id = int(user.id)
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(user_id, "discord")
    stored_payload = _decrypt_discord_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(stored_payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
        merged_payload["installations"] = installations
    installation = installations.get(cleaned_guild_id)
    if not isinstance(installation, dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="installation_not_found")

    installation["disabled"] = disabled
    now = datetime.now(timezone.utc)
    key_hint_token = _coerce_nonempty_string(installation.get("access_token"))
    await user_repo.upsert_secret(
        user_id=user_id,
        provider="discord",
        encrypted_blob=_encrypt_discord_payload(merged_payload),
        key_hint=key_hint_for_api_key(key_hint_token) if key_hint_token else None,
        metadata={"installation_count": len(installations)},
        updated_at=now,
        created_by=user_id,
        updated_by=user_id,
    )
    return {
        "ok": True,
        "status": "updated",
        "guild_id": cleaned_guild_id,
        "disabled": disabled,
    }
