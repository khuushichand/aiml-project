"""
Guardian DB resolution helpers shared by core and API layers.
"""
from __future__ import annotations

import hashlib

from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def coerce_guardian_storage_user_id(raw_user_id: object) -> int:
    """Normalize user IDs to the integer storage key used for guardian DB paths."""
    try:
        return int(raw_user_id)
    except Exception:
        digest = hashlib.sha256(str(raw_user_id).encode("utf-8")).digest()
        return int.from_bytes(digest[:4], byteorder="big", signed=False)


def resolve_guardian_db_for_user_id(user_id: object) -> GuardianDB:
    """Return a GuardianDB instance bound to the provided user ID."""
    storage_user_id = coerce_guardian_storage_user_id(user_id)
    db_path = DatabasePaths.get_guardian_db_path(storage_user_id)
    return GuardianDB(str(db_path))
