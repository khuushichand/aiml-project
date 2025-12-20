from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable
import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.status import HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.connectors import (
    ConnectorProvider,
    ConnectorAccount,
    ConnectorSource,
    SyncOptions,
    ImportJob,
    AuthorizeURLResponse,
    ConnectorPolicy,
    ConnectorSourceCreateRequest,
    ConnectorSourcePatchRequest,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_current_active_user,
    get_auth_principal,
    require_roles,
    get_db_transaction,
    get_user_org_policy,
    get_org_policy_from_principal,
    require_permissions,
)
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.External_Sources import (
    get_connector_by_name,
)
from tldw_Server_API.app.core.External_Sources.policy import (
    get_default_policy_from_env,
    evaluate_policy_constraints,
)
from tldw_Server_API.app.core.External_Sources.connectors_service import (
    upsert_policy,
    get_policy,
    create_account,
    list_accounts,
    delete_account,
    create_source,
    list_sources,
    update_source,
    create_import_job,
    get_account_tokens,
    get_account_email,
    get_account_for_user,
    count_connectors_jobs_today,
    create_oauth_state,
    consume_oauth_state,
)
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, ensure_traceparent, get_ps_logger


router = APIRouter(prefix="/connectors", tags=["connectors"])


def _resolve_redirect_base(request: Optional[Request], conn) -> str:
    """Resolve connector redirect base, allowing request to be optional for tests.

    Priority: CONNECTOR_REDIRECT_BASE_URL env var > request.base_url > connector.redirect_base.
    Returns empty string only in test scenarios where the OAuth flow is mocked.
    """
    base = os.getenv("CONNECTOR_REDIRECT_BASE_URL")
    if base:
        return base.rstrip("/")
    if request is not None:
        try:
            return str(request.base_url).rstrip("/")
        except (AttributeError, TypeError, ValueError) as e:
            logger.debug(f"Failed to resolve base_url from request: {e}")
    resolved = (getattr(conn, "redirect_base", "") or "").rstrip("/")
    if not resolved and request is not None:
        logger.warning(
            "Redirect base could not be resolved; OAuth redirect_uri may be invalid (expected only in tests)"
        )
    return resolved


def _get_user_id(current_user: Dict[str, Any]) -> int:
    user_id = current_user.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    try:
        return int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid user ID in token") from exc


def get_connectors_job_counter() -> Callable[[int], int]:
    """Dependency to supply the connectors job counter (overrideable in tests)."""
    return count_connectors_jobs_today


@router.get("/providers", response_model=List[ConnectorProvider])
async def list_providers() -> List[ConnectorProvider]:
    return [
        ConnectorProvider(name="drive", scopes_required=["drive.readonly"], auth_type="oauth2"),
        ConnectorProvider(name="notion", scopes_required=[], auth_type="oauth2"),
    ]


@router.post("/providers/{provider}/authorize", response_model=AuthorizeURLResponse)
async def start_authorize(
    provider: str,
    state: Optional[str] = None,
    scopes: Optional[str] = None,
    request: Request = None,
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> AuthorizeURLResponse:
    conn = get_connector_by_name(provider)
    redirect_base = _resolve_redirect_base(request, conn)
    if redirect_base:
        conn.redirect_base = redirect_base
    state = state or secrets.token_urlsafe(32)
    user_id = _get_user_id(current_user)
    await create_oauth_state(db, user_id, provider, state)
    scopes_list = [s for s in (scopes or "").split(",") if s]
    url = conn.authorize_url(state=state, scopes=scopes_list or None, redirect_path=f"/api/v1/connectors/providers/{provider}/callback")
    return AuthorizeURLResponse(auth_url=url, state=state)


@router.get("/providers/{provider}/callback", response_model=ConnectorAccount)
async def oauth_callback(
    provider: str,
    code: str,
    state: Optional[str] = None,
    request: Request = None,
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    org_policy: Dict[str, Any] = Depends(get_org_policy_from_principal),
) -> ConnectorAccount:
    conn = get_connector_by_name(provider)
    pol = org_policy
    user_id = _get_user_id(current_user)
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")
    default_ttl_minutes = 10
    raw_ttl_minutes = os.getenv("CONNECTOR_OAUTH_STATE_TTL_MINUTES")
    ttl_minutes = default_ttl_minutes
    if raw_ttl_minutes is not None:
        raw_ttl_minutes = raw_ttl_minutes.strip()
        if not raw_ttl_minutes:
            logger.warning(
                "CONNECTOR_OAUTH_STATE_TTL_MINUTES is empty; using default {}",
                default_ttl_minutes,
            )
        else:
            try:
                ttl_minutes = int(raw_ttl_minutes)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid CONNECTOR_OAUTH_STATE_TTL_MINUTES={!r}; using default {}",
                    raw_ttl_minutes,
                    default_ttl_minutes,
                )
                ttl_minutes = default_ttl_minutes
    if ttl_minutes <= 0:
        logger.warning(
            "CONNECTOR_OAUTH_STATE_TTL_MINUTES must be positive; using default {}",
            default_ttl_minutes,
        )
        ttl_minutes = default_ttl_minutes
    ok_state = await consume_oauth_state(
        db,
        user_id=user_id,
        provider=provider,
        state=state,
        max_age_minutes=ttl_minutes,
    )
    if not ok_state:
        raise HTTPException(status_code=403, detail="Invalid or expired OAuth state")

    # Enforce org-level account linking role based on org policy; single-user
    # callers pass via their role/admin claims rather than global mode checks.
    try:
        role = str(current_user.get("role", "member")).lower()
        required = str(pol.get("account_linking_role", "admin")).lower()
        # Admin bypass
        if role != "admin" and required and role != required:
            raise HTTPException(status_code=403, detail="Account linking not permitted for your role")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Policy enforcement error on callback for provider '{provider}': {e}")
        raise HTTPException(
            status_code=403,
            detail="Account linking denied: policy enforcement failed",
        ) from e

    # Exchange code with redirect derived from env base + this path
    base = _resolve_redirect_base(request, conn)
    redirect_uri = f"{base.rstrip('/')}/api/v1/connectors/providers/{provider}/callback" if base else ""
    tokens = await conn.exchange_code(code, redirect_uri)
    # Optional email/workspace fetch for policy enforcement
    acct_email: Optional[str] = None
    notion_workspace_id: Optional[str] = None
    if provider == 'drive' and (tokens.get('access_token')):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # userinfo endpoint provides email when scopes include 'email'
                async with session.get('https://openidconnect.googleapis.com/v1/userinfo', headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=15) as resp:
                    if resp.status == 200:
                        info = await resp.json()
                        acct_email = info.get('email')
                        tokens['email'] = acct_email
        except Exception:
            pass
    elif provider == 'notion':
        notion_workspace_id = tokens.get('workspace_id')
    # Enforce additional org policy constraints at callback across modes using
    # the same org policy surface.
    try:
        ok, why = evaluate_policy_constraints(
            pol,
            provider=provider,
            remote_path=None,
            notion_workspace_id=notion_workspace_id,
            account_email=acct_email,
        )
    except Exception as e:
        logger.exception(f"Callback constraint evaluation failed for provider '{provider}': {e}")
        raise HTTPException(
            status_code=500,
            detail="Account linking denied: policy evaluation failed",
        ) from e
    if not ok:
        raise HTTPException(status_code=403, detail=why or "Account not permitted by org policy")

    acct = await create_account(
        db,
        user_id=user_id,
        provider=provider,
        display_name=str(tokens.get("display_name") or tokens.get("workspace_name") or f"{provider.title()} Account"),
        email=acct_email or tokens.get("email"),
        tokens=tokens,
    )
    return ConnectorAccount(
        id=int(acct.get("id")),
        provider=provider, display_name=str(acct.get("display_name")),
        email=acct.get("email"), created_at=str(acct.get("created_at")), connected=True,
    )


@router.get("/accounts", response_model=List[ConnectorAccount])
async def get_accounts(
    db=Depends(get_db_transaction), current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[ConnectorAccount]:
    user_id = _get_user_id(current_user)
    rows = await list_accounts(db, user_id)
    return [ConnectorAccount(id=int(r["id"]), provider=r["provider"], display_name=r.get("display_name") or "", email=r.get("email"), created_at=str(r.get("created_at")), connected=True) for r in rows]


@router.delete("/accounts/{account_id}")
async def remove_account(
    account_id: int, db=Depends(get_db_transaction), current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    user_id = _get_user_id(current_user)
    await delete_account(db, user_id, account_id)
    return {"ok": True}


@router.get("/providers/{provider}/sources/browse")
async def browse_provider_sources(
    provider: str,
    account_id: int = Query(..., ge=1),
    parent_remote_id: Optional[str] = None,
    page_size: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = None,
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> Dict[str, Any]:
    user_id = _get_user_id(current_user)
    tokens = await get_account_tokens(db, user_id, account_id)
    if not tokens:
        raise HTTPException(status_code=404, detail="Account not found")
    email = await get_account_email(db, user_id, account_id)
    conn = get_connector_by_name(provider)
    # For Drive, parent_remote_id None implies root
    try:
        if provider == "drive":
            items, next_cursor = await conn.list_files({"tokens": tokens, "email": email}, parent_remote_id or "root", page_size=page_size, cursor=cursor)
        elif provider == "notion":
            # Notion: treat parent_remote_id as workspace hint; we search globally for now
            items, next_cursor = await conn.list_sources({"tokens": tokens, "email": email}, parent_remote_id=parent_remote_id, page_size=page_size, cursor=cursor)
        else:
            items, next_cursor = [], None
    except Exception as e:
        logger.error(f"Browse error for {provider}: {e}")
        raise HTTPException(status_code=502, detail=f"Browse failed: {e}")
    return {"items": items, "next_cursor": next_cursor}


@router.post("/sources", response_model=ConnectorSource)
async def add_source(
    payload: ConnectorSourceCreateRequest,
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    org_policy: Dict[str, Any] = Depends(get_org_policy_from_principal),
) -> ConnectorSource:
    # payload keys: account_id, provider, remote_id, type, path, options
    account_id = int(payload.account_id)
    provider = str(payload.provider)
    remote_id = str(payload.remote_id)
    type_ = str(payload.type)
    path = payload.path
    options = payload.options or {}

    user_id = _get_user_id(current_user)
    acct = await get_account_for_user(db, user_id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    acct_provider = str(acct.get("provider") or "").lower()
    if acct_provider and acct_provider != provider.lower():
        raise HTTPException(status_code=400, detail="Account provider mismatch")

    # Enforce org policy on provider/path for all modes; single-user callers
    # rely on their admin/role claims rather than mode flags.
    try:
        ok, why = evaluate_policy_constraints(org_policy, provider=provider, remote_path=path)
    except Exception as e:
        logger.exception(f"Policy evaluation failed for provider '{provider}': {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Source denied: policy evaluation failed",
        ) from e
    if not ok:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=why or "Source denied by org policy")

    row = await create_source(
        db,
        account_id=account_id,
        provider=provider,
        remote_id=remote_id,
        type_=type_,
        path=path,
        options=options,
        enabled=True,
    )
    return ConnectorSource(
        id=int(row.get("id")),
        account_id=int(row.get("account_id")),
        provider=row.get("provider"),
        remote_id=row.get("remote_id"),
        type=row.get("type"),
        path=row.get("path"),
        options=SyncOptions(**(row.get("options") or {})),
        enabled=bool(row.get("enabled", True)),
        last_synced_at=str(row.get("last_synced_at")) if row.get("last_synced_at") else None,
    )


@router.get("/sources", response_model=List[ConnectorSource])
async def get_sources(
    db=Depends(get_db_transaction), current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[ConnectorSource]:
    user_id = _get_user_id(current_user)
    rows = await list_sources(db, user_id)
    out: List[ConnectorSource] = []
    for r in rows:
        out.append(
            ConnectorSource(
                id=int(r.get("id")),
                account_id=int(r.get("account_id")),
                provider=r.get("provider"),
                remote_id=r.get("remote_id"),
                type=r.get("type"),
                path=r.get("path"),
                options=SyncOptions(**(r.get("options") or {})),
                enabled=bool(r.get("enabled", True)),
                last_synced_at=str(r.get("last_synced_at")) if r.get("last_synced_at") else None,
            )
        )
    return out


@router.patch("/sources/{source_id}", response_model=ConnectorSource)
async def patch_source(
    source_id: int,
    payload: ConnectorSourcePatchRequest,
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> ConnectorSource:
    enabled = payload.enabled
    options = payload.options
    user_id = _get_user_id(current_user)
    row = await update_source(db, user_id, source_id, enabled=enabled, options=options)
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    return ConnectorSource(
        id=int(row.get("id")),
        account_id=int(row.get("account_id")),
        provider=row.get("provider"),
        remote_id=row.get("remote_id"),
        type=row.get("type"),
        path=row.get("path"),
        options=SyncOptions(**(row.get("options") or {})),
        enabled=bool(row.get("enabled", True)),
        last_synced_at=str(row.get("last_synced_at")) if row.get("last_synced_at") else None,
    )


@router.post("/sources/{source_id}/import", response_model=ImportJob)
async def import_source(
    source_id: int,
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    request: Request = None,
    org_policy: Dict[str, Any] = Depends(get_org_policy_from_principal),
    count_jobs_fn: Callable[[int], int] = Depends(get_connectors_job_counter),
) -> ImportJob:
    # Enforce per-role daily quota from org policy for all modes; single-user
    # admin callers naturally bypass via their configured role/quotas.
    user_id = _get_user_id(current_user)
    role = str(current_user.get("role", "member")).lower()
    qpr = org_policy.get("quotas_per_role") or {}
    limits = qpr.get(role) or {}
    max_jobs = int(limits.get("max_jobs_per_day") or 0)
    if max_jobs > 0:
        try:
            today_count = count_jobs_fn(user_id)
        except Exception as exc:
            logger.exception(f"Quota check failed for user_id={user_id}: {exc}")
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Daily import quota check failed",
            ) from exc
        if today_count >= max_jobs:
            raise HTTPException(status_code=429, detail="Daily import quota reached for your role")
    # Correlate request → job
    rid = ensure_request_id(request) if request is not None else None
    tp = ensure_traceparent(request) if request is not None else ""
    job = await create_import_job(user_id, source_id, request_id=rid)
    # Structured log for queued import
    get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="connectors", traceparent=tp).info(
        "Queued connectors import job: job_id=%s source_id=%s", job.get("id"), source_id
    )
    return ImportJob(**job)


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: int) -> Dict[str, Any]:
    try:
        from tldw_Server_API.app.core.Jobs.manager import JobManager
        jm = JobManager()
        job = jm.get_job(int(job_id))
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        # Trim payload if large
        job.pop("payload", None)
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Admin: Org-level policy
@router.get(
    "/admin/policy",
    response_model=ConnectorPolicy,
    dependencies=[
        Depends(get_auth_principal),
        Depends(require_roles("admin")),
        Depends(require_permissions(SYSTEM_CONFIGURE)),
    ],
)
async def get_org_policy(
    org_id: int = Query(..., ge=1),
    db=Depends(get_db_transaction),
) -> ConnectorPolicy:
    # In single-user mode, mimic multi-user but no enforcement beyond exposure
    pol = await get_policy(db, org_id)
    if not pol:
        pol = get_default_policy_from_env(org_id)
    return ConnectorPolicy(
        org_id=org_id,
        enabled_providers=[p for p in pol.get("enabled_providers") or [] if p],
        allowed_export_formats=[f for f in pol.get("allowed_export_formats") or [] if f],
        allowed_file_types=[t for t in pol.get("allowed_file_types") or [] if t],
        max_file_size_mb=int(pol.get("max_file_size_mb") or 0),
        account_linking_role=str(pol.get("account_linking_role") or "admin"),
        allowed_account_domains=[d for d in pol.get("allowed_account_domains") or [] if d],
        allowed_remote_paths=[p for p in pol.get("allowed_remote_paths") or [] if p],
        denied_remote_paths=[p for p in pol.get("denied_remote_paths") or [] if p],
        allowed_notion_workspaces=[w for w in pol.get("allowed_notion_workspaces") or [] if w],
        denied_notion_workspaces=[w for w in pol.get("denied_notion_workspaces") or [] if w],
        quotas_per_role=dict(pol.get("quotas_per_role") or {}),
    )


@router.put(
    "/admin/policy",
    response_model=ConnectorPolicy,
    dependencies=[
        Depends(get_auth_principal),
        Depends(require_roles("admin")),
        Depends(require_permissions(SYSTEM_CONFIGURE)),
    ],
)
async def upsert_org_policy(
    policy: ConnectorPolicy,
    db=Depends(get_db_transaction),
) -> ConnectorPolicy:
    # Enforce: only meaningful in multi-user mode; but persist anyway for forward usage
    p = policy.model_dump()
    saved = await upsert_policy(db, int(policy.org_id), p)
    return await get_org_policy(org_id=int(policy.org_id), db=db)
