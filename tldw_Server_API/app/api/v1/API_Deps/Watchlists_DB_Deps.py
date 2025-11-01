"""
FastAPI dependencies for Watchlists database access (per-user Media DB).
"""

from fastapi import Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase


async def get_watchlists_db_for_user(
    current_user: User = Depends(get_request_user)
) -> WatchlistsDatabase:
    if not current_user or current_user.id is None:
        logger.error("get_watchlists_db_for_user called without a valid User")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User identification failed")
    try:
        db = WatchlistsDatabase.for_user(user_id=current_user.id)
        # Defensive: ensure schema exists for this user's DB in test/minimal app contexts
        try:
            db.ensure_schema()
        except Exception:
            # Best-effort; creation may have already occurred or be gated by init
            pass
        return db
    except Exception as e:
        logger.error(f"Failed to init Watchlists DB for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Watchlists DB unavailable")
