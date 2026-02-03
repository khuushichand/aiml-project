"""Base contracts for file artifact adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ValidationIssue:
    """Validation issue produced during structured payload checks."""
    code: str
    message: str
    path: str | None = None
    level: Literal["error", "warning"] = "error"


@dataclass(frozen=True)
class ExportResult:
    """Result of an export operation (inline bytes or deferred job)."""
    status: str
    content_type: str | None = None
    bytes_len: int | None = None
    content: bytes | None = None
    storage_path: str | None = None
    job_id: str | None = None


class FileAdapter(Protocol):
    """Protocol every file artifact adapter must implement."""
    file_type: str
    export_formats: set[str]

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return canonical structured representation for persistence."""
        ...

    def validate(self, structured: dict[str, Any]) -> list[ValidationIssue]:
        """Return validation issues; non-empty should fail the request."""
        ...

    def export(self, structured: dict[str, Any], *, format: str) -> ExportResult:
        """Export structured content to bytes or a deferred job."""
        ...
