# moderation_schemas.py
# Description: Pydantic models for Moderation admin endpoints

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ModerationUserOverride(BaseModel):
    enabled: Optional[bool] = Field(None, description="Enable moderation for this user")
    input_enabled: Optional[bool] = Field(None, description="Enable input moderation for this user")
    output_enabled: Optional[bool] = Field(None, description="Enable output moderation for this user")
    input_action: Optional[Literal['block', 'redact', 'warn']] = Field(None, description="Action for input violations")
    output_action: Optional[Literal['block', 'redact', 'warn']] = Field(None, description="Action for output violations")
    redact_replacement: Optional[str] = Field(None, description="Replacement text for redaction")
    categories_enabled: Optional[list[str]] = Field(
        None,
        description="Categories to enable for this user (comma-separated string or list, e.g., 'pii,confidential')",
    )

    @field_validator("categories_enabled", mode="before")
    @classmethod
    def _normalize_categories_enabled(cls, v: Any) -> Optional[list[str]]:
        if v is None:
            return None
        if isinstance(v, str):
            tokens = [token.strip() for token in v.split(",")]
            return [token for token in tokens if token]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator('redact_replacement')
    @classmethod
    def _non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("redact_replacement cannot be empty if provided")
        return v


class ModerationBlocklistUpdate(BaseModel):
    lines: list[str] = Field(default_factory=list, description="Blocklist lines; regex lines can be wrapped in /.../")


class ModerationUserOverridesResponse(BaseModel):
    overrides: dict[str, dict[str, Any]]


class BlocklistManagedItem(BaseModel):
    id: int
    line: str


class BlocklistManagedResponse(BaseModel):
    version: str = Field(..., description="Content hash for optimistic concurrency")
    items: list[BlocklistManagedItem]


class BlocklistAppendRequest(BaseModel):
    line: str = Field(..., min_length=1)

    @field_validator("line")
    @classmethod
    def _single_line(cls, v: str) -> str:
        if "\n" in v or "\r" in v:
            raise ValueError("line must be a single line")
        return v


class BlocklistAppendResponse(BaseModel):
    version: str
    index: int
    count: int


class BlocklistDeleteResponse(BaseModel):
    version: str
    count: int


class BlocklistLintRequest(BaseModel):
    lines: Optional[list[str]] = None
    line: Optional[str] = None

    @field_validator('line')
    @classmethod
    def _ensure_any(cls, v, info):
        # Validation occurs after both fields parsed; check neither set later in endpoint
        return v


class BlocklistLintItem(BaseModel):
    index: int
    line: str
    ok: bool
    pattern_type: Optional[Literal['literal', 'regex', 'comment', 'empty']] = None
    action: Optional[Literal['block', 'redact', 'warn']] = None
    replacement: Optional[str] = None
    categories: Optional[list[str]] = None
    error: Optional[str] = None
    warning: Optional[str] = None
    sample: Optional[str] = None


class BlocklistLintResponse(BaseModel):
    items: list[BlocklistLintItem]
    valid_count: int
    invalid_count: int


class ModerationTestRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="User ID to apply effective policy")
    phase: Literal['input', 'output'] = Field('input', description="Moderation phase to test")
    text: str = Field(..., description="Sample text to test against moderation policy")


class ModerationTestResponse(BaseModel):
    flagged: bool
    action: Literal['block', 'redact', 'warn', 'pass']
    sample: Optional[str] = None
    redacted_text: Optional[str] = None
    effective: dict[str, Any]
    category: Optional[str] = None


class ModerationSettingsResponse(BaseModel):
    pii_enabled: Optional[bool] = Field(None, description="Runtime override for pii_enabled or None if not overridden")
    categories_enabled: Optional[list[str]] = Field(None, description="Runtime override for categories_enabled or None if not overridden")
    effective: dict[str, Any] = Field(..., description="Effective settings after merge with config")


class ModerationSettingsUpdate(BaseModel):
    pii_enabled: Optional[bool] = None
    categories_enabled: Optional[list[str]] = None
    persist: Optional[bool] = Field(False, description="Persist runtime overrides to file")
