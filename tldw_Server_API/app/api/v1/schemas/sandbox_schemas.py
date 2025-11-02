from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


RuntimeType = Literal["docker", "firecracker"]


class SandboxRuntimeInfo(BaseModel):
    name: RuntimeType
    available: bool = Field(description="Whether this runtime is detected/usable on host")
    default_images: List[str] = Field(default_factory=list)
    max_cpu: Optional[float] = Field(default=None, description="Max CPU (cores) per run")
    max_mem_mb: Optional[int] = Field(default=None, description="Max memory (MB) per run")
    max_upload_mb: Optional[int] = Field(default=None, description="Max inline/session upload size (MB)")
    max_log_bytes: Optional[int] = Field(default=None, description="Max bytes streamed to logs per run")
    queue_max_length: Optional[int] = Field(default=None, description="Max queued runs before 429 is returned")
    queue_ttl_sec: Optional[int] = Field(default=None, description="Maximum time a run may remain queued before being dropped")
    workspace_cap_mb: Optional[int] = Field(default=None, description="Default workspace size cap (MB)")
    artifact_ttl_hours: Optional[int] = Field(default=None, description="Default artifact retention (hours)")
    supported_spec_versions: List[str] = Field(default_factory=lambda: ["1.0"])
    interactive_supported: Optional[bool] = Field(default=None, description="Whether stdin-over-WS interactive runs are supported")
    egress_allowlist_supported: Optional[bool] = Field(default=None, description="Whether egress allowlisting is supported by the runtime")
    store_mode: Optional[str] = Field(default=None, description="Current store backend mode (memory|sqlite|cluster)")
    notes: Optional[str] = None


class SandboxRuntimesResponse(BaseModel):
    runtimes: List[SandboxRuntimeInfo]


class SandboxSessionCreateRequest(BaseModel):
    spec_version: str = Field(default="1.0")
    runtime: Optional[RuntimeType] = Field(default=None, description="Preferred runtime; if omitted, policy decides")
    base_image: Optional[str] = Field(default=None, description="Default base image for runs in this session")
    cpu_limit: Optional[float] = Field(default=None, ge=0, description="vCPUs or CPU shares as supported by runtime")
    memory_mb: Optional[int] = Field(default=None, ge=64, description="Memory limit in MB")
    timeout_sec: Optional[int] = Field(default=300, ge=1, le=3600)
    network_policy: Optional[Literal["deny_all", "allowlist"]] = Field(default="deny_all")
    env: Optional[Dict[str, str]] = Field(default=None, description="Non-secret environment variables")
    labels: Optional[Dict[str, str]] = Field(default=None)


class SandboxSession(BaseModel):
    id: str
    runtime: RuntimeType
    base_image: Optional[str] = None
    expires_at: Optional[datetime] = None
    policy_hash: Optional[str] = None


class SandboxFileUploadResponse(BaseModel):
    session_id: str
    bytes_received: int
    file_count: int


class RunResources(BaseModel):
    cpu: Optional[float] = Field(default=None, ge=0)
    memory_mb: Optional[int] = Field(default=None, ge=64)


class RunFile(BaseModel):
    path: str
    content_b64: str


class SandboxRunCreateRequest(BaseModel):
    spec_version: str = Field(default="1.0")
    session_id: Optional[str] = None
    runtime: Optional[RuntimeType] = None
    base_image: Optional[str] = None
    command: List[str]
    env: Optional[Dict[str, str]] = None
    startup_timeout_sec: Optional[int] = Field(default=None, ge=1, le=600, description="Provisioning timeout (image pull/start). Separate from execution timeout.")
    timeout_sec: Optional[int] = Field(default=300, ge=1, le=3600)
    resources: Optional[RunResources] = None
    network_policy: Optional[Literal["deny_all", "allowlist"]] = Field(default=None)
    files: Optional[List[RunFile]] = Field(default=None, description="Inline small files to write before run")
    capture_patterns: Optional[List[str]] = Field(default=None, description="Glob patterns for artifact capture")


class SandboxRun(BaseModel):
    id: str
    session_id: Optional[str] = None
    runtime: RuntimeType
    base_image: Optional[str] = None
    command: List[str]
    created_at: datetime


class SandboxRunStatus(BaseModel):
    id: str
    spec_version: Optional[str] = None
    runtime: Optional[RuntimeType] = None
    base_image: Optional[str] = None
    image_digest: Optional[str] = None
    policy_hash: Optional[str] = None
    phase: Literal[
        "queued",
        "starting",
        "running",
        "completed",
        "failed",
        "killed",
        "timed_out",
    ]
    exit_code: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: Optional[str] = None
    resource_usage: Optional[Dict[str, int]] = Field(default=None, description="Resource usage summary when available")
    estimated_start_time: Optional[datetime] = None
    log_stream_url: Optional[str] = Field(default=None, description="Optional WS URL (signed or unsigned) to stream logs for this run")


class ArtifactInfo(BaseModel):
    path: str
    size: int
    download_url: Optional[str] = None


class ArtifactListResponse(BaseModel):
    items: List[ArtifactInfo]


class CancelResponse(BaseModel):
    id: str
    cancelled: bool
    message: Optional[str] = None


# Admin API Schemas
class SandboxAdminRunSummary(BaseModel):
    id: str
    user_id: Optional[str] = None
    spec_version: Optional[str] = None
    runtime: Optional[RuntimeType] = None
    base_image: Optional[str] = None
    image_digest: Optional[str] = None
    policy_hash: Optional[str] = None
    phase: Literal[
        "queued",
        "starting",
        "running",
        "completed",
        "failed",
        "killed",
        "timed_out",
    ]
    exit_code: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: Optional[str] = None


class SandboxAdminRunListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
    items: List[SandboxAdminRunSummary]


class SandboxAdminRunDetails(SandboxAdminRunSummary):
    resource_usage: Optional[Dict[str, int]] = None
