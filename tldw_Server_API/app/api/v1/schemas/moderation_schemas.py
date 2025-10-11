# moderation_schemas.py
# Description: Pydantic models for Moderation admin endpoints

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ModerationUserOverride(BaseModel):
    enabled: Optional[bool] = Field(None, description="Enable moderation for this user")
    input_enabled: Optional[bool] = Field(None, description="Enable input moderation for this user")
    output_enabled: Optional[bool] = Field(None, description="Enable output moderation for this user")
    input_action: Optional[Literal['block', 'redact', 'warn']] = Field(None, description="Action for input violations")
    output_action: Optional[Literal['block', 'redact', 'warn']] = Field(None, description="Action for output violations")
    redact_replacement: Optional[str] = Field(None, description="Replacement text for redaction")

    @field_validator('redact_replacement')
    @classmethod
    def _non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("redact_replacement cannot be empty if provided")
        return v


class ModerationBlocklistUpdate(BaseModel):
    lines: List[str] = Field(default_factory=list, description="Blocklist lines; regex lines can be wrapped in /.../")


class ModerationUserOverridesResponse(BaseModel):
    overrides: Dict[str, Dict[str, Any]]


class BlocklistManagedItem(BaseModel):
    id: int
    line: str


class BlocklistManagedResponse(BaseModel):
    version: str = Field(..., description="Content hash for optimistic concurrency")
    items: List[BlocklistManagedItem]


class BlocklistAppendRequest(BaseModel):
    line: str = Field(..., min_length=1)


class BlocklistAppendResponse(BaseModel):
    version: str
    index: int
    count: int


class BlocklistDeleteResponse(BaseModel):
    version: str
    count: int

