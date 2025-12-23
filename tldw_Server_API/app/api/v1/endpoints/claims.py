from fastapi import APIRouter, HTTPException, Query, Depends, Request, status
from typing import Dict, Any, Optional

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.Claims_Extraction.claims_rebuild_service import get_claims_rebuild_service
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    require_roles,
    require_permissions,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo
from tldw_Server_API.app.core.Setup import setup_manager
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.api.v1.schemas.claims_schemas import (
    ClaimsSettingsResponse,
    ClaimsSettingsUpdate,
    ClaimUpdateRequest,
)

router = APIRouter(prefix="/claims", tags=["claims"])

_ROLE_HIERARCHY = {
    "owner": 4,
    "admin": 3,
    "lead": 2,
    "member": 1,
}
_ACTIVE_MEMBERSHIP_STATUSES = {"active"}


def _role_at_least(user_role: str, required_role: str) -> bool:
    user_level = _ROLE_HIERARCHY.get(str(user_role).lower(), 0)
    required_level = _ROLE_HIERARCHY.get(str(required_role).lower(), 0)
    return user_level >= required_level


def _is_membership_active(membership: Optional[dict]) -> bool:
    if not membership:
        return False
    status_val = membership.get("status")
    if status_val is None:
        return False
    return str(status_val).strip().lower() in _ACTIVE_MEMBERSHIP_STATUSES


def _normalize_claim_row(row: Dict[str, Any]) -> Dict[str, Any]:
    row.pop("media_owner_user_id", None)
    row.pop("media_client_id", None)
    return row


def _claims_settings_snapshot() -> ClaimsSettingsResponse:
    return ClaimsSettingsResponse(
        enable_ingestion_claims=bool(settings.get("ENABLE_INGESTION_CLAIMS", False)),
        claim_extractor_mode=str(settings.get("CLAIM_EXTRACTOR_MODE", "heuristic")),
        claims_max_per_chunk=int(settings.get("CLAIMS_MAX_PER_CHUNK", 3)),
        claims_embed=bool(settings.get("CLAIMS_EMBED", False)),
        claims_embed_model_id=str(settings.get("CLAIMS_EMBED_MODEL_ID", "")),
        claims_llm_provider=str(settings.get("CLAIMS_LLM_PROVIDER", "")),
        claims_llm_temperature=float(settings.get("CLAIMS_LLM_TEMPERATURE", 0.1)),
        claims_llm_model=str(settings.get("CLAIMS_LLM_MODEL", "")),
        claims_rebuild_enabled=bool(settings.get("CLAIMS_REBUILD_ENABLED", False)),
        claims_rebuild_interval_sec=int(settings.get("CLAIMS_REBUILD_INTERVAL_SEC", 3600)),
        claims_rebuild_policy=str(settings.get("CLAIMS_REBUILD_POLICY", "missing")),
        claims_stale_days=int(settings.get("CLAIMS_STALE_DAYS", 7)),
    )


async def _ensure_claim_edit_access(
    *,
    principal: AuthPrincipal,
    claim_row: Dict[str, Any],
) -> None:
    if principal.is_admin:
        return

    visibility = str(claim_row.get("media_visibility") or "personal").lower()
    owner_user_id = claim_row.get("media_owner_user_id")
    media_client_id = claim_row.get("media_client_id")
    if visibility == "personal":
        try:
            if owner_user_id is not None and int(owner_user_id) == int(principal.user_id):
                return
        except Exception:
            pass
        if media_client_id is not None and str(media_client_id) == str(principal.user_id):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    org_id = claim_row.get("media_org_id")
    team_id = claim_row.get("media_team_id")
    db_pool = await get_db_pool()
    repo = AuthnzOrgsTeamsRepo(db_pool=db_pool)

    if visibility == "org":
        if org_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        membership = await repo.get_org_member(int(org_id), int(principal.user_id))
        if not _is_membership_active(membership):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        role = str(membership.get("role", "member"))
        if _role_at_least(role, "admin"):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    if visibility == "team":
        if team_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")
        org_membership = None
        if org_id is not None:
            org_membership = await repo.get_org_member(int(org_id), int(principal.user_id))
        if _is_membership_active(org_membership):
            org_role = str(org_membership.get("role", "member"))
            if _role_at_least(org_role, "admin"):
                return
        team_membership = await repo.get_team_member(int(team_id), int(principal.user_id))
        if _is_membership_active(team_membership):
            team_role = str(team_membership.get("role", "member"))
            if _role_at_least(team_role, "lead"):
                return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit claim")


@router.get("/status")
def claims_rebuild_status(
    _principal: AuthPrincipal = Depends(require_roles("admin")),  # admin role enforced via dependency; value unused  # noqa: B008
) -> Dict[str, Any]:
    """Return statistics about the claims rebuild worker. Admin only."""
    try:
        svc = get_claims_rebuild_service()
        try:
            stats = svc.get_stats()
        except Exception:
            stats = {}
        try:
            qlen = svc.get_queue_length()
        except Exception:
            qlen = 0
        try:
            workers = svc.get_worker_count()
        except Exception:
            workers = None
        return {"status": "ok", "stats": stats, "queue_length": qlen, "workers": workers}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_all_claims(
    media_id: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=100000),
    include_deleted: bool = Query(False),
    user_id: Optional[int] = None,
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> list[Dict[str, Any]]:
    """List claims across accessible media for the current user."""
    try:
        override_db: Optional[MediaDatabase] = None
        owner_filter: Optional[int] = None
        try:
            if user_id is not None:
                if not getattr(current_user, "is_admin", False):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
                if db.backend_type == BackendType.POSTGRESQL:
                    owner_filter = int(user_id)
                    target_db = db
                else:
                    db_path = get_user_media_db_path(int(user_id))
                    override_db = MediaDatabase(
                        db_path=db_path,
                        client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                    )
                    target_db = override_db
            else:
                target_db = db

            claims = target_db.list_claims(
                media_id=media_id,
                owner_user_id=owner_filter,
                limit=limit,
                offset=offset,
                include_deleted=include_deleted,
            )
            return [_normalize_claim_row(dict(row)) for row in claims]
        finally:
            if override_db is not None:
                try:
                    override_db.close_connection()
                except Exception:
                    pass
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings", response_model=ClaimsSettingsResponse)
def get_claims_settings(
    _principal: AuthPrincipal = Depends(require_roles("admin")),  # admin only
) -> ClaimsSettingsResponse:
    """Return current claims settings."""
    try:
        return _claims_settings_snapshot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings", response_model=ClaimsSettingsResponse)
def update_claims_settings(
    payload: ClaimsSettingsUpdate,
    _principal: AuthPrincipal = Depends(require_roles("admin")),
    _perm: AuthPrincipal = Depends(require_permissions(SYSTEM_CONFIGURE)),
) -> ClaimsSettingsResponse:
    """Update claims settings (optionally persisted)."""
    updates: Dict[str, Any] = {}
    if payload.enable_ingestion_claims is not None:
        updates["ENABLE_INGESTION_CLAIMS"] = bool(payload.enable_ingestion_claims)
    if payload.claim_extractor_mode is not None:
        updates["CLAIM_EXTRACTOR_MODE"] = str(payload.claim_extractor_mode).strip()
    if payload.claims_max_per_chunk is not None:
        updates["CLAIMS_MAX_PER_CHUNK"] = int(payload.claims_max_per_chunk)
    if payload.claims_embed is not None:
        updates["CLAIMS_EMBED"] = bool(payload.claims_embed)
    if payload.claims_embed_model_id is not None:
        updates["CLAIMS_EMBED_MODEL_ID"] = str(payload.claims_embed_model_id)
    if payload.claims_llm_provider is not None:
        updates["CLAIMS_LLM_PROVIDER"] = str(payload.claims_llm_provider)
    if payload.claims_llm_temperature is not None:
        updates["CLAIMS_LLM_TEMPERATURE"] = float(payload.claims_llm_temperature)
    if payload.claims_llm_model is not None:
        updates["CLAIMS_LLM_MODEL"] = str(payload.claims_llm_model)
    if payload.claims_rebuild_enabled is not None:
        updates["CLAIMS_REBUILD_ENABLED"] = bool(payload.claims_rebuild_enabled)
    if payload.claims_rebuild_interval_sec is not None:
        updates["CLAIMS_REBUILD_INTERVAL_SEC"] = int(payload.claims_rebuild_interval_sec)
    if payload.claims_rebuild_policy is not None:
        updates["CLAIMS_REBUILD_POLICY"] = str(payload.claims_rebuild_policy)
    if payload.claims_stale_days is not None:
        updates["CLAIMS_STALE_DAYS"] = int(payload.claims_stale_days)

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")

    for key, value in updates.items():
        settings[key] = value

    if payload.persist:
        try:
            setup_manager.update_config({"Claims": updates})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return _claims_settings_snapshot()


# envelope: if true, return {items: [...], next_offset: int|None}
@router.get("/{media_id}")
def list_claims(
    media_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=100000),
    envelope: bool = Query(False),
    absolute_links: bool = Query(False),
    user_id: Optional[int] = None,
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
    request: Request = None,
) -> Any:
    try:
        # Admin can override user_id (use a temporary DB instance only in this case)
        override_db: Optional[MediaDatabase] = None
        try:
            if user_id is not None:
                if not getattr(current_user, 'is_admin', False):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
                if db.backend_type == BackendType.POSTGRESQL:
                    target_db = db
                else:
                    db_path = get_user_media_db_path(int(user_id))
                    override_db = MediaDatabase(
                        db_path=db_path,
                        client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                    )
                    target_db = override_db
            else:
                target_db = db
            claims = target_db.get_claims_by_media(media_id, limit=limit, offset=offset)
            if envelope:
                # Total count for pagination
                try:
                    cur = target_db.execute_query(
                        "SELECT COUNT(*) AS c FROM Claims WHERE media_id = ? AND deleted = 0",
                        (media_id,),
                    )
                    row = cur.fetchone()
                    total = int(row[0]) if row else 0
                except Exception:
                    total = offset + len(claims)
                next_off: Optional[int] = None
                if offset + len(claims) < total:
                    next_off = offset + len(claims)
                # Build simple next link (relative/absolute), preserving user_id if present
                next_link: Optional[str] = None
                if next_off is not None:
                    if request and absolute_links:
                        base = f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
                    else:
                        base = request.url.path if request else f"/api/v1/claims/{media_id}"
                    params = f"limit={limit}&offset={next_off}&envelope=true"
                    if user_id is not None and getattr(current_user, 'is_admin', False):
                        params += f"&user_id={int(user_id)}"
                    if absolute_links:
                        params += "&absolute_links=true"
                    next_link = f"{base}?{params}"
                total_pages = int((total + int(limit) - 1) // int(limit)) if int(limit) > 0 else 0
                return {"items": claims, "next_offset": next_off, "total": total, "total_pages": total_pages, "next_link": next_link}  # type: ignore[return-value]
        finally:
            # Only close the temporary override DB we created here; never close DI-provided instance
            if override_db is not None:
                try:
                    override_db.close_connection()
                except Exception:
                    pass
        return claims
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/{claim_id}")
def get_claim_item(
    claim_id: int,
    include_deleted: bool = Query(False),
    user_id: Optional[int] = None,
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> Dict[str, Any]:
    """Fetch a single claim by id."""
    try:
        override_db: Optional[MediaDatabase] = None
        try:
            if user_id is not None:
                if not getattr(current_user, "is_admin", False):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
                if db.backend_type == BackendType.POSTGRESQL:
                    target_db = db
                else:
                    db_path = get_user_media_db_path(int(user_id))
                    override_db = MediaDatabase(
                        db_path=db_path,
                        client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                    )
                    target_db = override_db
            else:
                target_db = db

            row = target_db.get_claim_with_media(int(claim_id), include_deleted=include_deleted)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
            return _normalize_claim_row(dict(row))
        finally:
            if override_db is not None:
                try:
                    override_db.close_connection()
                except Exception:
                    pass
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/items/{claim_id}")
async def update_claim_item(
    claim_id: int,
    payload: ClaimUpdateRequest,
    user_id: Optional[int] = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> Dict[str, Any]:
    """Update a claim entry."""
    try:
        override_db: Optional[MediaDatabase] = None
        try:
            if user_id is not None:
                if not getattr(current_user, "is_admin", False):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
                if db.backend_type == BackendType.POSTGRESQL:
                    target_db = db
                else:
                    db_path = get_user_media_db_path(int(user_id))
                    override_db = MediaDatabase(
                        db_path=db_path,
                        client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                    )
                    target_db = override_db
            else:
                target_db = db

            claim_row = target_db.get_claim_with_media(int(claim_id), include_deleted=True)
            if not claim_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

            await _ensure_claim_edit_access(principal=principal, claim_row=claim_row)

            updated = target_db.update_claim(
                int(claim_id),
                claim_text=payload.claim_text,
                span_start=payload.span_start,
                span_end=payload.span_end,
                confidence=payload.confidence,
                extractor=payload.extractor,
                extractor_version=payload.extractor_version,
                deleted=payload.deleted,
            )
            if not updated:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
            return _normalize_claim_row(dict(updated))
        finally:
            if override_db is not None:
                try:
                    override_db.close_connection()
                except Exception:
                    pass
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{media_id}/rebuild")
def rebuild_claims(
    media_id: int,
    user_id: Optional[int] = None,
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> Dict[str, Any]:
    try:
        # Resolve db_path for current user or admin override
        if user_id is not None and getattr(current_user, 'is_admin', False):
            db_path = get_user_media_db_path(int(user_id))
        else:
            db_path = db.db_path_str
        svc = get_claims_rebuild_service()
        svc.submit(media_id=media_id, db_path=db_path)
        return {"status": "accepted", "media_id": media_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild/all")
def rebuild_all_media(
    policy: str = "missing",
    user_id: Optional[int] = None,
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> Dict[str, Any]:
    """
    Enqueue rebuild tasks for all media for the current user based on policy:
    - missing: media with no non-deleted claims
    - all: all media
    - stale: media where MAX(Claims.last_modified) < Media.last_modified
    """
    try:
        override_db: Optional[MediaDatabase] = None
        try:
            if user_id is not None and getattr(current_user, 'is_admin', False):
                db_path = get_user_media_db_path(int(user_id))
                override_db = MediaDatabase(
                    db_path=db_path,
                    client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                )
                query_db = override_db
            else:
                db_path = db.db_path_str
                query_db = db

            svc = get_claims_rebuild_service()

            policy = str(policy or "missing").lower()
            if policy == "all":
                sql = "SELECT id FROM Media WHERE deleted=0 AND is_trash=0"
                rows = query_db.execute_query(sql).fetchall()
            elif policy == "stale":
                sql = (
                    "SELECT m.id FROM Media m "
                    "LEFT JOIN (SELECT media_id, MAX(last_modified) AS lastc FROM Claims WHERE deleted=0 GROUP BY media_id) c ON c.media_id = m.id "
                    "WHERE m.deleted=0 AND m.is_trash=0 AND (c.lastc IS NULL OR c.lastc < m.last_modified)"
                )
                rows = query_db.execute_query(sql).fetchall()
            else:  # missing
                sql = (
                    "SELECT m.id FROM Media m "
                    "WHERE m.deleted = 0 AND m.is_trash = 0 AND NOT EXISTS ("
                    "  SELECT 1 FROM Claims c WHERE c.media_id = m.id AND c.deleted = 0"
                    ")"
                )
                rows = query_db.execute_query(sql).fetchall()
            # Support both dict-shaped rows and sequence rows
            mids: list[int] = []
            for r in rows:
                try:
                    mids.append(int(r["id"]))  # type: ignore[index]
                except Exception:
                    try:
                        mids.append(int(r[0]))  # type: ignore[index]
                    except Exception:
                        # Fallback: first value in row mapping/sequence
                        try:
                            if isinstance(r, dict):
                                first_val = next(iter(r.values()))
                                mids.append(int(first_val))
                            else:
                                # Attempt generic indexing
                                mids.append(int(r[0]))  # type: ignore[index]
                        except Exception:
                            continue
            for mid in mids:
                svc.submit(media_id=mid, db_path=db_path)
            return {"status": "accepted", "enqueued": len(mids), "policy": policy}
        finally:
            if override_db is not None:
                try:
                    override_db.close_connection()
                except Exception:
                    pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild_fts")
def rebuild_claims_fts(
    user_id: Optional[int] = None,
    current_user: User = Depends(get_request_user),  # noqa: B008
    db: MediaDatabase = Depends(get_media_db_for_user),  # noqa: B008
) -> Dict[str, Any]:
    """Rebuild claims_fts index from Claims content."""
    try:
        override_db: Optional[MediaDatabase] = None
        try:
            if user_id is not None and getattr(current_user, 'is_admin', False):
                db_path = get_user_media_db_path(int(user_id))
                override_db = MediaDatabase(
                    db_path=db_path,
                    client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                )
                count = override_db.rebuild_claims_fts()
            else:
                count = db.rebuild_claims_fts()
        finally:
            if override_db is not None:
                try:
                    override_db.close_connection()
                except Exception:
                    pass
        return {"status": "ok", "indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
