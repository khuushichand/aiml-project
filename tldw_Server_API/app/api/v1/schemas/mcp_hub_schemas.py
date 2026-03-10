from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ScopeType = Literal["global", "org", "team", "user"]
ProfileMode = Literal["preset", "custom"]
AssignmentTargetType = Literal["default", "group", "persona"]
PolicyProvenanceSourceKind = Literal["profile", "assignment_inline", "assignment_override"]
PolicyProvenanceEffect = Literal["merged", "replaced"]
ApprovalMode = Literal[
    "allow_silently",
    "ask_every_time",
    "ask_outside_profile",
    "ask_on_sensitive_actions",
    "temporary_elevation_allowed",
]
ApprovalDecision = Literal["approved", "denied"]
ApprovalDuration = Literal["once", "session", "conversation"]
ToolRiskClass = Literal["low", "medium", "high", "unclassified"]
ToolMetadataSource = Literal["explicit", "heuristic", "fallback"]
PathScopeMode = Literal["none", "workspace_root", "cwd_descendants"]
PathScopeEnforcement = Literal["approval_required_when_unenforceable"]


class ACPProfileCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    profile: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ACPProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType | None = None
    owner_scope_id: int | None = None
    profile: dict[str, Any] | None = None
    is_active: bool | None = None


class ACPProfileResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    profile: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class PermissionProfileCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    mode: ProfileMode = "custom"
    policy_document: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PermissionProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType | None = None
    owner_scope_id: int | None = None
    mode: ProfileMode | None = None
    policy_document: dict[str, Any] | None = None
    is_active: bool | None = None


class PermissionProfileResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    mode: ProfileMode
    policy_document: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class PolicyAssignmentCreateRequest(BaseModel):
    target_type: AssignmentTargetType
    target_id: str | None = Field(default=None, max_length=200)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    profile_id: int | None = None
    inline_policy_document: dict[str, Any] = Field(default_factory=dict)
    approval_policy_id: int | None = None
    is_active: bool = True


class PolicyAssignmentUpdateRequest(BaseModel):
    target_type: AssignmentTargetType | None = None
    target_id: str | None = Field(default=None, max_length=200)
    owner_scope_type: ScopeType | None = None
    owner_scope_id: int | None = None
    profile_id: int | None = None
    inline_policy_document: dict[str, Any] | None = None
    approval_policy_id: int | None = None
    is_active: bool | None = None


class PolicyAssignmentResponse(BaseModel):
    id: int
    target_type: AssignmentTargetType
    target_id: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    profile_id: int | None = None
    inline_policy_document: dict[str, Any] = Field(default_factory=dict)
    approval_policy_id: int | None = None
    is_active: bool
    has_override: bool = False
    override_id: int | None = None
    override_active: bool = False
    override_updated_at: datetime | str | None = None
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class PolicyOverrideUpsertRequest(BaseModel):
    override_policy_document: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PolicyOverrideResponse(BaseModel):
    id: int
    assignment_id: int
    override_policy_document: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class ApprovalPolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    mode: ApprovalMode
    rules: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ApprovalPolicyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType | None = None
    owner_scope_id: int | None = None
    mode: ApprovalMode | None = None
    rules: dict[str, Any] | None = None
    is_active: bool | None = None


class ApprovalPolicyResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    mode: ApprovalMode
    rules: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class ApprovalDecisionCreateRequest(BaseModel):
    approval_policy_id: int | None = None
    context_key: str = Field(..., min_length=1, max_length=255)
    conversation_id: str | None = Field(default=None, max_length=255)
    tool_name: str = Field(..., min_length=1, max_length=255)
    scope_key: str = Field(..., min_length=1, max_length=255)
    decision: ApprovalDecision
    duration: ApprovalDuration = "once"


class ApprovalDecisionResponse(BaseModel):
    id: int
    approval_policy_id: int | None = None
    context_key: str
    conversation_id: str | None = None
    tool_name: str
    scope_key: str
    decision: ApprovalDecision
    consume_on_match: bool = False
    expires_at: datetime | str | None = None
    consumed_at: datetime | str | None = None
    created_by: int | None = None
    created_at: datetime | str | None = None


class EffectivePolicySourceResponse(BaseModel):
    assignment_id: int
    target_type: AssignmentTargetType
    target_id: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    profile_id: int | None = None


class EffectivePolicyProvenanceResponse(BaseModel):
    field: str
    value: Any
    source_kind: PolicyProvenanceSourceKind
    assignment_id: int
    profile_id: int | None = None
    override_id: int | None = None
    effect: PolicyProvenanceEffect


class EffectivePolicyResponse(BaseModel):
    enabled: bool
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    approval_policy_id: int | None = None
    approval_mode: ApprovalMode | None = None
    policy_document: dict[str, Any] = Field(default_factory=dict)
    sources: list[EffectivePolicySourceResponse] = Field(default_factory=list)
    provenance: list[EffectivePolicyProvenanceResponse] = Field(default_factory=list)


class ToolRegistryEntryResponse(BaseModel):
    tool_name: str
    display_name: str
    description: str | None = None
    module: str
    module_display_name: str | None = None
    category: str
    risk_class: ToolRiskClass
    capabilities: list[str] = Field(default_factory=list)
    mutates_state: bool = False
    uses_filesystem: bool = False
    uses_processes: bool = False
    uses_network: bool = False
    uses_credentials: bool = False
    supports_arguments_preview: bool = False
    path_boundable: bool = False
    path_argument_hints: list[str] = Field(default_factory=list)
    metadata_source: ToolMetadataSource
    metadata_warnings: list[str] = Field(default_factory=list)


class ToolRegistryModuleResponse(BaseModel):
    module: str
    display_name: str
    tool_count: int
    risk_summary: dict[str, int] = Field(default_factory=dict)
    metadata_warnings: list[str] = Field(default_factory=list)


class ToolRegistrySummaryResponse(BaseModel):
    entries: list[ToolRegistryEntryResponse] = Field(default_factory=list)
    modules: list[ToolRegistryModuleResponse] = Field(default_factory=list)


class ExternalServerCreateRequest(BaseModel):
    server_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)
    transport: str = Field(..., min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    enabled: bool = True


class ExternalServerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    transport: str | None = Field(default=None, min_length=1, max_length=64)
    config: dict[str, Any] | None = None
    owner_scope_type: ScopeType | None = None
    owner_scope_id: int | None = None
    enabled: bool | None = None


class ExternalServerResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    transport: str
    config: dict[str, Any] = Field(default_factory=dict)
    secret_configured: bool
    key_hint: str | None = None
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class ExternalSecretSetRequest(BaseModel):
    secret: str = Field(..., min_length=1, max_length=8192)


class ExternalSecretSetResponse(BaseModel):
    server_id: str
    secret_configured: bool
    key_hint: str | None = None
    updated_at: datetime | str | None = None


class MCPHubDeleteResponse(BaseModel):
    ok: bool
