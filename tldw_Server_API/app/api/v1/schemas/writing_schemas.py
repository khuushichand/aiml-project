from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WritingVersionResponse(BaseModel):
    version: int = Field(..., description="Writing Playground API version")


class WritingSessionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Session name")
    payload: dict[str, Any] = Field(..., description="Session payload JSON")
    schema_version: int = Field(1, ge=1, description="Payload schema version")
    id: str | None = Field(None, description="Optional client-provided UUID")
    version_parent_id: str | None = Field(None, description="Optional parent session ID")


class WritingSessionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255, description="Session name")
    payload: dict[str, Any] | None = Field(None, description="Session payload JSON")
    schema_version: int | None = Field(None, ge=1, description="Payload schema version")
    version_parent_id: str | None = Field(None, description="Optional parent session ID")


class WritingSessionCloneRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255, description="Name for the cloned session")


class WritingSessionResponse(BaseModel):
    id: str
    name: str
    payload: dict[str, Any]
    schema_version: int
    version_parent_id: str | None = None
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
    sessions: list[WritingSessionListItem]
    total: int


class WritingTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    payload: dict[str, Any] = Field(..., description="Template payload JSON")
    schema_version: int = Field(1, ge=1, description="Payload schema version")
    version_parent_id: str | None = Field(None, description="Optional parent template ID")
    is_default: bool = Field(False, description="Whether this template is a default")


class WritingTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255, description="Template name")
    payload: dict[str, Any] | None = Field(None, description="Template payload JSON")
    schema_version: int | None = Field(None, ge=1, description="Payload schema version")
    version_parent_id: str | None = Field(None, description="Optional parent template ID")
    is_default: bool | None = Field(None, description="Whether this template is a default")


class WritingTemplateResponse(BaseModel):
    id: int
    name: str
    payload: dict[str, Any]
    schema_version: int
    version_parent_id: str | None = None
    is_default: bool
    created_at: datetime
    last_modified: datetime
    deleted: bool
    client_id: str
    version: int


class WritingTemplateListResponse(BaseModel):
    templates: list[WritingTemplateResponse]
    total: int


class WritingThemeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Theme name")
    class_name: str | None = Field(None, description="CSS class name")
    css: str | None = Field(None, description="CSS rules scoped to the playground")
    schema_version: int = Field(1, ge=1, description="Theme schema version")
    version_parent_id: str | None = Field(None, description="Optional parent theme ID")
    is_default: bool = Field(False, description="Whether this theme is a default")
    order: int = Field(0, description="Ordering index")


class WritingThemeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255, description="Theme name")
    class_name: str | None = Field(None, description="CSS class name")
    css: str | None = Field(None, description="CSS rules scoped to the playground")
    schema_version: int | None = Field(None, ge=1, description="Theme schema version")
    version_parent_id: str | None = Field(None, description="Optional parent theme ID")
    is_default: bool | None = Field(None, description="Whether this theme is a default")
    order: int | None = Field(None, description="Ordering index")


class WritingThemeResponse(BaseModel):
    id: int
    name: str
    class_name: str | None = None
    css: str | None = None
    schema_version: int
    version_parent_id: str | None = None
    is_default: bool
    order: int
    created_at: datetime
    last_modified: datetime
    deleted: bool
    client_id: str
    version: int


class WritingThemeListResponse(BaseModel):
    themes: list[WritingThemeResponse]
    total: int


class WritingTokenizeOptions(BaseModel):
    include_strings: bool = Field(True, description="Include decoded token strings")


class WritingTokenizeRequest(BaseModel):
    provider: str = Field(..., min_length=1, description="Provider name")
    model: str = Field(..., min_length=1, description="Model name")
    text: str = Field(..., min_length=1, description="Input text")
    options: WritingTokenizeOptions | None = None


class WritingTokenizeMeta(BaseModel):
    provider: str
    model: str
    tokenizer: str
    input_chars: int
    token_count: int
    warnings: list[str] = Field(default_factory=list)


class WritingTokenizeResponse(BaseModel):
    ids: list[int]
    strings: list[str] | None = None
    meta: WritingTokenizeMeta


class WritingTokenCountRequest(BaseModel):
    provider: str = Field(..., min_length=1, description="Provider name")
    model: str = Field(..., min_length=1, description="Model name")
    text: str = Field(..., min_length=1, description="Input text")


class WritingTokenCountResponse(BaseModel):
    count: int
    meta: WritingTokenizeMeta


class WritingWordcloudOptions(BaseModel):
    max_words: int = Field(100, ge=1, le=1000, description="Maximum number of words to return")
    min_word_length: int = Field(3, ge=1, le=64, description="Minimum token length to include")
    keep_numbers: bool = Field(False, description="Whether to include purely numeric tokens")
    stopwords: list[str] | None = Field(
        None,
        description="Optional stopwords list. Omit to use defaults; use [] to disable stopwords.",
    )


class WritingWordcloudRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Input text to analyze")
    options: WritingWordcloudOptions | None = None


class WritingWordcloudWord(BaseModel):
    text: str
    weight: int


class WritingWordcloudMeta(BaseModel):
    input_chars: int
    total_tokens: int
    top_n: int


class WritingWordcloudResult(BaseModel):
    words: list[WritingWordcloudWord]
    meta: WritingWordcloudMeta


class WritingWordcloudResponse(BaseModel):
    id: str
    status: str
    cached: bool = False
    result: WritingWordcloudResult | None = None
    error: str | None = None


class WritingTokenizerSupport(BaseModel):
    available: bool
    tokenizer: str | None = None
    error: str | None = None


class WritingServerCapabilities(BaseModel):
    sessions: bool
    templates: bool
    themes: bool
    tokenize: bool
    token_count: bool
    wordclouds: bool = False


class WritingProviderCapabilities(BaseModel):
    name: str
    models: list[str]
    capabilities: dict[str, Any]
    supported_fields: list[str]
    features: dict[str, bool]
    tokenizers: dict[str, WritingTokenizerSupport] | None = None


class WritingRequestedCapabilities(BaseModel):
    provider: str
    model: str | None = None
    supported_fields: list[str]
    features: dict[str, bool]
    tokenizer_available: bool
    tokenizer: str | None = None
    tokenization_error: str | None = None


class WritingCapabilitiesResponse(BaseModel):
    version: int
    server: WritingServerCapabilities
    default_provider: str | None = None
    providers: list[WritingProviderCapabilities] | None = None
    requested: WritingRequestedCapabilities | None = None
