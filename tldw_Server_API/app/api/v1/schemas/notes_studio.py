"""Shared request and response models for Notes Studio sidecar storage."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .notes_schemas import NoteResponse

NoteStudioTemplateType = Literal["lined", "grid", "cornell"]
NoteStudioHandwritingMode = Literal["off", "accented"]


class NoteStudioDocumentBase(BaseModel):
    note_id: str = Field(..., description="Primary note identifier for the Studio sidecar.")
    payload_json: dict[str, Any] = Field(..., description="Canonical structured Studio payload.")
    template_type: NoteStudioTemplateType = Field(
        ...,
        description="Studio template used to render the note companion.",
    )
    handwriting_mode: NoteStudioHandwritingMode = Field(
        "accented",
        description="Notebook handwriting treatment used by Studio rendering.",
    )
    source_note_id: str | None = Field(
        default=None,
        description="Original source note identifier for derived Studio content.",
    )
    excerpt_snapshot: str | None = Field(
        default=None,
        description="Exact excerpt snapshot used to derive the Studio note.",
    )
    excerpt_hash: str | None = Field(
        default=None,
        description="Stable hash for the excerpt snapshot.",
    )
    diagram_manifest_json: dict[str, Any] | None = Field(
        default=None,
        description="Optional manifest for Studio diagram requests and outputs.",
    )
    companion_content_hash: str | None = Field(
        default=None,
        description="Hash of the generated Markdown companion body.",
    )
    render_version: int = Field(..., ge=1, description="Renderer schema version.")


class NoteStudioDocumentCreateRequest(NoteStudioDocumentBase):
    """Request model for inserting a new Studio sidecar record."""


class NoteStudioDocumentUpsertRequest(NoteStudioDocumentBase):
    """Request model for inserting or updating a Studio sidecar record."""


class NoteStudioDocumentSummaryResponse(BaseModel):
    note_id: str
    template_type: NoteStudioTemplateType
    handwriting_mode: NoteStudioHandwritingMode
    source_note_id: str | None = None
    excerpt_hash: str | None = None
    companion_content_hash: str | None = None
    render_version: int = Field(..., ge=1)

    model_config = ConfigDict(from_attributes=True)


class NoteStudioDocumentResponse(NoteStudioDocumentBase):
    created_at: datetime = Field(..., description="Creation timestamp.")
    last_modified: datetime = Field(..., description="Last modification timestamp.")

    model_config = ConfigDict(from_attributes=True)


class NoteStudioDeriveRequest(BaseModel):
    source_note_id: str = Field(..., description="Source note identifier used for derivation.")
    excerpt_text: str = Field(..., description="Selected source excerpt used for Studio generation.")
    template_type: NoteStudioTemplateType = Field(
        "lined",
        description="Notebook template to use for the derived Studio note.",
    )
    handwriting_mode: NoteStudioHandwritingMode = Field(
        "accented",
        description="Handwriting accent mode for the derived Studio note.",
    )
    provider: str | None = Field(default=None, description="Optional provider override for structured generation.")
    model: str | None = Field(default=None, description="Optional model override for structured generation.")


class NoteStudioRegenerateRequest(BaseModel):
    current_markdown: str | None = Field(
        default=None,
        description="Optional current Markdown companion from the editor when regenerating a stale Studio note.",
    )


class NoteStudioDiagramRequest(BaseModel):
    diagram_type: Literal["flowchart", "sequence", "class", "state", "er", "gantt", "pie"] = Field(
        "flowchart",
        description="Diagram type to generate for the Studio note.",
    )
    source_section_ids: list[str] = Field(
        default_factory=list,
        description="Canonical Studio section identifiers used as diagram sources.",
    )
    provider: str | None = Field(default=None, description="Optional provider override for diagram generation.")
    model: str | None = Field(default=None, description="Optional model override for diagram generation.")


class NoteStudioStateResponse(BaseModel):
    note: "NoteResponse" = Field(..., description="The current note payload for the Studio note.")
    studio_document: NoteStudioDocumentResponse = Field(..., description="Canonical Studio sidecar document.")
    is_stale: bool = Field(..., description="Whether note Markdown drifted from the canonical Studio payload.")
    stale_reason: str | None = Field(default=None, description="Reason the note is currently marked stale.")


class NoteStudioDiagramResponse(NoteStudioStateResponse):
    """Response envelope for diagram manifest updates."""
