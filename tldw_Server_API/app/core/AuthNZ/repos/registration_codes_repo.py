from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


    @dataclass
class AuthnzRegistrationCodesRepo:
    """
    Repository for AuthNZ registration code maintenance.

    This helper currently owns the small cross-backend cleanup used by the
    AuthNZ scheduler to deactivate expired registration codes, so the
    scheduler no longer embeds dialect-specific SQL.
    """

    db_pool: DatabasePool

    async def deactivate_expired_codes(self, cutoff: datetime) -> int:
        """
        Deactivate registration codes whose ``expires_at`` is in the past.

        Returns:
            Best-effort count of rows updated.
        """
        try:
            async with self.db_pool.transaction() as conn:
                updated = 0
                if hasattr(conn, "fetchrow"):
                    result = await conn.execute(
                        """
                        UPDATE registration_codes
                        SET is_active = FALSE
                        WHERE is_active = TRUE
                          AND expires_at < $1
                        """,
                        cutoff,
                    )
                    if isinstance(result, str):
                        try:
                            updated = int(result.split()[-1])
                        except (ValueError, IndexError):
                            updated = 0
                else:
                    cursor = await conn.execute(
                        """
                        UPDATE registration_codes
                        SET is_active = 0
                        WHERE is_active = 1
                          AND expires_at < ?
                        """,
                        (cutoff.isoformat(),),
                    )
                    updated = getattr(cursor, "rowcount", 0) or 0
                return int(updated or 0)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                "AuthnzRegistrationCodesRepo.deactivate_expired_codes failed: %s",
                exc,
            )
            raise
