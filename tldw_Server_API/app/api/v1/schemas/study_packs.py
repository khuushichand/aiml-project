from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


StudyPackSourceType = Literal["note", "media", "message"]
StudyPackStatus = Literal["active", "superseded"]


class StudyPackSourceSelection(BaseModel):
    source_type: StudyPackSourceType
    source_id: str = Field(..., min_length=1)

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: Any) -> str:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("source_id must not be blank")
        return str(value)


class StudyPackCreateJobRequest(BaseModel):
    title: str = Field(..., min_length=1)
    workspace_id: Optional[str] = None
    deck_mode: Literal["new"] = "new"
    source_items: list[StudyPackSourceSelection] = Field(..., min_length=1)


class StudyPackSummaryResponse(BaseModel):
    id: int
    workspace_id: Optional[str] = None
    title: str
    deck_id: Optional[int] = None
    source_bundle_json: dict[str, Any] = Field(default_factory=dict)
    generation_options_json: Optional[dict[str, Any]] = None
    status: StudyPackStatus
    superseded_by_pack_id: Optional[int] = None
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    deleted: bool
    client_id: str
    version: int


StudyPackJobApiStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class StudyPackJobSummaryResponse(BaseModel):
    id: int
    status: StudyPackJobApiStatus
    domain: str
    queue: str
    job_type: str


class StudyPackJobAcceptedResponse(BaseModel):
    job: StudyPackJobSummaryResponse


class StudyPackJobStatusResponse(BaseModel):
    job: StudyPackJobSummaryResponse
    study_pack: Optional[StudyPackSummaryResponse] = None
    error: Optional[str] = None


class FlashcardCitationResponse(BaseModel):
    id: int
    flashcard_uuid: str
    source_type: StudyPackSourceType
    source_id: str
    citation_text: Optional[str] = None
    locator: Optional[str] = None
    ordinal: int = Field(default=0, ge=0)
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    deleted: bool
    client_id: str
    version: int


class FlashcardDeepDiveTarget(BaseModel):
    source_type: StudyPackSourceType
    source_id: str
    citation_ordinal: Optional[int] = Field(default=None, ge=0)
    route_kind: Optional[Literal["exact_locator", "workspace_route", "citation_only"]] = None
    route: Optional[str] = None
    available: bool = True
    fallback_reason: Optional[str] = None
