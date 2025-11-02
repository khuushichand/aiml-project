from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ConnectorProvider(BaseModel):
    name: Literal["drive", "notion"]
    auth_type: Literal["oauth2", "token"] = "oauth2"
    scopes_required: List[str] = Field(default_factory=list)


class ConnectorAccount(BaseModel):
    id: int
    provider: Literal["drive", "notion"]
    display_name: str
    created_at: Optional[str] = None
    connected: bool = True
    email: Optional[str] = None


class SyncOptions(BaseModel):
    recursive: bool = True
    include_types: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)
    export_format_overrides: Dict[str, str] = Field(default_factory=dict)


class ConnectorSource(BaseModel):
    id: int
    account_id: int
    provider: Literal["drive", "notion"]
    remote_id: str
    type: Literal["folder", "page", "database", "link"]
    path: Optional[str] = None
    options: SyncOptions = Field(default_factory=SyncOptions)
    enabled: bool = True
    last_synced_at: Optional[str] = None


class ImportJob(BaseModel):
    id: str = Field(..., description="Job identifier (UUID)")
    source_id: int
    type: Literal["import", "sync"] = "import"
    status: Literal["queued", "running", "succeeded", "failed", "canceled"] = "queued"
    progress_pct: int = 0
    counts: Dict[str, int] = Field(default_factory=lambda: {"processed": 0, "skipped": 0, "failed": 0})
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class AuthorizeURLResponse(BaseModel):
    auth_url: str
    state: Optional[str] = None


class ConnectorPolicy(BaseModel):
    org_id: int
    enabled_providers: List[Literal["drive", "notion"]] = Field(default_factory=lambda: ["drive", "notion"])
    allowed_export_formats: List[Literal["md", "txt", "pdf"]] = Field(default_factory=lambda: ["md", "txt", "pdf"])
    allowed_file_types: List[str] = Field(default_factory=list, description="Extensions or MIME prefixes")
    max_file_size_mb: int = 500
    account_linking_role: Literal["admin", "owner", "lead", "member"] = "admin"
    allowed_account_domains: List[str] = Field(default_factory=list)
    allowed_remote_paths: List[str] = Field(default_factory=list)
    denied_remote_paths: List[str] = Field(default_factory=list)
    allowed_notion_workspaces: List[str] = Field(default_factory=list)
    denied_notion_workspaces: List[str] = Field(default_factory=list)
    quotas_per_role: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="e.g., {role: {max_jobs_per_day: N}}")
