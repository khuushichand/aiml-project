"""Pydantic schemas for file artifact APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FileType = Literal["ical", "markdown_table", "html_table", "xlsx", "data_table", "image"]
ExportFormat = Literal["ics", "md", "html", "xlsx", "csv", "json", "png", "jpg", "webp"]
ExportMode = Literal["url", "inline"]
AsyncMode = Literal["auto", "sync", "async"]


class FileExportRequest(BaseModel):
    """Export request options for file artifacts."""
    format: ExportFormat
    mode: ExportMode = Field(default="url", description="Return URL or inline base64 content")
    async_mode: AsyncMode = Field(default="auto", description="auto defers large exports; async forces 202 + job_id")


class FileCreateOptions(BaseModel):
    """Options controlling artifact persistence and export limits."""
    persist: Literal[True] = Field(description="Persist artifact and export metadata (must be true)")
    max_bytes: int | None = Field(default=None, ge=1, description="Hard cap for export bytes")
    max_rows: int | None = Field(default=None, ge=1, description="Row cap for table-like payloads")
    max_cells: int | None = Field(default=None, ge=1, description="Cell cap for table-like payloads")
    export_ttl_seconds: int | None = Field(
        default=None,
        ge=1,
        description="TTL in seconds for transient exports (URL mode only)",
    )
    retention_until: datetime | None = Field(
        default=None,
        description="UTC timestamp after which the artifact may be purged",
    )


class FileCreateRequest(BaseModel):
    """Request payload for creating a file artifact."""
    file_type: FileType
    payload: dict[str, Any] = Field(description="File-type specific payload")
    title: str | None = Field(default=None, description="Display name for artifact")
    export: FileExportRequest | None = None
    options: FileCreateOptions


class FileValidationIssue(BaseModel):
    """Validation issue detail for artifact payloads."""
    code: str
    message: str
    path: str | None = None


class FileValidationResult(BaseModel):
    """Validation result containing warnings."""
    ok: bool
    warnings: list[FileValidationIssue] = Field(default_factory=list)


class FileExportInfo(BaseModel):
    """Export status and delivery details."""
    status: Literal["none", "ready", "pending"]
    format: ExportFormat | None = None
    url: str | None = None
    content_type: str | None = None
    bytes: int | None = None
    job_id: str | None = None
    content_b64: str | None = Field(default=None, description="Inline export payload (small files only)")
    expires_at: datetime | None = None


class FileArtifact(BaseModel):
    """File artifact response payload."""
    file_id: int
    file_type: FileType
    title: str
    structured: dict[str, Any]
    validation: FileValidationResult
    export: FileExportInfo
    retention_until: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FileCreateResponse(BaseModel):
    """Response wrapper for artifact creation."""
    artifact: FileArtifact


class FileArtifactResponse(BaseModel):
    """Response wrapper for fetching an artifact."""
    artifact: FileArtifact


class FileDeleteResponse(BaseModel):
    """Response for delete operations."""
    success: bool
    file_deleted: bool = False


class ReferenceImageListItem(BaseModel):
    """Picker-safe metadata for a reference image candidate."""

    file_id: int
    title: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    created_at: datetime


class ReferenceImageListResponse(BaseModel):
    """Response wrapper for picker-safe reference image candidates."""

    items: list[ReferenceImageListItem] = Field(default_factory=list)


class FileArtifactsPurgeRequest(BaseModel):
    """Request to purge file artifacts."""
    delete_files: bool = False
    soft_deleted_grace_days: int = Field(default=30, ge=0)
    include_retention: bool = True


class FileArtifactsPurgeResponse(BaseModel):
    """Response for purge summary."""
    removed: int
    files_deleted: int
