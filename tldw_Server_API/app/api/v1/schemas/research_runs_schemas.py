"""Schemas for deep research session APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchRunCreateRequest(BaseModel):
    """Request body for creating a deep research session."""

    query: str = Field(..., min_length=1, max_length=4000)
    source_policy: str = Field(default="balanced", min_length=1, max_length=64)
    autonomy_mode: str = Field(default="checkpointed", min_length=1, max_length=64)
    limits_json: dict[str, Any] | None = None
    provider_overrides: dict[str, Any] | None = None


class ResearchCheckpointPatchApproveRequest(BaseModel):
    """Optional user edits applied when approving a checkpoint."""

    patch_payload: dict[str, Any] | None = None


class ResearchRunResponse(BaseModel):
    """Current state returned for research session operations."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    phase: str
    control_state: str = "running"
    progress_percent: float | None = None
    progress_message: str | None = None
    active_job_id: str | None = None
    latest_checkpoint_id: str | None = None
    completed_at: str | None = None


class ResearchRunListItemResponse(ResearchRunResponse):
    """List item returned for recent deep research run queries."""

    query: str
    created_at: str
    updated_at: str


class ResearchCheckpointSummary(BaseModel):
    """Current checkpoint summary included in research stream snapshots."""

    checkpoint_id: str
    checkpoint_type: str
    status: str
    proposed_payload: dict[str, Any]
    resolution: str | None = None


class ResearchArtifactManifestEntry(BaseModel):
    """Latest-version artifact metadata for research stream snapshots."""

    artifact_name: str
    artifact_version: int
    content_type: str
    phase: str
    job_id: str | None = None


class ResearchRunSnapshotResponse(BaseModel):
    """Reconnect-safe snapshot for live research progress streams."""

    run: ResearchRunResponse
    latest_event_id: int = 0
    checkpoint: ResearchCheckpointSummary | None = None
    artifacts: list[ResearchArtifactManifestEntry] = Field(default_factory=list)


class ResearchArtifactResponse(BaseModel):
    """Typed artifact response for deep research polling APIs."""

    artifact_name: str
    content_type: str
    content: Any
