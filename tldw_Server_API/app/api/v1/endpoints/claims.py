from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.claims_rebuild_service import get_claims_rebuild_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/{media_id}")
def list_claims(media_id: int, limit: int = Query(100, ge=1, le=1000)) -> List[Dict[str, Any]]:
    try:
        # In server mode, you'd inject a DB path; here we use default Users DB path helper if available
        from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
        from tldw_Server_API.app.core.config import settings
        user_id = int(settings.get("SINGLE_USER_FIXED_ID", "1"))
        db_path = get_user_media_db_path(user_id)
        db = MediaDatabase(db_path=db_path, client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")))
        claims = db.get_claims_by_media(media_id, limit=limit)
        db.close_connection()
        return claims
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{media_id}/rebuild")
def rebuild_claims(media_id: int) -> Dict[str, Any]:
    try:
        from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
        from tldw_Server_API.app.core.config import settings
        user_id = int(settings.get("SINGLE_USER_FIXED_ID", "1"))
        db_path = get_user_media_db_path(user_id)
        svc = get_claims_rebuild_service()
        svc.submit(media_id=media_id, db_path=db_path)
        return {"status": "accepted", "media_id": media_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
