"""ToolGate — approval interface between adapter and governance layer."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolGateResult:
    """Result of a tool approval request."""

    approved: bool
    reason: str | None = None


class ToolGate(ABC):
    """Abstract approval gate for tool execution.

    Implementations sit between the protocol adapter and the actual tool
    executor, allowing governance policies (human-in-the-loop, RBAC,
    budget limits, etc.) to approve or deny each tool call.
    """

    @abstractmethod
    async def request_approval(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolGateResult:
        """Block until governance decision. Returns approved/denied."""
