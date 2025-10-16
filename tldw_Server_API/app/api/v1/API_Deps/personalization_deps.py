"""
Personalization dependencies: per-user DB access and event logger.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Depends, Request
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Personalization_DB import (
    PersonalizationDB,
    UsageEvent,
)


def get_personalization_db_for_user(user: User = Depends(get_request_user)) -> PersonalizationDB:
    """Return a PersonalizationDB instance bound to the current user's DB path."""
    # Accept both numeric and string IDs in tests/single-user flows
    try:
        uid = int(user.id)
    except Exception:
        # Derive a stable numeric from string id (e.g., "test_user")
        try:
            import hashlib
            digest = hashlib.sha1(str(user.id).encode("utf-8")).digest()
            uid = int.from_bytes(digest[:4], byteorder="big", signed=False)
        except Exception:
            uid = 0
    db_path = DatabasePaths.get_personalization_db_path(uid)
    return PersonalizationDB(str(db_path))


@dataclass
class UsageEventLogger:
    user_id: str
    db: PersonalizationDB

    def log_event(
        self,
        event_type: str,
        resource_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        try:
            evt = UsageEvent(user_id=self.user_id, type=event_type, resource_id=resource_id, tags=tags, metadata=metadata)
            return self.db.insert_usage_event(evt)
        except Exception as e:
            logger.debug(f"UsageEventLogger failed (non-fatal): {e}")
            return None


def get_usage_event_logger(
    request: Request,
    user: User = Depends(get_request_user),
    db: PersonalizationDB = Depends(get_personalization_db_for_user),
) -> UsageEventLogger:
    return UsageEventLogger(user_id=str(user.id), db=db)
