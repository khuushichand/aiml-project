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


class ResearchArtifactResponse(BaseModel):
    """Typed artifact response for deep research polling APIs."""

    artifact_name: str
    content_type: str
    content: Any
