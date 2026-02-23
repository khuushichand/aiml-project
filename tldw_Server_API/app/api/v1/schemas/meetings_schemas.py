from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MeetingSessionStatus = Literal["scheduled", "live", "processing", "completed", "failed"]
MeetingSourceType = Literal["upload", "stream", "import"]
MeetingTemplateScope = Literal["builtin", "org", "team", "personal"]
MeetingArtifactKind = Literal[
    "transcript",
    "summary",
    "action_items",
    "decisions",
    "risks",
    "speaker_stats",
    "sentiment",
]


class MeetingHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "meetings"


class MeetingSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    meeting_type: str = Field(..., min_length=1, max_length=100)
    source_type: MeetingSourceType = "upload"
    language: str | None = Field(default=None, max_length=32)
    template_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] | None = None


class MeetingSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    meeting_type: str
    status: MeetingSessionStatus
    source_type: MeetingSourceType
    language: str | None = None
    template_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MeetingSessionStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MeetingSessionStatus


class MeetingTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    scope: MeetingTemplateScope = "personal"
    schema_json: dict[str, Any]
    enabled: bool = True
    is_default: bool = False


class MeetingTemplateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    scope: MeetingTemplateScope
    enabled: bool = True
    is_default: bool = False
    version: int = 1
    schema_json: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MeetingArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    kind: MeetingArtifactKind
    format: str
    payload_json: dict[str, Any]
    version: int = 1
    created_at: datetime | None = None


class MeetingArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MeetingArtifactKind
    format: str = Field(..., min_length=1, max_length=64)
    payload_json: dict[str, Any]
    version: int = Field(default=1, ge=1)
