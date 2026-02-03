"""
Schema helpers for normalized RAG chunk metadata.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

try:
    # Pydantic v2
    from pydantic import ConfigDict, field_validator  # type: ignore
except Exception:
    ConfigDict = None  # type: ignore
    from pydantic import validator as field_validator  # type: ignore


class CitationPoint(BaseModel):
    x: float = Field(..., ge=0.0)
    y: float = Field(..., ge=0.0)

    if ConfigDict is not None:
        model_config = ConfigDict(extra="ignore")
    else:  # pragma: no cover - v1 fallback
        class Config:
            extra = "ignore"


class CitationSpan(BaseModel):
    page_number: Optional[int] = None
    paragraph_number: Optional[int] = None
    line_number: Optional[int] = None
    slide_number: Optional[int] = None
    row_number: Optional[int] = None
    column_number: Optional[int] = None
    sheet_name: Optional[str] = None
    start_timestamp_ms: Optional[int] = None
    end_timestamp_ms: Optional[int] = None
    bbox_quad: Optional[list[CitationPoint]] = None

    if ConfigDict is not None:
        model_config = ConfigDict(extra="ignore")
    else:  # pragma: no cover - v1 fallback
        class Config:
            extra = "ignore"

    @field_validator("bbox_quad")
    @classmethod
    def _cap_bbox_quad(cls, value: Optional[list[CitationPoint]]):
        if not value:
            return value
        if len(value) > 4:
            return value[:4]
        return value


class RAGChunkMetadata(BaseModel):
    media_id: Optional[str] = None
    file_name: Optional[str] = None
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    chunk_type: Optional[Literal["text", "table", "list", "code", "media", "heading", "vlm"]] = None
    section_path: Optional[str] = None
    ancestry_titles: Optional[list[str]] = None
    language: Optional[str] = None
    code_language: Optional[str] = None
    list_style: Optional[str] = None
    table_row: Optional[int] = None
    table_col: Optional[int] = None
    context_header: Optional[str] = None
    contextual_summary_ref: Optional[str] = None
    citation: Optional[CitationSpan] = None

    if ConfigDict is not None:
        model_config = ConfigDict(extra="ignore")
    else:  # pragma: no cover - v1 fallback
        class Config:
            extra = "ignore"


def model_dump_compat(model: BaseModel) -> dict[str, Any]:
    """Return a Pydantic model as a dict without None values (v1/v2 compatible)."""
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)  # type: ignore[call-arg]
    return model.dict(exclude_none=True)  # type: ignore[call-arg]

