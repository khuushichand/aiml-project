"""
Guardian & Self-Monitoring dependencies: per-user DB access.
"""
from __future__ import annotations

from fastapi import Depends

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB


def get_guardian_db_for_user(user: User = Depends(get_request_user)) -> GuardianDB:
    """Return a GuardianDB instance bound to the current user's DB path."""
    try:
        uid = int(user.id)
    except Exception:
        import hashlib
        digest = hashlib.sha1(str(user.id).encode("utf-8")).digest()
        uid = int.from_bytes(digest[:4], byteorder="big", signed=False)
    db_path = DatabasePaths.get_guardian_db_path(uid)
    return GuardianDB(str(db_path))
