from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.connectors import (
    ConnectorProvider,
    ConnectorAccount,
    ConnectorSource,
    SyncOptions,
    ImportJob,
    AuthorizeURLResponse,
    ConnectorPolicy,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_current_active_user,
    require_admin,
    get_db_transaction,
)
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode
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
    count_connectors_jobs_today,
)
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, ensure_traceparent, get_ps_logger


router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("/providers", response_model=List[ConnectorProvider])
async def list_providers() -> List[ConnectorProvider]:
    return [
        ConnectorProvider(name="drive", scopes_required=["drive.readonly"], auth_type="oauth2"),
        ConnectorProvider(name="notion", scopes_required=[], auth_type="oauth2"),
    ]


@router.post("/providers/{provider}/authorize", response_model=AuthorizeURLResponse)
async def start_authorize(provider: str, state: Optional[str] = None, scopes: Optional[str] = None) -> AuthorizeURLResponse:
    conn = get_connector_by_name(provider)
    scopes_list = [s for s in (scopes or "").split(",") if s]
    url = conn.authorize_url(state=state, scopes=scopes_list or None, redirect_path=f"/api/v1/connectors/providers/{provider}/callback")
    return AuthorizeURLResponse(auth_url=url, state=state)


@router.get("/providers/{provider}/callback", response_model=ConnectorAccount)
async def oauth_callback(
    provider: str,
    code: str,
    state: Optional[str] = None,
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> ConnectorAccount:
    conn = get_connector_by_name(provider)
    # Enforce org-level account linking role only in multi-user mode
    if not is_single_user_mode():
        try:
            memberships = current_user.get("org_memberships") or []
            # pick active org or first membership
            org_id = memberships[0]["org_id"] if memberships else 1
            pol = await get_policy(db, org_id)
            if not pol:
                pol = get_default_policy_from_env(org_id)
            role = str(current_user.get("role", "member")).lower()
            required = str(pol.get("account_linking_role", "admin")).lower()
            # Admin bypass
            if role != "admin" and required and role != required:
                raise HTTPException(status_code=403, detail="Account linking not permitted for your role")
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Policy enforcement error on callback: {e}")

    # Exchange code with redirect derived from env base + this path
    import os as _os
    base = _os.getenv("CONNECTOR_REDIRECT_BASE_URL")
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
    # Enforce additional org policy constraints at callback in multi-user mode
    if not is_single_user_mode():
        try:
            memberships = current_user.get("org_memberships") or []
            org_id = memberships[0]["org_id"] if memberships else 1
            pol = await get_policy(db, org_id)
            if not pol:
                pol = get_default_policy_from_env(org_id)
            ok, why = evaluate_policy_constraints(
                pol,
                provider=provider,
                remote_path=None,
                notion_workspace_id=notion_workspace_id,
                account_email=acct_email,
            )
            if not ok:
                raise HTTPException(status_code=403, detail=why or "Account not permitted by org policy")
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Callback constraint evaluation failed: {e}")

    acct = await create_account(
        db,
        user_id=int(current_user.get("id")),
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
    rows = await list_accounts(db, int(current_user.get("id")))
    return [ConnectorAccount(id=int(r["id"]), provider=r["provider"], display_name=r.get("display_name") or "", email=r.get("email"), created_at=str(r.get("created_at")), connected=True) for r in rows]


@router.delete("/accounts/{account_id}")
async def remove_account(
    account_id: int, db=Depends(get_db_transaction), current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    await delete_account(db, int(current_user.get("id")), account_id)
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
    tokens = await get_account_tokens(db, int(current_user.get("id")), account_id)
    if not tokens:
        raise HTTPException(status_code=404, detail="Account not found")
    email = await get_account_email(db, int(current_user.get("id")), account_id)
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
    payload: Dict[str, Any],
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> ConnectorSource:
    # payload keys: account_id, provider, remote_id, type, path, options
    account_id = int(payload.get("account_id"))
    provider = str(payload.get("provider"))
    remote_id = str(payload.get("remote_id"))
    type_ = str(payload.get("type"))
    path = payload.get("path")
    options = payload.get("options") or {}

    # Enforce org policy on provider/path only in multi-user mode
    if not is_single_user_mode():
        try:
            memberships = current_user.get("org_memberships") or []
            org_id = memberships[0]["org_id"] if memberships else 1
            pol = await get_policy(db, org_id)
            if not pol:
                pol = get_default_policy_from_env(org_id)
            ok, why = evaluate_policy_constraints(pol, provider=provider, remote_path=path)
            if not ok:
                raise HTTPException(status_code=403, detail=why or "Source denied by org policy")
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Policy evaluation failed: {e}")

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
    rows = await list_sources(db, int(current_user.get("id")))
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
    payload: Dict[str, Any],
    db=Depends(get_db_transaction),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> ConnectorSource:
    enabled = payload.get("enabled")
    options = payload.get("options")
    row = await update_source(db, int(current_user.get("id")), source_id, enabled=enabled, options=options)
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
) -> ImportJob:
    # Enforce per-role daily quota from org policy (multi-user only)
    if not is_single_user_mode():
        try:
            role = str(current_user.get("role", "member")).lower()
            memberships = current_user.get("org_memberships") or []
            org_id = memberships[0]["org_id"] if memberships else 1
            pol = await get_policy(db, org_id)
            if not pol:
                pol = get_default_policy_from_env(org_id)
            qpr = pol.get("quotas_per_role") or {}
            limits = qpr.get(role) or {}
            max_jobs = int(limits.get("max_jobs_per_day") or 0)
            if max_jobs > 0:
                today_count = count_connectors_jobs_today(int(current_user.get("id")))
                if today_count >= max_jobs:
                    raise HTTPException(status_code=429, detail="Daily import quota reached for your role")
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"Quota check error: {e}")
    # Correlate request → job
    rid = ensure_request_id(request) if request is not None else None
    tp = ensure_traceparent(request) if request is not None else ""
    job = await create_import_job(int(current_user.get("id")), source_id, request_id=rid)
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
@router.get("/admin/policy", response_model=ConnectorPolicy, dependencies=[Depends(require_admin)])
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


@router.put("/admin/policy", response_model=ConnectorPolicy, dependencies=[Depends(require_admin)])
async def upsert_org_policy(
    policy: ConnectorPolicy,
    db=Depends(get_db_transaction),
) -> ConnectorPolicy:
    # Enforce: only meaningful in multi-user mode; but persist anyway for forward usage
    p = policy.model_dump()
    saved = await upsert_policy(db, int(policy.org_id), p)
    return await get_org_policy(org_id=int(policy.org_id), db=db)
