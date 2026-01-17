from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


FileType = Literal["ical", "markdown_table", "html_table", "xlsx", "data_table"]
ExportFormat = Literal["ics", "md", "html", "xlsx", "csv", "json"]
ExportMode = Literal["url", "inline"]
AsyncMode = Literal["auto", "sync", "async"]


class FileExportRequest(BaseModel):
    format: ExportFormat
    mode: ExportMode = Field(default="url", description="Return URL or inline base64 content")
    async_mode: AsyncMode = Field(default="auto", description="auto defers large exports; async forces 202 + job_id")


class FileCreateOptions(BaseModel):
    persist: Literal[True] = Field(description="Persist artifact and export metadata (must be true)")
    max_bytes: Optional[int] = Field(default=None, ge=1, description="Hard cap for export bytes")
    max_rows: Optional[int] = Field(default=None, ge=1, description="Row cap for table-like payloads")
    max_cells: Optional[int] = Field(default=None, ge=1, description="Cell cap for table-like payloads")
    export_ttl_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="TTL in seconds for transient exports (URL mode only)",
    )
    retention_until: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp after which the artifact may be purged",
    )


class FileCreateRequest(BaseModel):
    file_type: FileType
    payload: Dict[str, Any] = Field(description="File-type specific payload")
    title: Optional[str] = Field(default=None, description="Display name for artifact")
    export: Optional[FileExportRequest] = None
    options: FileCreateOptions


class FileValidationIssue(BaseModel):
    code: str
    message: str
    path: Optional[str] = None


class FileValidationResult(BaseModel):
    ok: bool
    warnings: List[FileValidationIssue] = Field(default_factory=list)


class FileExportInfo(BaseModel):
    status: Literal["none", "ready", "pending"]
    format: Optional[ExportFormat] = None
    url: Optional[str] = None
    content_type: Optional[str] = None
    bytes: Optional[int] = None
    job_id: Optional[str] = None
    content_b64: Optional[str] = Field(default=None, description="Inline export payload (small files only)")
    expires_at: Optional[datetime] = None


class FileArtifact(BaseModel):
    file_id: int
    file_type: FileType
    title: str
    structured: Dict[str, Any]
    validation: FileValidationResult
    export: FileExportInfo
    retention_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class FileCreateResponse(BaseModel):
    artifact: FileArtifact


class FileArtifactResponse(BaseModel):
    artifact: FileArtifact


class FileDeleteResponse(BaseModel):
    success: bool
    file_deleted: bool = False


class FileArtifactsPurgeRequest(BaseModel):
    delete_files: bool = False
    soft_deleted_grace_days: int = Field(default=30, ge=0)
    include_retention: bool = True


class FileArtifactsPurgeResponse(BaseModel):
    removed: int
    files_deleted: int
