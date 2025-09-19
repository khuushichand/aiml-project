from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.claims_rebuild_service import get_claims_rebuild_service
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.config import settings

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/{media_id}")
def list_claims(
    media_id: int,
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = None,
    current_user: User = Depends(get_request_user),
    db: MediaDatabase = Depends(get_media_db_for_user),
) -> List[Dict[str, Any]]:
    try:
        # Admin can override user_id
        if user_id is not None and getattr(current_user, 'is_admin', False):
            db_path = get_user_media_db_path(int(user_id))
            db = MediaDatabase(db_path=db_path, client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")))
        claims = db.get_claims_by_media(media_id, limit=limit)
        try:
            db.close_connection()
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
        if user_id is not None and getattr(current_user, 'is_admin', False):
            db_path = get_user_media_db_path(int(user_id))
            db = MediaDatabase(db_path=db_path, client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")))
        else:
            db_path = db.db_path_str
        svc = get_claims_rebuild_service()

        policy = str(policy or "missing").lower()
        if policy == "all":
            sql = "SELECT id FROM Media WHERE deleted=0 AND is_trash=0"
            rows = db.execute_query(sql).fetchall()
        elif policy == "stale":
            sql = (
                "SELECT m.id FROM Media m "
                "LEFT JOIN (SELECT media_id, MAX(last_modified) AS lastc FROM Claims WHERE deleted=0 GROUP BY media_id) c ON c.media_id = m.id "
                "WHERE m.deleted=0 AND m.is_trash=0 AND (c.lastc IS NULL OR c.lastc < m.last_modified)"
            )
            rows = db.execute_query(sql).fetchall()
        else:  # missing
            sql = (
                "SELECT m.id FROM Media m "
                "WHERE m.deleted = 0 AND m.is_trash = 0 AND NOT EXISTS ("
                "  SELECT 1 FROM Claims c WHERE c.media_id = m.id AND c.deleted = 0"
                ")"
            )
            rows = db.execute_query(sql).fetchall()
        mids = [int(r[0]) for r in rows]
        for mid in mids:
            svc.submit(media_id=mid, db_path=db_path)
        try:
            db.close_connection()
        except Exception:
            pass
        return {"status": "accepted", "enqueued": len(mids), "policy": policy}
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
        if user_id is not None and getattr(current_user, 'is_admin', False):
            db_path = get_user_media_db_path(int(user_id))
            db = MediaDatabase(db_path=db_path, client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")))
            count = db.rebuild_claims_fts()
            try:
                db.close_connection()
            except Exception:
                pass
        else:
            count = db.rebuild_claims_fts()
        return {"status": "ok", "indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
