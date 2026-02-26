from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_roles
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import key_hint_for_api_key
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter

from tldw_Server_API.app.api.v1.endpoints.slack_support import (
    _COMMAND_RECEIPTS,
    _EVENT_RECEIPTS,
    _RATE_LIMITER,
    _coerce_nonempty_string,
    _command_fingerprint,
    _decrypt_slack_payload,
    _dedupe_ttl_seconds,
    _encrypt_slack_payload,
    _error_response,
    _evaluate_slack_policy,
    _get_job_manager,
    _get_oauth_state_repo,
    _get_user_secret_repo,
    _ingress_rate_limit_per_minute,
    _is_bot_event,
    _normalize_installations_payload,
    _oauth_auth_url,
    _oauth_client_id,
    _oauth_client_secret,
    _oauth_redirect_uri,
    _oauth_scopes,
    _oauth_state_ttl_seconds,
    _oauth_token_url,
    _parse_slack_command,
    _parse_slack_mention,
    _public_installation_record,
    _rate_limit_key_for_commands,
    _rate_limit_key_for_events,
    _reset_slack_state_for_tests,
    _resolve_slack_actor_id,
    _safe_int,
    _set_slack_policy,
    _slack_response_mode,
    _slack_oauth_token_exchange,
    _slack_policy_for_workspace,
    _verify_slack_signature,
)

router = APIRouter(prefix="/slack", tags=["slack"])


def _metric_labels(**labels: Any) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in labels.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def _emit_slack_counter(metric_name: str, **labels: Any) -> None:
    try:
        log_counter(metric_name, labels=_metric_labels(**labels))
    except Exception as exc:
        logger.debug("Failed to emit Slack metric {}: {}", metric_name, exc)


def _slack_policy_error_response(policy_error: dict[str, Any], *, team_id: str | None, action: str | None) -> JSONResponse:
    status_code = int(policy_error.get("status_code") or status.HTTP_403_FORBIDDEN)
    response_payload = {k: v for k, v in policy_error.items() if k != "status_code"}
    headers: dict[str, str] = {}
    retry_after = _safe_int(policy_error.get("retry_after_seconds"))
    if retry_after is not None and retry_after > 0:
        headers["Retry-After"] = str(retry_after)
        _emit_slack_counter(
            "slack_policy_quota_rejections_total",
            team_id=team_id or "na",
            action=action or "na",
            error=response_payload.get("error"),
        )
    else:
        _emit_slack_counter(
            "slack_policy_denied_total",
            team_id=team_id or "na",
            action=action or "na",
            error=response_payload.get("error"),
        )
    logger.warning(
        "Slack policy denied request: team_id={} action={} error={}",
        team_id or "na",
        action or "na",
        response_payload.get("error"),
    )
    return JSONResponse(status_code=status_code, headers=headers, content={"ok": False, **response_payload})


def _enqueue_slack_job(
    *,
    form_payload: dict[str, str],
    parsed_command: dict[str, Any],
    owner_user_id: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jm = _get_job_manager()
    request_id = _coerce_nonempty_string(form_payload.get("trigger_id")) or secrets.token_urlsafe(12)
    owner = _coerce_nonempty_string(owner_user_id) or _coerce_nonempty_string(form_payload.get("user_id")) or None
    action = str(parsed_command.get("action") or "ask")
    response_mode = _slack_response_mode(form_payload, policy)
    job = jm.create_job(
        domain="slack",
        queue="default",
        job_type=f"slack_{action}",
        payload={
            "request_id": request_id,
            "team_id": _coerce_nonempty_string(form_payload.get("team_id")),
            "channel_id": _coerce_nonempty_string(form_payload.get("channel_id")),
            "thread_ts": _coerce_nonempty_string(form_payload.get("thread_ts")),
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


@router.post("/events")
async def slack_events(request: Request) -> JSONResponse:
    raw_body = await request.body()
    ok, error = _verify_slack_signature(
        raw_body,
        request.headers.get("x-slack-request-timestamp"),
        request.headers.get("x-slack-signature"),
    )
    if not ok:
        status = 503 if error == "signing_secret_not_configured" else 401
        _emit_slack_counter(
            "slack_signature_failures_total",
            endpoint="events",
            reason=error or "unknown",
        )
        return _error_response(status, str(error or "invalid_request"), "Slack request verification failed")

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error_response(400, "invalid_json", "Invalid JSON payload")

    if not isinstance(payload, dict):
        return _error_response(400, "invalid_payload", "Payload must be a JSON object")

    allowed, retry_after = _RATE_LIMITER.allow(
        _rate_limit_key_for_events(payload, request),
        _ingress_rate_limit_per_minute(),
    )
    if not allowed:
        _emit_slack_counter("slack_requests_total", endpoint="events", outcome="rate_limited")
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"ok": False, "error": "rate_limited", "retry_after_seconds": retry_after},
        )

    event_type = str(payload.get("type") or "").strip()
    if event_type == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            return _error_response(400, "missing_challenge", "Missing challenge")
        return JSONResponse(status_code=200, content={"challenge": challenge})

    if event_type == "event_callback":
        event_id = str(payload.get("event_id") or "").strip()
        dedupe_key = event_id or hashlib.sha256(raw_body).hexdigest()
        is_duplicate = _EVENT_RECEIPTS.seen_or_store(dedupe_key, _dedupe_ttl_seconds())
        if is_duplicate:
            _emit_slack_counter("slack_requests_total", endpoint="events", outcome="duplicate")
            return JSONResponse(status_code=200, content={"ok": True, "status": "duplicate"})

        if _is_bot_event(payload):
            _emit_slack_counter("slack_requests_total", endpoint="events", outcome="ignored_bot_event")
            return JSONResponse(status_code=200, content={"ok": True, "status": "ignored_bot_event"})

        mention_parsed = _parse_slack_mention(payload)
        if mention_parsed:
            event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
            team_id = _coerce_nonempty_string(payload.get("team_id"))
            channel_id = _coerce_nonempty_string(event.get("channel")) if isinstance(event, dict) else None
            slack_user_id = _coerce_nonempty_string(event.get("user")) if isinstance(event, dict) else None
            policy = _slack_policy_for_workspace(team_id)
            actor_user_id, mapping_error = _resolve_slack_actor_id(policy, slack_user_id)
            if mapping_error:
                return _slack_policy_error_response(
                    mapping_error,
                    team_id=team_id,
                    action=str(mention_parsed.get("action") or ""),
                )
            policy_error = _evaluate_slack_policy(
                policy=policy,
                team_id=team_id,
                channel_id=channel_id,
                actor_user_id=actor_user_id,
                action=str(mention_parsed.get("action") or ""),
            )
            if policy_error:
                return _slack_policy_error_response(
                    policy_error,
                    team_id=team_id,
                    action=str(mention_parsed.get("action") or ""),
                )
            _emit_slack_counter(
                "slack_requests_total",
                endpoint="events",
                outcome="accepted",
                action=str(mention_parsed.get("action") or "na"),
            )
            return JSONResponse(
                status_code=200,
                content={"ok": True, "status": "accepted", "parsed": mention_parsed},
            )
        _emit_slack_counter("slack_requests_total", endpoint="events", outcome="accepted")
        return JSONResponse(status_code=200, content={"ok": True, "status": "accepted"})

    _emit_slack_counter("slack_requests_total", endpoint="events", outcome="accepted")
    return JSONResponse(status_code=200, content={"ok": True, "status": "accepted"})


@router.post("/commands")
async def slack_commands(request: Request) -> JSONResponse:
    raw_body = await request.body()
    ok, error = _verify_slack_signature(
        raw_body,
        request.headers.get("x-slack-request-timestamp"),
        request.headers.get("x-slack-signature"),
    )
    if not ok:
        status = 503 if error == "signing_secret_not_configured" else 401
        _emit_slack_counter(
            "slack_signature_failures_total",
            endpoint="commands",
            reason=error or "unknown",
        )
        return _error_response(status, str(error or "invalid_request"), "Slack request verification failed")

    try:
        parsed = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return _error_response(400, "invalid_form", "Unable to parse form body")

    form_payload = {k: (v[0] if v else "") for k, v in parsed.items()}
    allowed, retry_after = _RATE_LIMITER.allow(
        _rate_limit_key_for_commands(form_payload, request),
        _ingress_rate_limit_per_minute(),
    )
    if not allowed:
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="rate_limited")
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"ok": False, "error": "rate_limited", "retry_after_seconds": retry_after},
        )

    dedupe_key = _command_fingerprint(raw_body)
    is_duplicate = _COMMAND_RECEIPTS.seen_or_store(dedupe_key, _dedupe_ttl_seconds())
    if is_duplicate:
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="duplicate")
        return JSONResponse(status_code=200, content={"ok": True, "status": "duplicate"})

    parsed_command, parse_error = _parse_slack_command(form_payload)
    if parse_error:
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="invalid_command")
        return JSONResponse(
            status_code=400,
            content={"ok": False, **parse_error},
        )
    action = str(parsed_command.get("action") or "")
    team_id = _coerce_nonempty_string(form_payload.get("team_id")) or _coerce_nonempty_string(form_payload.get("team_domain"))
    channel_id = _coerce_nonempty_string(form_payload.get("channel_id"))
    slack_user_id = _coerce_nonempty_string(form_payload.get("user_id"))
    policy = _slack_policy_for_workspace(team_id)
    actor_user_id, mapping_error = _resolve_slack_actor_id(policy, slack_user_id)
    if mapping_error:
        return _slack_policy_error_response(mapping_error, team_id=team_id, action=action)

    policy_error = _evaluate_slack_policy(
        policy=policy,
        team_id=team_id,
        channel_id=channel_id,
        actor_user_id=actor_user_id,
        action=action,
    )
    if policy_error:
        return _slack_policy_error_response(policy_error, team_id=team_id, action=action)

    logger.bind(
        integration="slack",
        workspace_id=team_id or "na",
        channel_id=channel_id or "na",
        command=action or "na",
        request_id=_coerce_nonempty_string(form_payload.get("trigger_id")) or "na",
        actor_user_id=actor_user_id or "na",
    ).info("Slack command accepted")

    if action in {"ask", "rag", "summarize"}:
        enqueued = _enqueue_slack_job(
            form_payload=form_payload,
            parsed_command=parsed_command,
            owner_user_id=actor_user_id,
            policy=policy,
        )
        _emit_slack_counter("slack_jobs_enqueued_total", action=action, team_id=team_id or "na")
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="queued", action=action)
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
            _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="invalid_status_query")
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
        job_team_id = _coerce_nonempty_string(job_payload.get("team_id"))
        owner_user_id = _coerce_nonempty_string(job.get("owner_user_id")) if isinstance(job, dict) else None
        status_scope = str(policy.get("status_scope") or "workspace").strip().lower()
        wrong_workspace = bool(job_team_id and team_id and job_team_id != team_id)
        wrong_user_scope = bool(
            status_scope == "workspace_and_user"
            and actor_user_id
            and owner_user_id
            and actor_user_id != owner_user_id
        )
        if not job or wrong_workspace or wrong_user_scope:
            _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="status_denied")
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "job_not_found", "job_id": requested_job_id},
            )
        _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="accepted", action=action)
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

    _emit_slack_counter("slack_requests_total", endpoint="commands", outcome="accepted", action=action or "na")
    return JSONResponse(
        status_code=200,
        content={"ok": True, "status": "accepted", "parsed": parsed_command},
    )


@router.get("/jobs/{job_id}")
async def slack_job_status(
    job_id: int,
):
    jm = _get_job_manager()
    job = jm.get_job(int(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    if str(job.get("domain") or "").strip().lower() != "slack":
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
async def slack_oauth_start(
    user: User = Depends(get_request_user),
):
    client_id = _oauth_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SLACK_CLIENT_ID is not configured",
        )
    redirect_uri = _oauth_redirect_uri()
    state = secrets.token_urlsafe(32)
    auth_session_id = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=max(1, _oauth_state_ttl_seconds()))

    state_repo = await _get_oauth_state_repo()
    state_secret = _encrypt_slack_payload({"nonce": secrets.token_urlsafe(24)})
    await state_repo.create_state(
        state=state,
        user_id=int(user.id),
        provider="slack",
        auth_session_id=auth_session_id,
        redirect_uri=redirect_uri,
        pkce_verifier_encrypted=state_secret,
        expires_at=expires_at,
        created_at=now,
    )

    query = {
        "client_id": client_id,
        "scope": _oauth_scopes(),
        "redirect_uri": redirect_uri,
        "state": state,
    }
    auth_url = f"{_oauth_auth_url()}?{urlencode(query)}"
    return {
        "ok": True,
        "status": "ready",
        "auth_url": auth_url,
        "auth_session_id": auth_session_id,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/oauth/callback")
async def slack_oauth_callback(
    code: str,
    state: str,
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
        provider="slack",
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
            detail="Slack OAuth client credentials are not configured",
        )

    token_payload = await _slack_oauth_token_exchange(
        token_url=_oauth_token_url(),
        form_data={
            "code": code_value,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
    )
    if not bool(token_payload.get("ok")):
        provider_error = _coerce_nonempty_string(token_payload.get("error")) or "token_exchange_failed"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Slack OAuth token exchange failed: {provider_error}",
        )

    access_token = _coerce_nonempty_string(token_payload.get("access_token"))
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack OAuth response missing access_token",
        )

    team_data = token_payload.get("team")
    team_id = _coerce_nonempty_string(team_data.get("id")) if isinstance(team_data, dict) else None
    team_name = _coerce_nonempty_string(team_data.get("name")) if isinstance(team_data, dict) else None
    if not team_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack OAuth response missing team.id",
        )

    user_repo = await _get_user_secret_repo()
    existing_row = await user_repo.fetch_secret_for_user(user_id, "slack")
    existing_payload = _decrypt_slack_payload(existing_row.get("encrypted_blob")) if existing_row else None
    merged_payload = _normalize_installations_payload(existing_payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
        merged_payload["installations"] = installations

    now = datetime.now(timezone.utc)
    authed_user = token_payload.get("authed_user")
    authed_user_id = _coerce_nonempty_string(authed_user.get("id")) if isinstance(authed_user, dict) else None
    installations[team_id] = {
        "team_id": team_id,
        "team_name": team_name,
        "enterprise_id": _coerce_nonempty_string(token_payload.get("enterprise_id")),
        "bot_user_id": _coerce_nonempty_string(token_payload.get("bot_user_id")),
        "scope": _coerce_nonempty_string(token_payload.get("scope")),
        "authed_user_id": authed_user_id,
        "access_token": access_token,
        "installed_at": now.isoformat(),
        "installed_by": user_id,
        "disabled": False,
    }

    encrypted_blob = _encrypt_slack_payload(merged_payload)
    await user_repo.upsert_secret(
        user_id=user_id,
        provider="slack",
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
        "team_id": team_id,
        "team_name": team_name,
    }


@router.get(
    "/admin/policy",
    dependencies=[Depends(require_roles("admin"))],
)
async def slack_admin_get_policy(
    team_id: str | None = Query(default=None),
):
    cleaned_team_id = _coerce_nonempty_string(team_id)
    policy = _slack_policy_for_workspace(cleaned_team_id)
    return {
        "ok": True,
        "team_id": cleaned_team_id,
        "policy": policy,
    }


@router.put(
    "/admin/policy",
    dependencies=[Depends(require_roles("admin"))],
)
async def slack_admin_set_policy(
    payload: dict[str, Any] | None = None,
):
    body = dict(payload or {})
    cleaned_team_id = _coerce_nonempty_string(body.pop("team_id", None))
    scope = "workspace" if cleaned_team_id else "default"
    team_id, policy = _set_slack_policy(cleaned_team_id, body)
    _emit_slack_counter("slack_policy_updates_total", scope=scope)
    return {
        "ok": True,
        "status": "updated",
        "team_id": team_id,
        "policy": policy,
    }


@router.get("/admin/installations")
async def slack_admin_list_installations(
    user: User = Depends(get_request_user),
):
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(int(user.id), "slack")
    payload = _decrypt_slack_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
    results = []
    for team_id, installation in installations.items():
        if not isinstance(installation, dict):
            continue
        record = _public_installation_record(installation)
        record["team_id"] = record.get("team_id") or team_id
        results.append(record)
    results.sort(key=lambda item: str(item.get("team_id") or ""))
    return {"ok": True, "installations": results}


@router.delete("/admin/installations/{team_id}")
async def slack_admin_delete_installation(
    team_id: str,
    user: User = Depends(get_request_user),
):
    cleaned_team_id = _coerce_nonempty_string(team_id)
    if not cleaned_team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is required")
    user_id = int(user.id)
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(user_id, "slack")
    payload = _decrypt_slack_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict) or cleaned_team_id not in installations:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="installation_not_found")

    installations.pop(cleaned_team_id, None)
    now = datetime.now(timezone.utc)
    if not installations:
        await user_repo.delete_secret(
            user_id=user_id,
            provider="slack",
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
            provider="slack",
            encrypted_blob=_encrypt_slack_payload(merged_payload),
            key_hint=key_hint_for_api_key(replacement_token) if replacement_token else None,
            metadata={"installation_count": len(installations)},
            updated_at=now,
            created_by=user_id,
            updated_by=user_id,
        )
    return {"ok": True, "status": "deleted", "team_id": cleaned_team_id}


@router.put("/admin/installations/{team_id}")
async def slack_admin_set_installation_state(
    team_id: str,
    payload: dict[str, Any] | None = None,
    user: User = Depends(get_request_user),
):
    cleaned_team_id = _coerce_nonempty_string(team_id)
    if not cleaned_team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is required")

    disabled = bool((payload or {}).get("disabled"))
    user_id = int(user.id)
    user_repo = await _get_user_secret_repo()
    row = await user_repo.fetch_secret_for_user(user_id, "slack")
    stored_payload = _decrypt_slack_payload(row.get("encrypted_blob")) if row else None
    merged_payload = _normalize_installations_payload(stored_payload)
    installations = merged_payload.get("installations")
    if not isinstance(installations, dict):
        installations = {}
        merged_payload["installations"] = installations
    installation = installations.get(cleaned_team_id)
    if not isinstance(installation, dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="installation_not_found")

    installation["disabled"] = disabled
    now = datetime.now(timezone.utc)
    key_hint_token = _coerce_nonempty_string(installation.get("access_token")) or ""
    await user_repo.upsert_secret(
        user_id=user_id,
        provider="slack",
        encrypted_blob=_encrypt_slack_payload(merged_payload),
        key_hint=key_hint_for_api_key(key_hint_token) if key_hint_token else None,
        metadata={"installation_count": len(installations)},
        updated_at=now,
        created_by=user_id,
        updated_by=user_id,
    )
    return {
        "ok": True,
        "status": "updated",
        "team_id": cleaned_team_id,
        "disabled": disabled,
    }
