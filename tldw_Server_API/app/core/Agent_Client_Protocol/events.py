"""AgentEvent schema -- the core contract for the agent workspace harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentEventKind(str, Enum):
    """All event types in the agent event stream."""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_CHANGE = "file_change"
    TERMINAL_OUTPUT = "terminal_output"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_RESPONSE = "permission_response"
    COMPLETION = "completion"
    ERROR = "error"
    STATUS_CHANGE = "status_change"
    TOKEN_USAGE = "token_usage"
    HEARTBEAT = "heartbeat"
    LIFECYCLE = "lifecycle"


@dataclass
class AgentEvent:
    """Single event in an agent session's event stream."""

    session_id: str
    kind: AgentEventKind
    payload: dict[str, Any]
    sequence: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict representation."""
        return {
            "session_id": self.session_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind.value,
            "payload": self.payload,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentEvent":
        """Reconstruct an AgentEvent from a dict (e.g., from audit DB replay)."""
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif not isinstance(ts, datetime):
            ts = datetime.now(timezone.utc)
        return cls(
            session_id=data["session_id"],
            kind=AgentEventKind(data["kind"]),
            payload=data.get("payload", {}),
            sequence=data.get("sequence", 0),
            timestamp=ts,
            metadata=data.get("metadata", {}),
        )
