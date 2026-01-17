from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tldw_Server_API.app.api.v1.schemas.file_artifacts_schemas import FileExportInfo
try:
    # Pydantic v2
    from pydantic import model_validator  # type: ignore
except Exception:  # pragma: no cover - fallback for older environments
    model_validator = None  # type: ignore


ColumnType = Literal["text", "number", "date", "url", "boolean", "currency"]
SourceType = Literal["chat", "document", "rag_query"]
DataTableExportFormat = Literal["csv", "json", "xlsx"]


class DataTableColumnHint(BaseModel):
    """Optional schema hint supplied during generation."""

    name: str = Field(..., min_length=1)
    type: Optional[ColumnType] = None
    description: Optional[str] = None
    format: Optional[str] = None


class DataTableSourceInput(BaseModel):
    """Source reference used to generate a table."""

    source_type: SourceType
    source_id: str = Field(..., min_length=1)
    title: Optional[str] = None
    snapshot: Optional[Any] = None
    retrieval_params: Optional[Dict[str, Any]] = None


class DataTableGenerateRequest(BaseModel):
    """Request payload for data table generation."""

    name: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    description: Optional[str] = None
    sources: List[DataTableSourceInput]
    column_hints: Optional[List[DataTableColumnHint]] = None
    model: Optional[str] = None
    max_rows: Optional[int] = Field(default=None, ge=1, le=20000)

    if model_validator is not None:
        @model_validator(mode="after")
        def _validate_payload(self) -> "DataTableGenerateRequest":
            if not self.name or not self.name.strip():
                raise ValueError("name is required")
            if not self.prompt or not self.prompt.strip():
                raise ValueError("prompt is required")
            if not self.sources:
                raise ValueError("sources are required")
            return self
    else:
        from pydantic import root_validator as _rv  # type: ignore

        @_rv
        def _validate_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[no-redef]
            name = (values.get("name") or "").strip()
            prompt = (values.get("prompt") or "").strip()
            sources = values.get("sources") or []
            if not name:
                raise ValueError("name is required")
            if not prompt:
                raise ValueError("prompt is required")
            if not sources:
                raise ValueError("sources are required")
            return values


class DataTableRegenerateRequest(BaseModel):
    """Optional overrides for table regeneration."""

    prompt: Optional[str] = None
    model: Optional[str] = None
    max_rows: Optional[int] = Field(default=None, ge=1, le=20000)


class DataTableUpdateRequest(BaseModel):
    """Patchable metadata fields for a data table."""

    name: Optional[str] = None
    description: Optional[str] = None

    if model_validator is not None:
        @model_validator(mode="after")
        def _validate_payload(self) -> "DataTableUpdateRequest":
            if self.name is None and self.description is None:
                raise ValueError("at least one field is required")
            if self.name is not None and not self.name.strip():
                raise ValueError("name cannot be blank")
            return self
    else:
        from pydantic import root_validator as _rv  # type: ignore

        @_rv
        def _validate_payload(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[no-redef]
            if values.get("name") is None and values.get("description") is None:
                raise ValueError("at least one field is required")
            name = values.get("name")
            if name is not None and not str(name).strip():
                raise ValueError("name cannot be blank")
            return values


class DataTableColumn(BaseModel):
    column_id: str
    name: str
    type: str
    description: Optional[str] = None
    format: Optional[str] = None
    position: int


class DataTableColumnInput(BaseModel):
    column_id: Optional[str] = None
    name: str = Field(..., min_length=1)
    type: ColumnType
    description: Optional[str] = None
    format: Optional[str] = None
    position: Optional[int] = None


class DataTableRow(BaseModel):
    row_id: str
    row_index: int
    data: Any
    row_hash: Optional[str] = None


class DataTableSource(BaseModel):
    source_type: str
    source_id: str
    title: Optional[str] = None
    snapshot: Optional[Any] = None
    retrieval_params: Optional[Any] = None


class DataTableSummary(BaseModel):
    uuid: str
    name: str
    description: Optional[str] = None
    prompt: str
    column_hints: Optional[Any] = None
    status: str
    row_count: int
    column_count: Optional[int] = None
    generation_model: Optional[str] = None
    last_error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_modified: Optional[str] = None
    version: Optional[int] = None
    source_count: Optional[int] = None


class DataTablesListResponse(BaseModel):
    tables: List[DataTableSummary]
    items: List[DataTableSummary]
    results: List[DataTableSummary]
    count: int
    limit: int
    offset: int
    total: Optional[int] = None


class DataTableDetailResponse(BaseModel):
    table: DataTableSummary
    columns: List[DataTableColumn]
    rows: List[DataTableRow]
    sources: List[DataTableSource]
    rows_limit: int
    rows_offset: int


class DataTableContentUpdateRequest(BaseModel):
    columns: List[DataTableColumnInput]
    rows: List[Dict[str, Any]]


class DataTableGenerateResponse(BaseModel):
    job_id: int
    job_uuid: Optional[str] = None
    status: str
    table: DataTableSummary


class DataTableDeleteResponse(BaseModel):
    success: bool


class DataTableJobStatus(BaseModel):
    id: int
    uuid: Optional[str]
    status: str
    job_type: str
    owner_user_id: Optional[str]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    cancelled_at: Optional[str]
    cancellation_reason: Optional[str]
    progress_percent: Optional[float]
    progress_message: Optional[str]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    table_uuid: Optional[str] = None


class DataTableJobCancelResponse(BaseModel):
    success: bool
    job_id: int
    status: str
    message: Optional[str] = None


class DataTableExportResponse(BaseModel):
    table_uuid: str
    file_id: int
    export: FileExportInfo
