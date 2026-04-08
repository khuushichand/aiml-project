from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


VideoLiteSourceState = Literal["not_ingested", "processing", "ready", "failed"]
VideoLiteLauncherAccess = Literal["login_required", "subscription_required", "allowed"]
VideoLiteEntitlement = Literal["signed_out", "signed_in_unsubscribed", "signed_in_subscribed"]
VideoLiteSummaryState = Literal["not_requested", "processing", "ready", "failed"]


class VideoLiteSourceStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(..., min_length=1, description="Original source URL or canonical source key.")
    source_state: VideoLiteSourceState = Field(
        default="not_ingested",
        description="Optional source state hint for the video-lite contract.",
    )
    target_tab: str | None = Field(
        default=None,
        description="Requested workspace tab for the source entry.",
    )

    @field_validator("source_url", mode="before")
    @classmethod
    def _normalize_source_url(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("source_url cannot be blank")
        return normalized


class VideoLiteSourceStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(..., description="Original source URL supplied by the client.")
    source_key: str = Field(..., description="Canonical source key derived from the source URL.")
    state: VideoLiteSourceState = Field(..., description="Current ingestion state for the source.")
    target_tab: str | None = Field(
        default=None,
        description="Requested workspace tab for the source entry.",
    )
    launcher_access: VideoLiteLauncherAccess = Field(
        ...,
        description="Canonical launcher-routing access state.",
    )
    entitlement: VideoLiteEntitlement = Field(
        ...,
        description="Current user entitlement state for the lightweight video contract.",
    )


class VideoLiteWorkspaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(..., description="Original source URL supplied by the client, if known.")
    source_key: str = Field(..., description="Canonical source key derived from the source URL.")
    state: VideoLiteSourceState = Field(..., description="Current ingestion state for the source.")
    transcript: str | None = Field(default=None, description="Transcript content when available.")
    summary: str | None = Field(default=None, description="Generated summary content when available.")
    summary_state: VideoLiteSummaryState = Field(
        default="not_requested",
        description="Current eager-summary lifecycle state for the source.",
    )
    entitlement: VideoLiteEntitlement = Field(
        ...,
        description="Current user entitlement state for the lightweight workspace.",
    )
