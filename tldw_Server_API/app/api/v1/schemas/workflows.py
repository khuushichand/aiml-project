from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class WorkflowInputSchema(BaseModel):
    # Free-form for v0.1 stub
    params: Dict[str, Any] = Field(default_factory=dict)


class StepConfig(BaseModel):
    id: str = Field(..., description="Step identifier")
    name: Optional[str] = None
    type: str = Field(..., description="Step type name")
    config: Dict[str, Any] = Field(default_factory=dict)
    retry: Optional[int] = 0
    timeout_seconds: Optional[float] = 300
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    on_timeout: Optional[str] = None


class WorkflowRagSearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    sources: Optional[List[str]] = None
    search_mode: Optional[Literal["fts", "vector", "hybrid"]] = None
    hybrid_alpha: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=1, le=100)
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    expand_query: Optional[bool] = None
    expansion_strategies: Optional[List[Literal["acronym", "synonym", "domain", "entity"]]] = None
    spell_check: Optional[bool] = None
    enable_cache: Optional[bool] = None
    cache_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    adaptive_cache: Optional[bool] = None
    cache_ttl: Optional[int] = Field(default=None, ge=0)
    enable_table_processing: Optional[bool] = None
    table_method: Optional[Literal["markdown", "html", "hybrid"]] = None
    include_sibling_chunks: Optional[bool] = None
    sibling_window: Optional[int] = Field(default=None, ge=0, le=20)
    enable_parent_expansion: Optional[bool] = None
    include_parent_document: Optional[bool] = None
    parent_max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)
    enable_reranking: Optional[bool] = None
    reranking_strategy: Optional[Literal["flashrank", "cross_encoder", "hybrid", "none"]] = None
    rerank_top_k: Optional[int] = Field(default=None, ge=1, le=100)
    enable_citations: Optional[bool] = None
    citation_style: Optional[Literal["apa", "mla", "chicago", "harvard", "ieee"]] = None
    include_page_numbers: Optional[bool] = None
    enable_chunk_citations: Optional[bool] = None
    enable_generation: Optional[bool] = None
    generation_model: Optional[str] = Field(default=None, max_length=128)
    generation_prompt: Optional[str] = Field(default=None, max_length=8192)
    max_generation_tokens: Optional[int] = Field(default=None, ge=1, le=8192)
    enable_security_filter: Optional[bool] = None
    detect_pii: Optional[bool] = None
    redact_pii: Optional[bool] = None
    sensitivity_level: Optional[Literal["public", "internal", "confidential", "restricted"]] = None
    content_filter: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    highlight_results: Optional[bool] = None
    highlight_query_terms: Optional[bool] = None
    track_cost: Optional[bool] = None

    @field_validator("query", mode="before")
    @classmethod
    def _normalize_query(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("query must not be empty")
            return stripped
        return value

    @field_validator(
        "search_mode",
        "table_method",
        "reranking_strategy",
        "citation_style",
        "sensitivity_level",
        mode="before",
    )
    @classmethod
    def _normalize_lower(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("sources", mode="before")
    @classmethod
    def _normalize_sources(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if "," in raw:
                return [s.strip() for s in raw.split(",") if s.strip()]
            return [raw]
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return value

    @field_validator("expansion_strategies", mode="before")
    @classmethod
    def _normalize_expansion_strategies(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            return [s.strip().lower() for s in raw.split(",") if s.strip()]
        if isinstance(value, list):
            return [str(v).strip().lower() for v in value if str(v).strip()]
        return value


class WorkflowDefinitionCreate(BaseModel):
    name: str
    version: int = 1
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    # Optional completion webhook configuration. Accepts either a URL string or
    # an object with fields like {"url": str, "include_outputs": bool}.
    on_completion_webhook: Optional[Dict[str, Any] | str] = None
    steps: List[StepConfig]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    visibility: Literal["private"] = "private"


class WorkflowDefinitionResponse(BaseModel):
    id: int
    name: str
    version: int
    description: Optional[str]
    tags: List[str]
    is_active: bool


class RunRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    session_id: Optional[str] = None
    # Scoped secrets are injected into the execution context but never persisted.
    # Keys are provider/module specific (e.g., api keys), values are strings.
    secrets: Optional[Dict[str, str]] = Field(default_factory=dict)
    # Per-run validation behavior for safety checks (e.g., artifact scope)
    # 'block' rejects on validation failure; 'non-block' logs/warns and proceeds.
    validation_mode: Literal["block", "non-block"] = "block"


class AdhocRunRequest(BaseModel):
    definition: WorkflowDefinitionCreate
    inputs: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    session_id: Optional[str] = None
    secrets: Optional[Dict[str, str]] = Field(default_factory=dict)
    validation_mode: Literal["block", "non-block"] = "block"


class WorkflowRunResponse(BaseModel):
    id: Optional[str] = None
    run_id: str
    workflow_id: Optional[int] = None
    user_id: Optional[str] = None
    status: str
    status_reason: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    definition_version: Optional[int] = None
    validation_mode: Optional[str] = None


class EventResponse(BaseModel):
    event_seq: int
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


# Listing schemas (lighter than full run response)
class WorkflowRunListItem(BaseModel):
    run_id: str
    workflow_id: Optional[int] = None
    user_id: Optional[str] = None
    status: str
    status_reason: Optional[str] = None
    definition_version: Optional[int] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class WorkflowRunListResponse(BaseModel):
    runs: List[WorkflowRunListItem]
    next_offset: Optional[int] = None
    next_cursor: Optional[str] = None
