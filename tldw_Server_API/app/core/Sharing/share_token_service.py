"""Service for creating, validating, and revoking share tokens."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any

import bcrypt

from tldw_Server_API.app.core.AuthNZ.repos.shared_workspace_repo import SharedWorkspaceRepo


class ShareTokenService:
    """Manages token-based sharing links with expiry, password, and use limits."""

    def __init__(self, repo: SharedWorkspaceRepo) -> None:
        self._repo = repo

    async def generate_token(
        self,
        *,
        resource_type: str,
        resource_id: str,
        owner_user_id: int,
        access_level: str = "view_chat",
        allow_clone: bool = True,
        password: str | None = None,
        max_uses: int | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token_prefix = raw_token[:8]

        password_hash: str | None = None
        if password:
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")

        record = await self._repo.create_token(
            token_hash=token_hash,
            token_prefix=token_prefix,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            access_level=access_level,
            allow_clone=allow_clone,
            password_hash=password_hash,
            max_uses=max_uses,
            expires_at=expires_at,
        )

        # Return raw token only once — never stored server-side
        record["raw_token"] = raw_token
        return record

    async def validate_token(self, raw_token: str) -> dict[str, Any] | None:
        prefix = raw_token[:8]
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        candidates = await self._repo.find_tokens_by_prefix(prefix)
        if not candidates:
            return None

        for candidate in candidates:
            stored_hash = candidate.get("token_hash", "")
            if not hmac.compare_digest(token_hash, stored_hash):
                continue

            # Defense-in-depth: check revocation even though SQL filters it
            if candidate.get("is_revoked") or candidate.get("revoked_at"):
                return None

            # Check expiry
            expires_at = candidate.get("expires_at")
            if expires_at:
                if isinstance(expires_at, str):
                    try:
                        exp_dt = datetime.fromisoformat(expires_at)
                    except ValueError:
                        return None
                else:
                    exp_dt = expires_at
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt < datetime.now(timezone.utc):
                    return None

            # Check use count
            max_uses = candidate.get("max_uses")
            if max_uses is not None and candidate.get("use_count", 0) >= max_uses:
                return None

            return candidate

        return None

    async def verify_password(self, token_record: dict[str, Any], password: str) -> bool:
        stored_hash = token_record.get("password_hash")
        if not stored_hash:
            return True  # No password required
        return bcrypt.checkpw(
            password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )

    async def use_token(self, token_id: int) -> None:
        await self._repo.increment_token_use_count(token_id)

    async def revoke_token(self, token_id: int) -> bool:
        return await self._repo.revoke_token(token_id)

    async def list_tokens(self, owner_user_id: int) -> list[dict[str, Any]]:
        tokens = await self._repo.list_tokens_for_user(owner_user_id)
        # Strip sensitive fields
        for t in tokens:
            t.pop("token_hash", None)
            t.pop("password_hash", None)
        return tokens

    async def revoke_tokens_for_resource(
        self, resource_type: str, resource_id: str, owner_user_id: int
    ) -> int:
        return await self._repo.revoke_tokens_for_resource(
            resource_type, resource_id, owner_user_id
        )
