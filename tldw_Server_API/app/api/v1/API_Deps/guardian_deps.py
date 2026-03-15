"""
Guardian & Self-Monitoring dependencies: per-user DB access.
"""
from __future__ import annotations

from fastapi import Depends

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB


def _coerce_storage_user_id(raw_user_id: object) -> int:
    try:
        return int(raw_user_id)
    except Exception:
        import hashlib
        # Deterministic non-crypto ID derivation for non-integer test/single-user IDs.
        # Use SHA-256 to avoid weak-hash false positives.
        digest = hashlib.sha256(str(raw_user_id).encode("utf-8")).digest()
        return int.from_bytes(digest[:4], byteorder="big", signed=False)


def get_guardian_db_for_user_id(user_id: object) -> GuardianDB:
    """Return a GuardianDB instance bound to the provided user ID."""
    uid = _coerce_storage_user_id(user_id)
    db_path = DatabasePaths.get_guardian_db_path(uid)
    return GuardianDB(str(db_path))


def get_guardian_db_for_user(user: User = Depends(get_request_user)) -> GuardianDB:
    """Return a GuardianDB instance bound to the current user's DB path."""
    return get_guardian_db_for_user_id(user.id)
