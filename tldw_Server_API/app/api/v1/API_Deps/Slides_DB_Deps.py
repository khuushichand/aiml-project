"""FastAPI dependency for SlidesDatabase per user."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Slides.slides_db import SlidesDatabase, SlidesDatabaseError, SchemaError


_MAX_CACHED_SLIDES_DB = 20
_slides_db_lock = threading.Lock()
_slides_db_instances: Dict[str, SlidesDatabase] = {}


def _get_slides_db_path_for_user(user_id: int) -> Path:
    return DatabasePaths.get_slides_db_path(user_id)


async def get_slides_db_for_user(
    current_user: User = Depends(get_request_user),
) -> SlidesDatabase:
    if not current_user or current_user.id is None:
        logger.error("get_slides_db_for_user called without valid user")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User identification failed")
    user_id = int(current_user.id)
    db_key = str(user_id)
    with _slides_db_lock:
        db_instance = _slides_db_instances.get(db_key)
        if db_instance:
            return db_instance
        try:
            db_path = _get_slides_db_path_for_user(user_id)
            db_instance = SlidesDatabase(db_path=str(db_path), client_id=str(current_user.id))
            if len(_slides_db_instances) >= _MAX_CACHED_SLIDES_DB:
                _slides_db_instances.pop(next(iter(_slides_db_instances)))
            _slides_db_instances[db_key] = db_instance
            return db_instance
        except (SlidesDatabaseError, SchemaError) as exc:
            logger.error("Failed to initialize Slides DB for user %s: %s", user_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Slides DB unavailable",
            ) from exc
        except Exception as exc:
            logger.error("Unexpected Slides DB init failure for user %s: %s", user_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Slides DB unavailable",
            ) from exc


async def try_get_slides_db_for_user(
    current_user: User = Depends(get_request_user),
) -> Optional[SlidesDatabase]:
    try:
        return await get_slides_db_for_user(current_user=current_user)
    except HTTPException:
        return None
    except Exception:
        return None
