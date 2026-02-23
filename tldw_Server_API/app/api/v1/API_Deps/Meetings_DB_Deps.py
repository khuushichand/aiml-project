"""FastAPI dependencies for Meetings database access (per-user Media DB)."""

from fastapi import Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase


async def get_meetings_db_for_user(
    current_user: User = Depends(get_request_user),
) -> MeetingsDatabase:
    if not current_user or current_user.id is None:
        logger.error("get_meetings_db_for_user called without a valid User")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User identification failed",
        )
    try:
        return MeetingsDatabase.for_user(user_id=current_user.id)
    except Exception as exc:
        logger.error(f"Failed to init Meetings DB for user {current_user.id}: {exc}")
        raise HTTPException(status_code=500, detail="Meetings DB unavailable") from exc
