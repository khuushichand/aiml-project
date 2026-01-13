# admin_schemas.py
# Description: Pydantic schemas for admin endpoints
from __future__ import annotations

# Imports
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, List, Union, Literal
from uuid import UUID
from datetime import datetime, date
from pydantic import BaseModel, Field, EmailStr, ConfigDict, NonNegativeInt, field_validator

#######################################################################################################################
#
# User Management Schemas

class UserUpdateRequest(BaseModel):
    """Request to update user information"""
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(None, pattern="^(user|admin|service)$")
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_locked: Optional[bool] = None
    storage_quota_mb: Optional[int] = Field(None, ge=100)

    model_config = ConfigDict(from_attributes=True)


class AdminUserCreateRequest(BaseModel):
    """Request to create a user as an admin."""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
    )
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)
    role: str = Field("user", pattern="^(user|admin|service)$")
    is_active: bool = True
    is_verified: bool = True
    storage_quota_mb: Optional[int] = Field(None, ge=100)

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        reserved = {"admin", "root", "system", "api", "null", "undefined"}
        normalized = v.strip()
        if normalized.lower() in reserved:
            raise ValueError("This username is reserved")
        return normalized.lower()

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()


class UserSummary(BaseModel):
    """Summary information about a user"""
    id: int
    uuid: UUID
    username: str
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    storage_quota_mb: int
    storage_used_mb: float

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Response for user list endpoint"""
    users: List[UserSummary]
    total: int
    page: int
    limit: int
    pages: int

    model_config = ConfigDict(from_attributes=True)


class UserQuotaUpdateRequest(BaseModel):
    """Request to update user storage quota"""
    storage_quota_mb: int = Field(..., ge=100, le=1000000)  # 100MB to 1TB

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Registration Code Schemas

class RegistrationCodeRequest(BaseModel):
    """Request to create a registration code"""
    max_uses: int = Field(1, ge=1, le=100)
    expiry_days: int = Field(7, ge=1, le=365)
    role_to_grant: str = Field("user", pattern="^(user|admin|service)$")
    allowed_email_domain: Optional[str] = Field(
        None,
        pattern=r"^@?[A-Za-z0-9.-]+$",
    )
    metadata: Optional[Dict[str, Any]] = None
    org_id: Optional[int] = Field(None, ge=1)
    org_role: Optional[str] = Field(None, pattern=r"^(owner|admin|lead|member)$")
    team_id: Optional[int] = Field(None, ge=1)

    model_config = ConfigDict(from_attributes=True)


class RegistrationCodeResponse(BaseModel):
    """Response with registration code details"""
    id: int
    code: str
    max_uses: int
    times_used: int
    expires_at: datetime
    created_at: datetime
    created_by: Optional[int] = None
    role_to_grant: str
    allowed_email_domain: Optional[str] = None
    org_id: Optional[int] = None
    org_role: Optional[str] = None
    team_id: Optional[int] = None
    org_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_valid: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

    def __init__(self, **data):
        super().__init__(**data)
        # Calculate is_valid if not provided
        if self.is_valid is None:
            is_active = True if self.is_active is None else bool(self.is_active)
            self.is_valid = is_active and self.times_used < self.max_uses and self.expires_at > datetime.utcnow()


class RegistrationCodeListResponse(BaseModel):
    """Response for registration code list"""
    codes: List[RegistrationCodeResponse]

    model_config = ConfigDict(from_attributes=True)


class RegistrationSettingsResponse(BaseModel):
    """Registration configuration status for admin surfaces."""
    enable_registration: bool
    require_registration_code: bool
    auth_mode: Optional[str] = None
    profile: Optional[str] = None
    self_registration_allowed: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class RegistrationSettingsUpdateRequest(BaseModel):
    """Request to update registration settings."""
    enable_registration: Optional[bool] = None
    require_registration_code: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# LLM Provider Overrides Schemas

class LLMProviderOverrideRequest(BaseModel):
    """Request to upsert LLM provider overrides."""
    is_enabled: Optional[bool] = None
    allowed_models: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    api_key: Optional[str] = None
    credential_fields: Optional[Dict[str, Any]] = None
    clear_api_key: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class LLMProviderOverrideResponse(BaseModel):
    """Response payload for LLM provider overrides."""
    provider: str
    is_enabled: Optional[bool] = None
    allowed_models: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    credential_fields: Optional[Dict[str, Any]] = None
    has_api_key: bool = False
    api_key_hint: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LLMProviderOverrideListResponse(BaseModel):
    """Response payload for listing LLM provider overrides."""
    items: List[LLMProviderOverrideResponse]

    model_config = ConfigDict(from_attributes=True)


class LLMProviderTestRequest(BaseModel):
    """Request to test LLM provider connectivity."""
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None
    credential_fields: Optional[Dict[str, Any]] = None
    use_override: bool = True

    model_config = ConfigDict(from_attributes=True)


class LLMProviderTestResponse(BaseModel):
    """Response payload for LLM provider test results."""
    provider: str
    status: str
    model: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# System Statistics Schemas

class UserStats(BaseModel):
    """User statistics"""
    total: int
    active: int
    verified: int
    admins: int
    new_last_30d: int

    model_config = ConfigDict(from_attributes=True)


class StorageStats(BaseModel):
    """Storage statistics"""
    total_used_mb: float
    total_quota_mb: float
    average_used_mb: float
    max_used_mb: float

    model_config = ConfigDict(from_attributes=True)


class SessionStats(BaseModel):
    """Session statistics"""
    active: int
    unique_users: int

    model_config = ConfigDict(from_attributes=True)


class SystemStatsResponse(BaseModel):
    """System statistics response"""
    users: UserStats
    storage: StorageStats
    sessions: SessionStats

    model_config = ConfigDict(from_attributes=True)


class ActivityPoint(BaseModel):
    """Daily activity point for dashboard charts."""
    date: date
    requests: NonNegativeInt
    users: NonNegativeInt

    model_config = ConfigDict(from_attributes=True)


class ActivitySummaryResponse(BaseModel):
    """Dashboard activity summary response."""
    days: int = Field(..., ge=0)
    points: List[ActivityPoint]
    warnings: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Security Alert Schemas

class SecurityAlertSinkStatus(BaseModel):
    """Represents the status of an individual security alert sink."""
    sink: str
    configured: bool
    min_severity: Optional[str] = None
    last_status: Optional[bool] = None
    last_error: Optional[str] = None
    backoff_until: Optional[datetime] = None


class SecurityAlertStatusResponse(BaseModel):
    """Aggregated security alert configuration and health."""
    enabled: bool
    min_severity: str
    last_dispatch_time: Optional[datetime]
    last_dispatch_success: Optional[bool]
    last_dispatch_error: Optional[str] = None
    dispatch_count: int
    last_validation_time: Optional[datetime]
    validation_errors: Optional[List[str]] = None
    sinks: List[SecurityAlertSinkStatus]
    health: str

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Audit Log Schemas

class AuditLogEntry(BaseModel):
    """Single audit log entry"""
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    resource: Optional[str] = None
    details: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    """Response for audit log endpoint"""
    entries: List[AuditLogEntry]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Data Ops Schemas (Backups, Retention, Exports)

class BackupItem(BaseModel):
    """Metadata for a backup artifact."""
    id: str
    dataset: str
    user_id: Optional[int] = None
    status: str = "ready"
    size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupListResponse(BaseModel):
    """Response for backup listing."""
    items: List[BackupItem]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class BackupCreateRequest(BaseModel):
    """Request to create a backup snapshot."""
    dataset: str
    user_id: Optional[int] = None
    backup_type: Optional[str] = Field("full", pattern="^(full|incremental)$")
    max_backups: Optional[int] = Field(None, ge=1, le=1000)

    model_config = ConfigDict(from_attributes=True)


class BackupCreateResponse(BaseModel):
    """Response for backup creation."""
    item: BackupItem

    model_config = ConfigDict(from_attributes=True)


class BackupRestoreRequest(BaseModel):
    """Request to restore a backup snapshot."""
    dataset: str
    user_id: Optional[int] = None
    confirm: bool = False

    model_config = ConfigDict(from_attributes=True)


class BackupRestoreResponse(BaseModel):
    """Response for backup restore."""
    status: str
    message: str

    model_config = ConfigDict(from_attributes=True)


class RetentionPolicy(BaseModel):
    """Retention policy descriptor."""
    key: str
    days: Optional[int] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RetentionPoliciesResponse(BaseModel):
    """Response for retention policy listing."""
    policies: List[RetentionPolicy]

    model_config = ConfigDict(from_attributes=True)


class RetentionPolicyUpdateRequest(BaseModel):
    """Request to update a retention policy."""
    days: int = Field(..., ge=1, le=3650)

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# System Ops Schemas (Logs, Incidents, Maintenance, Feature Flags)

class SystemLogEntry(BaseModel):
    """Single system log entry."""
    timestamp: Optional[datetime] = None
    level: Optional[str] = None
    message: Optional[str] = None
    logger: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    request_id: Optional[str] = None
    org_id: Optional[int] = None
    user_id: Optional[int] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    correlation_id: Optional[str] = None
    event: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SystemLogsResponse(BaseModel):
    """Response for system log listing."""
    items: List[SystemLogEntry]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class MaintenanceState(BaseModel):
    """Maintenance mode state."""
    enabled: bool
    message: str = ""
    allowlist_user_ids: List[int] = []
    allowlist_emails: List[str] = []
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MaintenanceUpdateRequest(BaseModel):
    """Request to update maintenance mode."""
    enabled: bool
    message: Optional[str] = None
    allowlist_user_ids: Optional[List[int]] = None
    allowlist_emails: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagHistoryEntry(BaseModel):
    """Feature flag change history entry."""
    timestamp: datetime
    enabled: bool
    actor: Optional[str] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagItem(BaseModel):
    """Feature flag descriptor."""
    key: str
    scope: Literal["global", "org", "user"]
    enabled: bool
    description: Optional[str] = None
    org_id: Optional[int] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    history: List[FeatureFlagHistoryEntry] = []

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagsResponse(BaseModel):
    """Response for feature flag listing."""
    items: List[FeatureFlagItem]
    total: int

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagUpsertRequest(BaseModel):
    """Request to upsert a feature flag."""
    scope: Literal["global", "org", "user"]
    enabled: bool
    description: Optional[str] = None
    org_id: Optional[int] = None
    user_id: Optional[int] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentEvent(BaseModel):
    """Incident timeline entry."""
    id: str
    message: str
    created_at: datetime
    actor: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentItem(BaseModel):
    """Incident summary with timeline."""
    id: str
    title: str
    status: Literal["open", "investigating", "mitigating", "resolved"]
    severity: Literal["low", "medium", "high", "critical"]
    summary: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    timeline: List[IncidentEvent] = []

    model_config = ConfigDict(from_attributes=True)


class IncidentListResponse(BaseModel):
    """Response for incident listing."""
    items: List[IncidentItem]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class IncidentCreateRequest(BaseModel):
    """Request to create an incident."""
    title: str
    status: Optional[Literal["open", "investigating", "mitigating", "resolved"]] = None
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentUpdateRequest(BaseModel):
    """Request to update an incident."""
    title: Optional[str] = None
    status: Optional[Literal["open", "investigating", "mitigating", "resolved"]] = None
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    update_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentEventCreateRequest(BaseModel):
    """Request to append a timeline entry."""
    message: str

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Batch Operation Schemas

class BatchUserOperation(BaseModel):
    """Batch operation on multiple users"""
    user_ids: List[int]
    operation: str = Field(..., pattern="^(activate|deactivate|verify|lock|unlock|delete)$")

    model_config = ConfigDict(from_attributes=True)


class BatchOperationResponse(BaseModel):
    """Response for batch operations"""
    success_count: int
    failed_count: int
    failed_ids: List[int] = []
    message: str

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Usage Reporting Schemas

class UsageDailyRow(BaseModel):
    """Single usage_daily record."""
    user_id: int
    day: Union[date, str]
    requests: int
    errors: int
    bytes_total: int
    bytes_in_total: Optional[int] = None
    latency_avg_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class UsageDailyResponse(BaseModel):
    """Response for daily usage query."""
    items: List[UsageDailyRow]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class UsageTopRow(BaseModel):
    """Aggregated usage by user for a date range."""
    user_id: int
    requests: int
    errors: int
    bytes_total: int
    bytes_in_total: Optional[int] = None
    latency_avg_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class UsageTopResponse(BaseModel):
    items: List[UsageTopRow]

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Budget Governance Schemas

_BUDGET_FIELD_KEYS = {
    "budget_day_usd",
    "budget_month_usd",
    "budget_day_tokens",
    "budget_month_tokens",
}


def _normalize_threshold_list(values: List[Any]) -> List[int]:
    if not values:
        raise ValueError("Alert thresholds must not be empty")
    cleaned: List[int] = []
    for val in values:
        try:
            num = int(val)
        except (TypeError, ValueError) as exc:
            raise ValueError("Alert thresholds must be integers") from exc
        if num < 1 or num > 100:
            raise ValueError("Alert thresholds must be between 1 and 100")
        cleaned.append(num)
    return sorted(set(cleaned))


def _validate_usd_precision(value: Optional[Any]) -> Optional[float]:
    if value is None:
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("USD budgets must be valid decimals") from exc
    if dec.as_tuple().exponent < -2:
        raise ValueError("USD budgets must have at most 2 decimal places")
    return float(dec)


class BudgetAlertThresholds(BaseModel):
    """Alert thresholds for budgets (global + per-metric)."""
    global_: Optional[List[int]] = Field(default=None, alias="global")
    per_metric: Optional[Dict[str, Optional[List[int]]]] = None

    @field_validator("global_")
    @classmethod
    def validate_global_thresholds(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is None:
            return v
        return _normalize_threshold_list(v)

    @field_validator("per_metric")
    @classmethod
    def validate_per_metric_thresholds(
        cls, v: Optional[Dict[str, Optional[List[int]]]]
    ) -> Optional[Dict[str, Optional[List[int]]]]:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Per-metric thresholds must be a mapping")
        cleaned: Dict[str, Optional[List[int]]] = {}
        for key, values in v.items():
            if key not in _BUDGET_FIELD_KEYS:
                raise ValueError("Unknown per-metric budget key")
            if values is None:
                cleaned[key] = None
                continue
            cleaned[key] = _normalize_threshold_list(values)
        return cleaned

    model_config = ConfigDict(populate_by_name=True)


class BudgetEnforcementMode(BaseModel):
    """Enforcement mode for budgets (global + per-metric)."""
    global_: Optional[Literal["none", "soft", "hard"]] = Field(default=None, alias="global")
    per_metric: Optional[Dict[str, Optional[Literal["none", "soft", "hard"]]]] = None

    @field_validator("per_metric")
    @classmethod
    def validate_per_metric_modes(
        cls, v: Optional[Dict[str, Optional[Literal["none", "soft", "hard"]]]]
    ) -> Optional[Dict[str, Optional[Literal["none", "soft", "hard"]]]]:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Per-metric enforcement must be a mapping")
        cleaned: Dict[str, Optional[Literal["none", "soft", "hard"]]] = {}
        for key, value in v.items():
            if key not in _BUDGET_FIELD_KEYS:
                raise ValueError("Unknown per-metric budget key")
            if value is None:
                cleaned[key] = None
                continue
            if value not in ("none", "soft", "hard"):
                raise ValueError("Enforcement mode must be none, soft, or hard")
            cleaned[key] = value
        return cleaned

    model_config = ConfigDict(populate_by_name=True)


class BudgetSettings(BaseModel):
    """Budget configuration for an organization."""
    budget_day_usd: Optional[float] = Field(None, ge=0)
    budget_month_usd: Optional[float] = Field(None, ge=0)
    budget_day_tokens: Optional[int] = Field(None, ge=0)
    budget_month_tokens: Optional[int] = Field(None, ge=0)
    alert_thresholds: Optional[BudgetAlertThresholds] = None
    enforcement_mode: Optional[BudgetEnforcementMode] = None

    @field_validator("budget_day_usd", "budget_month_usd", mode="before")
    @classmethod
    def validate_usd_precision(cls, v: Optional[Any]) -> Optional[float]:
        return _validate_usd_precision(v)

    @field_validator("alert_thresholds", mode="before")
    @classmethod
    def coerce_alert_thresholds(cls, v: Optional[Any]) -> Optional[Any]:
        if v is None:
            return v
        if isinstance(v, list):
            return {"global": v}
        return v

    @field_validator("enforcement_mode", mode="before")
    @classmethod
    def coerce_enforcement_mode(cls, v: Optional[Any]) -> Optional[Any]:
        if v is None:
            return v
        if isinstance(v, str):
            return {"global": v}
        return v


class OrgBudgetUpdateRequest(BaseModel):
    """Upsert budget settings for an organization."""
    org_id: int = Field(..., ge=1)
    budgets: Optional[BudgetSettings] = None
    clear_budgets: bool = False


class OrgBudgetSelfUpdateRequest(BaseModel):
    """Upsert budget settings for the current organization context."""
    budgets: Optional[BudgetSettings] = None
    clear_budgets: bool = False


class OrgBudgetItem(BaseModel):
    """Budget details for an organization."""
    org_id: int
    org_name: str
    org_slug: Optional[str] = None
    plan_name: str
    plan_display_name: str
    budgets: BudgetSettings = Field(default_factory=BudgetSettings)
    custom_limits: Dict[str, Any] = Field(default_factory=dict)
    effective_limits: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrgBudgetListResponse(BaseModel):
    items: List[OrgBudgetItem]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# LLM Usage Schemas

class LLMUsageLogRow(BaseModel):
    id: int
    ts: datetime
    user_id: Optional[int] = None
    key_id: Optional[int] = None
    endpoint: Optional[str] = None
    operation: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    status: Optional[int] = None
    latency_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    total_cost_usd: Optional[float] = None
    currency: Optional[str] = None
    estimated: Optional[bool] = None
    request_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LLMUsageLogResponse(BaseModel):
    items: List[LLMUsageLogRow]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class LLMUsageSummaryRow(BaseModel):
    group_value: str
    requests: int
    errors: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_cost_usd: float
    latency_avg_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class LLMUsageSummaryResponse(BaseModel):
    items: List[LLMUsageSummaryRow]

    model_config = ConfigDict(from_attributes=True)


class LLMTopSpenderRow(BaseModel):
    user_id: int
    total_cost_usd: float
    requests: int

    model_config = ConfigDict(from_attributes=True)


class LLMTopSpendersResponse(BaseModel):
    items: List[LLMTopSpenderRow]

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Tool Permission Schemas (MCP Integration)

class ToolPermissionCreateRequest(BaseModel):
    """Create a tool execute permission.

    If tool_name is "*", creates tools.execute:* (wildcard).
    """
    tool_name: str = Field(..., min_length=1)
    description: Optional[str] = None


class ToolPermissionResponse(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None


class ToolPermissionGrantRequest(BaseModel):
    """Grant a tool execution permission to a role.

    tool_name '*' means tools.execute:*
    """
    tool_name: str = Field(..., min_length=1)


class ToolPermissionBatchRequest(BaseModel):
    """Grant multiple tool execution permissions to a role in one call."""
    tool_names: List[str] = Field(..., min_length=1)


class ToolPermissionPrefixRequest(BaseModel):
    """Grant/Revoke all tool permissions matching a name prefix.

    Examples:
      {"prefix": "tools.execute:media."} or {"prefix": "media."}
    """
    prefix: str = Field(..., min_length=1)


#######################################################################################################################
#
# MCP Tool Catalog Schemas

class ToolCatalogCreateRequest(BaseModel):
    """Create a new MCP tool catalog."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    org_id: Optional[int] = None
    team_id: Optional[int] = None
    is_active: Optional[bool] = True


class ToolCatalogResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    org_id: Optional[int] = None
    team_id: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ToolCatalogEntryCreateRequest(BaseModel):
    """Add a tool entry to a catalog."""
    tool_name: str = Field(..., min_length=1, max_length=200)
    module_id: Optional[str] = Field(None, max_length=200)


class ToolCatalogEntryResponse(BaseModel):
    catalog_id: int
    tool_name: str
    module_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


#
# Kanban FTS Maintenance Schema

class KanbanFtsMaintenanceResponse(BaseModel):
    """Response for Kanban FTS maintenance actions."""
    user_id: int
    action: Literal["optimize", "rebuild"]
    status: str = "ok"

#
#
# Notes Title Settings Schema

class NotesTitleSettingsUpdate(BaseModel):
    """Update payload for Notes auto-title settings.

    - llm_enabled: enable/disable LLM-backed title generation
    - default_strategy: default strategy to use when clients send "heuristic"
    """
    model_config = ConfigDict(extra='forbid')

    llm_enabled: Optional[bool] = Field(default=None)
    default_strategy: Optional[Literal['heuristic', 'llm', 'llm_fallback']] = Field(default=None)

#
# Cleanup worker settings (admin)

class AdminCleanupSettingsUpdate(BaseModel):
    """Update payload for ephemeral cleanup worker settings.

    - enabled: turn cleanup worker on/off
    - interval_sec: run interval in seconds (60..604800)
    """
    model_config = ConfigDict(extra='forbid')

    enabled: Optional[bool] = Field(default=None)
    interval_sec: Optional[int] = Field(default=None, ge=60, le=604800)

#
## End of admin_schemas.py
#######################################################################################################################
