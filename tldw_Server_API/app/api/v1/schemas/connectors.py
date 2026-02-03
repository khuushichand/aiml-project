from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectorProvider(BaseModel):
    name: Literal["drive", "notion"]
    auth_type: Literal["oauth2", "token"] = "oauth2"
    scopes_required: list[str] = Field(default_factory=list)


class ConnectorAccount(BaseModel):
    id: int
    provider: Literal["drive", "notion"]
    display_name: str
    created_at: str | None = None
    connected: bool = True
    email: str | None = None


class SyncOptions(BaseModel):
    recursive: bool = True
    include_types: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    export_format_overrides: dict[str, str] = Field(default_factory=dict)


class ConnectorSource(BaseModel):
    id: int
    account_id: int
    provider: Literal["drive", "notion"]
    remote_id: str
    type: Literal["folder", "page", "database", "link"]
    path: str | None = None
    options: SyncOptions = Field(default_factory=SyncOptions)
    enabled: bool = True
    last_synced_at: str | None = None


class ImportJob(BaseModel):
    id: str = Field(..., description="Job identifier (UUID)")
    source_id: int
    type: Literal["import", "sync"] = "import"
    status: Literal["queued", "running", "succeeded", "failed", "canceled"] = "queued"
    progress_pct: int = 0
    counts: dict[str, int] = Field(default_factory=lambda: {"processed": 0, "skipped": 0, "failed": 0})
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class AuthorizeURLResponse(BaseModel):
    auth_url: str
    state: str | None = None


class ConnectorPolicy(BaseModel):
    org_id: int
    enabled_providers: list[Literal["drive", "notion"]] = Field(default_factory=lambda: ["drive", "notion"])
    allowed_export_formats: list[Literal["md", "txt", "pdf"]] = Field(default_factory=lambda: ["md", "txt", "pdf"])
    allowed_file_types: list[str] = Field(default_factory=list, description="Extensions or MIME prefixes")
    max_file_size_mb: int = 500
    account_linking_role: Literal["admin", "owner", "lead", "member"] = "admin"
    allowed_account_domains: list[str] = Field(default_factory=list)
    allowed_remote_paths: list[str] = Field(default_factory=list)
    denied_remote_paths: list[str] = Field(default_factory=list)
    allowed_notion_workspaces: list[str] = Field(default_factory=list)
    denied_notion_workspaces: list[str] = Field(default_factory=list)
    quotas_per_role: dict[str, dict[str, int]] = Field(default_factory=dict, description="e.g., {role: {max_jobs_per_day: N}}")


# Request models

class ConnectorSourceCreateRequest(BaseModel):
    """Create a new connector source to import/sync from."""
    model_config = dict(extra='forbid')

    account_id: int
    provider: Literal["drive", "notion"]
    remote_id: str
    type: Literal["folder", "page", "database", "link"]
    path: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ConnectorSourcePatchRequest(BaseModel):
    """Patch a connector source."""
    model_config = dict(extra='forbid')

    enabled: bool | None = None
    options: dict[str, Any] | None = None
