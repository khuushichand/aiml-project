"""
Pydantic schemas for Persona Agent API.

Scaffold only - minimal models to enable endpoint stubs.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator


PersonaMode = Literal["session_scoped", "persistent_scoped"]
PersonaScopeRuleType = Literal["conversation_id", "character_id", "media_id", "media_tag", "note_id"]
PersonaPolicyRuleKind = Literal["mcp_tool", "skill"]
PersonaSessionStatus = Literal["active", "paused", "closed", "archived"]
PersonaExemplarKind = Literal["style", "catchphrase", "boundary", "scenario_demo", "tool_behavior"]
PersonaExemplarSourceType = Literal["manual", "transcript_import", "character_seed", "generated_candidate"]
PersonaExemplarReviewAction = Literal["approve", "reject"]
PersonaConfirmationMode = Literal["always", "destructive_only", "never"]


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
    surface: str | None = Field(default=None, max_length=120)

    @field_validator("project_id", "resume_session_id", "surface", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


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


class PersonaVoiceDefaults(BaseModel):
    stt_language: str | None = None
    stt_model: str | None = None
    tts_provider: str | None = None
    tts_voice: str | None = None
    confirmation_mode: PersonaConfirmationMode | None = None
    voice_chat_trigger_phrases: list[str] = Field(default_factory=list)
    auto_resume: bool | None = None
    barge_in: bool | None = None
    auto_commit_enabled: bool | None = None
    vad_threshold: float | None = None
    min_silence_ms: int | None = None
    turn_stop_secs: float | None = None
    min_utterance_secs: float | None = None

    @field_validator("stt_language", "stt_model", "tts_provider", "tts_voice", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("voice_chat_trigger_phrases", mode="before")
    @classmethod
    def _normalize_trigger_phrases(cls, value: Any) -> list[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        seen: set[str] = set()
        normalized: list[str] = []
        for item in items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    @field_validator("vad_threshold", "turn_stop_secs", "min_utterance_secs", mode="before")
    @classmethod
    def _normalize_turn_detection_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        if value is None or value == "":
            return None
        bounds = {
            "vad_threshold": (0.0, 1.0),
            "turn_stop_secs": (0.05, 10.0),
            "min_utterance_secs": (0.0, 10.0),
        }
        min_value, max_value = bounds[info.field_name]
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return max(min_value, min(max_value, numeric))

    @field_validator("min_silence_ms", mode="before")
    @classmethod
    def _normalize_min_silence_ms(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return None
        return max(50, min(10_000, numeric))


class PersonaProfileCreate(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    character_card_id: int | None = None
    mode: PersonaMode = "session_scoped"
    system_prompt: str | None = None
    is_active: bool = True
    use_persona_state_context_default: bool = True
    voice_defaults: PersonaVoiceDefaults = Field(default_factory=PersonaVoiceDefaults)


class PersonaProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    character_card_id: int | None = None
    mode: PersonaMode | None = None
    system_prompt: str | None = None
    is_active: bool | None = None
    use_persona_state_context_default: bool | None = None
    voice_defaults: PersonaVoiceDefaults | None = None


class PersonaProfileResponse(BaseModel):
    id: str
    name: str
    character_card_id: int | None = None
    origin_character_id: int | None = None
    origin_character_name: str | None = None
    origin_character_snapshot_at: str | None = None
    mode: PersonaMode
    system_prompt: str | None = None
    is_active: bool = True
    use_persona_state_context_default: bool = True
    voice_defaults: PersonaVoiceDefaults = Field(default_factory=PersonaVoiceDefaults)
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


class PersonaExemplarCreate(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=200)
    kind: PersonaExemplarKind = "style"
    content: str = Field(..., min_length=1, max_length=20_000)
    tone: str | None = Field(default=None, min_length=1, max_length=200)
    scenario_tags: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    source_type: PersonaExemplarSourceType = "manual"
    source_ref: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=10_000)


class PersonaExemplarUpdate(BaseModel):
    kind: PersonaExemplarKind | None = None
    content: str | None = Field(default=None, min_length=1, max_length=20_000)
    tone: str | None = Field(default=None, min_length=1, max_length=200)
    scenario_tags: list[str] | None = None
    capability_tags: list[str] | None = None
    priority: int | None = None
    enabled: bool | None = None
    source_type: PersonaExemplarSourceType | None = None
    source_ref: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=10_000)


class PersonaExemplarResponse(BaseModel):
    id: str
    persona_id: str
    user_id: str
    kind: PersonaExemplarKind
    content: str
    tone: str | None = None
    scenario_tags: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    source_type: PersonaExemplarSourceType
    source_ref: str | None = None
    notes: str | None = None
    created_at: str
    last_modified: str
    deleted: bool = False
    version: int = 1


class PersonaExemplarImportRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=100_000)
    source_ref: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=10_000)
    max_candidates: int = Field(default=5, ge=1, le=10)


class PersonaExemplarReviewRequest(BaseModel):
    action: PersonaExemplarReviewAction
    notes: str | None = Field(default=None, max_length=10_000)


class PersonaExemplarDeleteResponse(BaseModel):
    status: str
    persona_id: str
    exemplar_id: str


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


class PersonaConnectionCreate(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    base_url: str = Field(..., min_length=1, max_length=2048)
    auth_type: str = Field(default="none", min_length=1, max_length=64)
    secret: str | None = Field(default=None, min_length=1, max_length=8192)
    headers_template: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = Field(default=15_000, ge=100, le=120_000)


class PersonaConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    auth_type: str | None = Field(default=None, min_length=1, max_length=64)
    secret: str | None = Field(default=None, min_length=1, max_length=8192)
    clear_secret: bool = False
    headers_template: dict[str, str] | None = None
    timeout_ms: int | None = Field(default=None, ge=100, le=120_000)


class PersonaConnectionResponse(BaseModel):
    id: str
    persona_id: str
    name: str
    base_url: str
    auth_type: str
    headers_template: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int
    allowed_hosts: list[str] = Field(default_factory=list)
    secret_configured: bool = False
    key_hint: str | None = None
    created_at: str | None = None
    last_modified: str | None = None


class PersonaConnectionDeleteResponse(BaseModel):
    status: str
    persona_id: str
    connection_id: str


class PersonaConnectionTestRequest(BaseModel):
    method: str = Field(default="GET", min_length=1, max_length=16)
    path: str | None = Field(default=None, max_length=2048)
    payload: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    auth_header_name: str | None = Field(default=None, min_length=1, max_length=256)


class PersonaConnectionTestResponse(BaseModel):
    ok: bool
    connection_id: str
    method: str
    url: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_payload: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int
    status_code: int | None = None
    body_preview: Any = None
    latency_ms: int | None = None
    error: str | None = None


class PersonaCommandDryRunRequest(BaseModel):
    heard_text: str = Field(..., min_length=1, max_length=20_000)


class PersonaCommandPlannedActionResponse(BaseModel):
    target_type: str
    target_name: str | None = None
    payload_preview: dict[str, Any] = Field(default_factory=dict)


class PersonaCommandSafetyGateResponse(BaseModel):
    classification: str
    requires_confirmation: bool
    reason: str


class PersonaCommandDryRunResponse(BaseModel):
    heard_text: str
    matched: bool
    match_reason: str | None = None
    command_id: str | None = None
    command_name: str | None = None
    connection_id: str | None = None
    connection_status: Literal["ok", "missing"] | None = None
    connection_name: str | None = None
    extracted_params: dict[str, Any] = Field(default_factory=dict)
    planned_action: PersonaCommandPlannedActionResponse | None = None
    safety_gate: PersonaCommandSafetyGateResponse | None = None
    fallback_to_persona_planner: bool = False
    failure_phase: str | None = None


class PersonaVoiceCommandAnalyticsItem(BaseModel):
    command_id: str
    command_name: str | None = None
    total_invocations: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_response_time_ms: float = 0.0
    last_used: str | None = None


class PersonaVoiceFallbackAnalytics(BaseModel):
    total_invocations: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_response_time_ms: float = 0.0
    last_used: str | None = None


class PersonaVoiceAnalyticsSummary(BaseModel):
    total_events: int = 0
    direct_command_count: int = 0
    planner_fallback_count: int = 0
    success_rate: float = 0.0
    fallback_rate: float = 0.0
    avg_response_time_ms: float = 0.0


class PersonaLiveVoiceAnalyticsSummary(BaseModel):
    total_committed_turns: int = 0
    vad_auto_commit_count: int = 0
    manual_commit_count: int = 0
    vad_auto_rate: float = 0.0
    manual_commit_rate: float = 0.0
    degraded_session_count: int = 0


class PersonaVoiceAnalyticsResponse(BaseModel):
    persona_id: str
    summary: PersonaVoiceAnalyticsSummary
    live_voice: PersonaLiveVoiceAnalyticsSummary = Field(
        default_factory=PersonaLiveVoiceAnalyticsSummary
    )
    commands: list[PersonaVoiceCommandAnalyticsItem] = Field(default_factory=list)
    fallbacks: PersonaVoiceFallbackAnalytics = Field(
        default_factory=PersonaVoiceFallbackAnalytics
    )
