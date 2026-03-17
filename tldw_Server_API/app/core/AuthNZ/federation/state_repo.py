from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager


@dataclass
class FederationStateRepo:
    """Ephemeral repository for OIDC login state during browser callbacks."""

    session_manager: SessionManager
    key_prefix: str = "oidc-login"

    def _cache_key(self, state: str) -> str:
        return f"{self.key_prefix}:{state}"

    async def create_state(
        self,
        *,
        state: str,
        payload: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        await self.session_manager.store_ephemeral_value(
            self._cache_key(state),
            json.dumps(payload),
            ttl_seconds,
        )

    async def consume_state(
        self,
        *,
        state: str,
    ) -> dict[str, Any] | None:
        cache_key = self._cache_key(state)
        payload_raw = await self.session_manager.consume_ephemeral_value(cache_key)
        if not payload_raw:
            return None
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None
