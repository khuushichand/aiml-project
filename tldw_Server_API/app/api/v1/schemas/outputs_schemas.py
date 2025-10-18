from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class OutputCreateRequest(BaseModel):
    template_id: int
    item_ids: Optional[List[int]] = Field(default=None, description="Items to render")
    run_id: Optional[int] = Field(default=None, description="Run to select items from (future)")
    title: Optional[str] = None
    data: Optional[Dict[str, object]] = Field(default=None, description="Inline context override (advanced)")
    tts_model: Optional[str] = Field(default=None, description="TTS model id, e.g., 'kokoro', 'tts-1'")
    tts_voice: Optional[str] = Field(default=None, description="TTS voice id, e.g., 'af_heart'")
    tts_speed: Optional[float] = Field(default=None, ge=0.25, le=4.0, description="TTS speed override")


class OutputArtifact(BaseModel):
    id: int
    title: str
    type: str
    format: Literal["md", "html", "mp3"]
    storage_path: str
    created_at: datetime


class OutputListResponse(BaseModel):
    items: List[OutputArtifact]
    total: int
    page: int
    size: int


class OutputUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    retention_until: Optional[str] = Field(default=None, description="ISO timestamp when this output can be purged")
    format: Optional[Literal["md", "html"]] = Field(default=None, description="Change text format and re-encode (md/html only)")
