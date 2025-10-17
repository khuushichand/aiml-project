from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


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
