"""
Pydantic schemas for Persona Agent API.

Scaffold only - minimal models to enable endpoint stubs.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PersonaMode = Literal["session_scoped", "persistent_scoped"]
PersonaScopeRuleType = Literal["conversation_id", "character_id", "media_id", "media_tag", "note_id"]
PersonaPolicyRuleKind = Literal["mcp_tool", "skill"]
PersonaSessionStatus = Literal["active", "paused", "closed", "archived"]


class PersonaInfo(BaseModel):
    id: str
    name: str
    description: str | None = None
    voice: str | None = None
    avatar_url: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    default_tools: list[str] = Field(default_factory=list)


class PersonaSessionRequest(BaseModel):
    persona_id: str
    project_id: str | None = None
    resume_session_id: str | None = None


class PersonaSessionResponse(BaseModel):
    session_id: str
    persona: PersonaInfo
    scopes: list[str] = Field(default_factory=list)
    runtime_mode: PersonaMode | None = None
    scope_snapshot_id: str | None = None
    scope_audit: dict[str, object] = Field(default_factory=dict)


class PersonaSessionSummary(BaseModel):
    session_id: str
    persona_id: str
    created_at: str
    updated_at: str
    turn_count: int = 0
    pending_plan_count: int = 0
    preferences: dict[str, object] = Field(default_factory=dict)
    runtime_mode: PersonaMode | None = None
    status: PersonaSessionStatus | None = None
    reuse_allowed: bool | None = None
    scope_snapshot_id: str | None = None
    scope_audit: dict[str, object] = Field(default_factory=dict)


class PersonaSessionDetail(PersonaSessionSummary):
    turns: list[dict[str, object]] = Field(default_factory=list)


class PersonaProfileCreate(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    character_card_id: int | None = None
    mode: PersonaMode = "session_scoped"
    system_prompt: str | None = None
    is_active: bool = True
    use_persona_state_context_default: bool = True


class PersonaProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    character_card_id: int | None = None
    mode: PersonaMode | None = None
    system_prompt: str | None = None
    is_active: bool | None = None
    use_persona_state_context_default: bool | None = None


class PersonaProfileResponse(BaseModel):
    id: str
    name: str
    character_card_id: int | None = None
    mode: PersonaMode
    system_prompt: str | None = None
    is_active: bool = True
    use_persona_state_context_default: bool = True
    created_at: str
    last_modified: str
    version: int = 1


class PersonaScopeRule(BaseModel):
    rule_type: PersonaScopeRuleType
    rule_value: str = Field(..., min_length=1, max_length=2048)
    include: bool = True


class PersonaScopeRulesReplaceRequest(BaseModel):
    rules: list[PersonaScopeRule] = Field(default_factory=list)


class PersonaScopeRulesResponse(BaseModel):
    persona_id: str
    replaced_count: int | None = None
    rules: list[PersonaScopeRule] = Field(default_factory=list)


class PersonaPolicyRule(BaseModel):
    rule_kind: PersonaPolicyRuleKind
    rule_name: str = Field(..., min_length=1, max_length=512)
    allowed: bool = True
    require_confirmation: bool = False
    max_calls_per_turn: int | None = Field(default=None, ge=1)


class PersonaPolicyRulesReplaceRequest(BaseModel):
    rules: list[PersonaPolicyRule] = Field(default_factory=list)


class PersonaPolicyRulesResponse(BaseModel):
    persona_id: str
    replaced_count: int | None = None
    rules: list[PersonaPolicyRule] = Field(default_factory=list)


class PersonaDeleteResponse(BaseModel):
    status: str
    persona_id: str


class PersonaStateUpdateRequest(BaseModel):
    soul_md: str | None = Field(default=None, max_length=200_000)
    identity_md: str | None = Field(default=None, max_length=200_000)
    heartbeat_md: str | None = Field(default=None, max_length=200_000)


class PersonaStateResponse(BaseModel):
    persona_id: str
    soul_md: str | None = None
    identity_md: str | None = None
    heartbeat_md: str | None = None
    last_modified: str | None = None


PersonaStateField = Literal["soul_md", "identity_md", "heartbeat_md"]


class PersonaStateHistoryItem(BaseModel):
    entry_id: str
    field: PersonaStateField
    content: str
    is_active: bool = True
    created_at: str | None = None
    last_modified: str | None = None
    version: int = 1


class PersonaStateHistoryResponse(BaseModel):
    persona_id: str
    entries: list[PersonaStateHistoryItem] = Field(default_factory=list)


class PersonaStateRestoreRequest(BaseModel):
    entry_id: str = Field(..., min_length=1, max_length=200)
