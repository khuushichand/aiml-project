"""Base contracts for file artifact adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Protocol


@dataclass(frozen=True)
class ValidationIssue:
    """Validation issue produced during structured payload checks."""
    code: str
    message: str
    path: Optional[str] = None
    level: Literal["error", "warning"] = "error"


@dataclass(frozen=True)
class ExportResult:
    """Result of an export operation (inline bytes or deferred job)."""
    status: str
    content_type: Optional[str] = None
    bytes_len: Optional[int] = None
    content: Optional[bytes] = None
    storage_path: Optional[str] = None
    job_id: Optional[str] = None


class FileAdapter(Protocol):
    """Protocol every file artifact adapter must implement."""
    file_type: str
    export_formats: set[str]

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return canonical structured representation for persistence."""
        ...

    def validate(self, structured: Dict[str, Any]) -> list[ValidationIssue]:
        """Return validation issues; non-empty should fail the request."""
        ...

    def export(self, structured: Dict[str, Any], *, format: str) -> ExportResult:
        """Export structured content to bytes or a deferred job."""
        ...
