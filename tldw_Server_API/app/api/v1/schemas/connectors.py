from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectorProvider(BaseModel):
    name: Literal["drive", "notion", "gmail", "onedrive"]
    auth_type: Literal["oauth2", "token"] = "oauth2"
    scopes_required: list[str] = Field(default_factory=list)


class ConnectorAccount(BaseModel):
    id: int
    provider: Literal["drive", "notion", "gmail", "onedrive"]
    display_name: str
    created_at: str | None = None
    connected: bool = True
    email: str | None = None


class SyncOptions(BaseModel):
    recursive: bool = True
    include_types: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    export_format_overrides: dict[str, str] = Field(default_factory=dict)


class ConnectorSourceSyncSummary(BaseModel):
    state: str = "idle"
    sync_mode: str = "manual"
    last_sync_succeeded_at: str | None = None
    last_sync_failed_at: str | None = None
    last_error: str | None = None
    webhook_status: str | None = None
    needs_full_rescan: bool = False
    active_job_id: str | None = None
    tracked_item_count: int = 0
    degraded_item_count: int = 0


class ConnectorSource(BaseModel):
    id: int
    account_id: int
    provider: Literal["drive", "notion", "gmail", "onedrive"]
    remote_id: str
    type: Literal["folder", "file", "page", "database", "link"]
    path: str | None = None
    options: SyncOptions = Field(default_factory=SyncOptions)
    enabled: bool = True
    last_synced_at: str | None = None
    sync: ConnectorSourceSyncSummary | None = None


class ImportJob(BaseModel):
    id: str = Field(..., description="Job identifier (UUID)")
    source_id: int
    type: str = "import"
    status: Literal["queued", "running", "succeeded", "failed", "canceled"] = "queued"
    progress_pct: int = 0
    counts: dict[str, int] = Field(default_factory=lambda: {"processed": 0, "skipped": 0, "failed": 0})
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class ConnectorSyncJobSummary(BaseModel):
    id: str
    type: str = "import"
    status: str
    progress_pct: int = 0
    counts: dict[str, int] = Field(default_factory=lambda: {"processed": 0, "skipped": 0, "failed": 0})


class ConnectorSourceSyncStatus(BaseModel):
    source_id: int
    provider: Literal["drive", "notion", "gmail", "onedrive"]
    enabled: bool = True
    state: str = "idle"
    sync_mode: str = "manual"
    cursor: str | None = None
    cursor_kind: str | None = None
    last_bootstrap_at: str | None = None
    last_sync_started_at: str | None = None
    last_sync_succeeded_at: str | None = None
    last_sync_failed_at: str | None = None
    last_error: str | None = None
    retry_backoff_count: int = 0
    webhook_status: str | None = None
    webhook_expires_at: str | None = None
    needs_full_rescan: bool = False
    active_job_id: str | None = None
    active_job_started_at: str | None = None
    active_job: ConnectorSyncJobSummary | None = None
    tracked_item_count: int = 0
    degraded_item_count: int = 0


class AuthorizeURLResponse(BaseModel):
    auth_url: str
    state: str | None = None


class ConnectorPolicy(BaseModel):
    org_id: int
    enabled_providers: list[Literal["drive", "notion", "gmail", "onedrive"]] = Field(default_factory=lambda: ["drive", "notion"])
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
    model_config = {"extra": 'forbid'}

    account_id: int
    provider: Literal["drive", "notion", "gmail", "onedrive"]
    remote_id: str
    type: Literal["folder", "file", "page", "database", "link"]
    path: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ConnectorSourcePatchRequest(BaseModel):
    """Patch a connector source."""
    model_config = {"extra": 'forbid'}

    enabled: bool | None = None
    options: dict[str, Any] | None = None
