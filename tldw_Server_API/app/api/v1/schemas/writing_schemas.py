from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WritingVersionResponse(BaseModel):
    version: int = Field(..., description="Writing Playground API version")


class WritingSessionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Session name")
    payload: Dict[str, Any] = Field(..., description="Session payload JSON")
    schema_version: int = Field(1, ge=1, description="Payload schema version")
    id: Optional[str] = Field(None, description="Optional client-provided UUID")
    version_parent_id: Optional[str] = Field(None, description="Optional parent session ID")


class WritingSessionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Session name")
    payload: Optional[Dict[str, Any]] = Field(None, description="Session payload JSON")
    schema_version: Optional[int] = Field(None, ge=1, description="Payload schema version")
    version_parent_id: Optional[str] = Field(None, description="Optional parent session ID")


class WritingSessionCloneRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Name for the cloned session")


class WritingSessionResponse(BaseModel):
    id: str
    name: str
    payload: Dict[str, Any]
    schema_version: int
    version_parent_id: Optional[str] = None
    created_at: datetime
    last_modified: datetime
    deleted: bool
    client_id: str
    version: int


class WritingSessionListItem(BaseModel):
    id: str
    name: str
    last_modified: datetime
    version: int


class WritingSessionListResponse(BaseModel):
    sessions: List[WritingSessionListItem]
    total: int


class WritingTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    payload: Dict[str, Any] = Field(..., description="Template payload JSON")
    schema_version: int = Field(1, ge=1, description="Payload schema version")
    version_parent_id: Optional[str] = Field(None, description="Optional parent template ID")
    is_default: bool = Field(False, description="Whether this template is a default")


class WritingTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Template name")
    payload: Optional[Dict[str, Any]] = Field(None, description="Template payload JSON")
    schema_version: Optional[int] = Field(None, ge=1, description="Payload schema version")
    version_parent_id: Optional[str] = Field(None, description="Optional parent template ID")
    is_default: Optional[bool] = Field(None, description="Whether this template is a default")


class WritingTemplateResponse(BaseModel):
    id: int
    name: str
    payload: Dict[str, Any]
    schema_version: int
    version_parent_id: Optional[str] = None
    is_default: bool
    created_at: datetime
    last_modified: datetime
    deleted: bool
    client_id: str
    version: int


class WritingTemplateListResponse(BaseModel):
    templates: List[WritingTemplateResponse]
    total: int


class WritingThemeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Theme name")
    class_name: Optional[str] = Field(None, description="CSS class name")
    css: Optional[str] = Field(None, description="CSS rules scoped to the playground")
    schema_version: int = Field(1, ge=1, description="Theme schema version")
    version_parent_id: Optional[str] = Field(None, description="Optional parent theme ID")
    is_default: bool = Field(False, description="Whether this theme is a default")
    order: int = Field(0, description="Ordering index")


class WritingThemeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Theme name")
    class_name: Optional[str] = Field(None, description="CSS class name")
    css: Optional[str] = Field(None, description="CSS rules scoped to the playground")
    schema_version: Optional[int] = Field(None, ge=1, description="Theme schema version")
    version_parent_id: Optional[str] = Field(None, description="Optional parent theme ID")
    is_default: Optional[bool] = Field(None, description="Whether this theme is a default")
    order: Optional[int] = Field(None, description="Ordering index")


class WritingThemeResponse(BaseModel):
    id: int
    name: str
    class_name: Optional[str] = None
    css: Optional[str] = None
    schema_version: int
    version_parent_id: Optional[str] = None
    is_default: bool
    order: int
    created_at: datetime
    last_modified: datetime
    deleted: bool
    client_id: str
    version: int


class WritingThemeListResponse(BaseModel):
    themes: List[WritingThemeResponse]
    total: int


class WritingTokenizeOptions(BaseModel):
    include_strings: bool = Field(True, description="Include decoded token strings")


class WritingTokenizeRequest(BaseModel):
    provider: str = Field(..., min_length=1, description="Provider name")
    model: str = Field(..., min_length=1, description="Model name")
    text: str = Field(..., min_length=1, description="Input text")
    options: Optional[WritingTokenizeOptions] = None


class WritingTokenizeMeta(BaseModel):
    provider: str
    model: str
    tokenizer: str
    input_chars: int
    token_count: int
    warnings: List[str] = Field(default_factory=list)


class WritingTokenizeResponse(BaseModel):
    ids: List[int]
    strings: Optional[List[str]] = None
    meta: WritingTokenizeMeta


class WritingTokenCountRequest(BaseModel):
    provider: str = Field(..., min_length=1, description="Provider name")
    model: str = Field(..., min_length=1, description="Model name")
    text: str = Field(..., min_length=1, description="Input text")


class WritingTokenCountResponse(BaseModel):
    count: int
    meta: WritingTokenizeMeta


class WritingServerCapabilities(BaseModel):
    sessions: bool
    templates: bool
    themes: bool
    tokenize: bool
    token_count: bool


class WritingProviderCapabilities(BaseModel):
    name: str
    models: List[str]
    capabilities: Dict[str, Any]
    supported_fields: List[str]
    features: Dict[str, bool]


class WritingRequestedCapabilities(BaseModel):
    provider: str
    model: Optional[str] = None
    supported_fields: List[str]
    features: Dict[str, bool]
    tokenizer_available: bool
    tokenizer: Optional[str] = None
    tokenization_error: Optional[str] = None


class WritingCapabilitiesResponse(BaseModel):
    version: int
    server: WritingServerCapabilities
    default_provider: Optional[str] = None
    providers: Optional[List[WritingProviderCapabilities]] = None
    requested: Optional[WritingRequestedCapabilities] = None
