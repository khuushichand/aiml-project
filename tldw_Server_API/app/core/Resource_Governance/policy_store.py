from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, Tuple


class PolicyStore(Protocol):
    async def get_latest_policy(self) -> Tuple[int, Dict[str, Any], Dict[str, Any], float]:
        """
        Return (version, policies, tenant, updated_at_epoch_seconds).

        Implementations should retrieve the current policy snapshot from the
        AuthNZ database (or other SoT), using the most recent `updated_at`.
        """


@dataclass(frozen=True)
class PolicyRecord:
    id: str
    payload: Dict[str, Any]
    version: int
    updated_at: datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryPolicyStore:
    """Simple in-memory store, useful for tests and bootstrapping."""

    def __init__(self, version: int, policies: Dict[str, Any], tenant: Optional[Dict[str, Any]] = None) -> None:
        self._version = int(version)
        self._policies = dict(policies)
        self._tenant = dict(tenant or {})
        self._updated_at = utc_now().timestamp()

    async def get_latest_policy(self) -> Tuple[int, Dict[str, Any], Dict[str, Any], float]:
        return self._version, dict(self._policies), dict(self._tenant), float(self._updated_at)
