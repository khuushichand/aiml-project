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
    timeout_seconds: Optional[int] = 300
    on_success: Optional[str] = None
    on_failure: Optional[str] = None


class WorkflowDefinitionCreate(BaseModel):
    name: str
    version: int = 1
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
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


class AdhocRunRequest(BaseModel):
    definition: WorkflowDefinitionCreate
    inputs: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    session_id: Optional[str] = None


class WorkflowRunResponse(BaseModel):
    run_id: str
    workflow_id: Optional[int] = None
    status: str
    status_reason: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    definition_version: Optional[int] = None


class EventResponse(BaseModel):
    event_seq: int
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str

