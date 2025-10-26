from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import List, Dict, Any, Optional

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.claims_rebuild_service import get_claims_rebuild_service
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.config import settings

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/status")
def claims_rebuild_status(
    current_user: User = Depends(get_request_user),
) -> Dict[str, Any]:
    """Return statistics about the claims rebuild worker. Admin only."""
    try:
        if not getattr(current_user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Admin privileges required")
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
            if user_id is not None and getattr(current_user, 'is_admin', False):
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
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
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
