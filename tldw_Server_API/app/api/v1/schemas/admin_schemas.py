# admin_schemas.py
# Description: Pydantic schemas for admin endpoints
from __future__ import annotations

from datetime import date, datetime

# Imports
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, NonNegativeInt, field_validator

#######################################################################################################################
#
# User Management Schemas

class UserUpdateRequest(BaseModel):
    """Request to update user information"""
    email: EmailStr | None = None
    role: str | None = Field(None, pattern="^(user|admin|service)$")
    is_active: bool | None = None
    is_verified: bool | None = None
    is_locked: bool | None = None
    storage_quota_mb: int | None = Field(None, ge=100)

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
    storage_quota_mb: int | None = Field(None, ge=100)

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
    last_login: datetime | None = None
    storage_quota_mb: int
    storage_used_mb: float

    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(BaseModel):
    """Detailed user information for admin endpoints."""

    id: int
    uuid: UUID | None = None
    username: str
    email: str
    role: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_verified: bool | None = None
    email_verified: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login: datetime | None = None
    storage_quota_mb: int | None = None
    storage_used_mb: float | None = None
    is_locked: bool | None = None
    failed_login_attempts: int | None = None
    locked_until: datetime | None = None
    metadata: Any | None = None

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Response for user list endpoint"""
    users: list[UserSummary]
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
    allowed_email_domain: str | None = Field(
        None,
        pattern=r"^@?[A-Za-z0-9.-]+$",
    )
    metadata: dict[str, Any] | None = None
    org_id: int | None = Field(None, ge=1)
    org_role: str | None = Field(None, pattern=r"^(owner|admin|lead|member)$")
    team_id: int | None = Field(None, ge=1)

    model_config = ConfigDict(from_attributes=True)


class RegistrationCodeResponse(BaseModel):
    """Response with registration code details"""
    id: int
    code: str
    max_uses: int
    times_used: int
    expires_at: datetime
    created_at: datetime
    created_by: int | None = None
    role_to_grant: str
    allowed_email_domain: str | None = None
    org_id: int | None = None
    org_role: str | None = None
    team_id: int | None = None
    org_name: str | None = None
    metadata: dict[str, Any] | None = None
    is_active: bool | None = None
    is_valid: bool | None = None

    model_config = ConfigDict(from_attributes=True)

    def __init__(self, **data):
        super().__init__(**data)
        # Calculate is_valid if not provided
        if self.is_valid is None:
            is_active = True if self.is_active is None else bool(self.is_active)
            self.is_valid = is_active and self.times_used < self.max_uses and self.expires_at > datetime.utcnow()


class RegistrationCodeListResponse(BaseModel):
    """Response for registration code list"""
    codes: list[RegistrationCodeResponse]

    model_config = ConfigDict(from_attributes=True)


class RegistrationSettingsResponse(BaseModel):
    """Registration configuration status for admin surfaces."""
    enable_registration: bool
    require_registration_code: bool
    auth_mode: str | None = None
    profile: str | None = None
    self_registration_allowed: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class RegistrationSettingsUpdateRequest(BaseModel):
    """Request to update registration settings."""
    enable_registration: bool | None = None
    require_registration_code: bool | None = None

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# LLM Provider Overrides Schemas

class LLMProviderOverrideRequest(BaseModel):
    """Request to upsert LLM provider overrides."""
    is_enabled: bool | None = None
    allowed_models: list[str] | None = None
    config: dict[str, Any] | None = None
    api_key: str | None = None
    credential_fields: dict[str, Any] | None = None
    clear_api_key: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class LLMProviderOverrideResponse(BaseModel):
    """Response payload for LLM provider overrides."""
    provider: str
    is_enabled: bool | None = None
    allowed_models: list[str] | None = None
    config: dict[str, Any] | None = None
    credential_fields: dict[str, Any] | None = None
    has_api_key: bool = False
    api_key_hint: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LLMProviderOverrideListResponse(BaseModel):
    """Response payload for listing LLM provider overrides."""
    items: list[LLMProviderOverrideResponse]

    model_config = ConfigDict(from_attributes=True)


class LLMProviderTestRequest(BaseModel):
    """Request to test LLM provider connectivity."""
    provider: str
    model: str | None = None
    api_key: str | None = None
    credential_fields: dict[str, Any] | None = None
    use_override: bool = True

    model_config = ConfigDict(from_attributes=True)


class LLMProviderTestResponse(BaseModel):
    """Response payload for LLM provider test results."""
    provider: str
    status: str
    model: str | None = None

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
    points: list[ActivityPoint]
    warnings: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Security Alert Schemas

class SecurityAlertSinkStatus(BaseModel):
    """Represents the status of an individual security alert sink."""
    sink: str
    configured: bool
    min_severity: str | None = None
    last_status: bool | None = None
    last_error: str | None = None
    backoff_until: datetime | None = None


class SecurityAlertStatusResponse(BaseModel):
    """Aggregated security alert configuration and health."""
    enabled: bool
    min_severity: str
    last_dispatch_time: datetime | None
    last_dispatch_success: bool | None
    last_dispatch_error: str | None = None
    dispatch_count: int
    last_validation_time: datetime | None
    validation_errors: list[str] | None = None
    sinks: list[SecurityAlertSinkStatus]
    health: str

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Audit Log Schemas

class AuditLogEntry(BaseModel):
    """Single audit log entry"""
    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    resource: str | None = None
    details: Any | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    """Response for audit log endpoint"""
    entries: list[AuditLogEntry]
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
    user_id: int | None = None
    status: str = "ready"
    size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupListResponse(BaseModel):
    """Response for backup listing."""
    items: list[BackupItem]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class BackupCreateRequest(BaseModel):
    """Request to create a backup snapshot."""
    dataset: str
    user_id: int | None = None
    backup_type: str | None = Field("full", pattern="^(full|incremental)$")
    max_backups: int | None = Field(None, ge=1, le=1000)

    model_config = ConfigDict(from_attributes=True)


class BackupCreateResponse(BaseModel):
    """Response for backup creation."""
    item: BackupItem

    model_config = ConfigDict(from_attributes=True)


class BackupRestoreRequest(BaseModel):
    """Request to restore a backup snapshot."""
    dataset: str
    user_id: int | None = None
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
    days: int | None = None
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RetentionPoliciesResponse(BaseModel):
    """Response for retention policy listing."""
    policies: list[RetentionPolicy]

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
    timestamp: datetime | None = None
    level: str | None = None
    message: str | None = None
    logger: str | None = None
    module: str | None = None
    function: str | None = None
    line: int | None = None
    request_id: str | None = None
    org_id: int | None = None
    user_id: int | None = None
    trace_id: str | None = None
    span_id: str | None = None
    correlation_id: str | None = None
    event: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SystemLogsResponse(BaseModel):
    """Response for system log listing."""
    items: list[SystemLogEntry]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class MaintenanceState(BaseModel):
    """Maintenance mode state."""
    enabled: bool
    message: str = ""
    allowlist_user_ids: list[int] = []
    allowlist_emails: list[str] = []
    updated_at: datetime | None = None
    updated_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MaintenanceUpdateRequest(BaseModel):
    """Request to update maintenance mode."""
    enabled: bool
    message: str | None = None
    allowlist_user_ids: list[int] | None = None
    allowlist_emails: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagHistoryEntry(BaseModel):
    """Feature flag change history entry."""
    timestamp: datetime
    enabled: bool
    actor: str | None = None
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagItem(BaseModel):
    """Feature flag descriptor."""
    key: str
    scope: Literal["global", "org", "user"]
    enabled: bool
    description: str | None = None
    org_id: int | None = None
    user_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None
    history: list[FeatureFlagHistoryEntry] = []

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagsResponse(BaseModel):
    """Response for feature flag listing."""
    items: list[FeatureFlagItem]
    total: int

    model_config = ConfigDict(from_attributes=True)


class FeatureFlagUpsertRequest(BaseModel):
    """Request to upsert a feature flag."""
    scope: Literal["global", "org", "user"]
    enabled: bool
    description: str | None = None
    org_id: int | None = None
    user_id: int | None = None
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class IncidentEvent(BaseModel):
    """Incident timeline entry."""
    id: str
    message: str
    created_at: datetime
    actor: str | None = None

    model_config = ConfigDict(from_attributes=True)


class IncidentItem(BaseModel):
    """Incident summary with timeline."""
    id: str
    title: str
    status: Literal["open", "investigating", "mitigating", "resolved"]
    severity: Literal["low", "medium", "high", "critical"]
    summary: str | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    timeline: list[IncidentEvent] = []

    model_config = ConfigDict(from_attributes=True)


class IncidentListResponse(BaseModel):
    """Response for incident listing."""
    items: list[IncidentItem]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class IncidentCreateRequest(BaseModel):
    """Request to create an incident."""
    title: str
    status: Literal["open", "investigating", "mitigating", "resolved"] | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    summary: str | None = None
    tags: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)


class IncidentUpdateRequest(BaseModel):
    """Request to update an incident."""
    title: str | None = None
    status: Literal["open", "investigating", "mitigating", "resolved"] | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    summary: str | None = None
    tags: list[str] | None = None
    update_message: str | None = None

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
    user_ids: list[int]
    operation: str = Field(..., pattern="^(activate|deactivate|verify|lock|unlock|delete)$")

    model_config = ConfigDict(from_attributes=True)


class BatchOperationResponse(BaseModel):
    """Response for batch operations"""
    success_count: int
    failed_count: int
    failed_ids: list[int] = []
    message: str

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Usage Reporting Schemas

class UsageDailyRow(BaseModel):
    """Single usage_daily record."""
    user_id: int
    day: date | str
    requests: int
    errors: int
    bytes_total: int
    bytes_in_total: int | None = None
    latency_avg_ms: float | None = None

    model_config = ConfigDict(from_attributes=True)


class UsageDailyResponse(BaseModel):
    """Response for daily usage query."""
    items: list[UsageDailyRow]
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
    bytes_in_total: int | None = None
    latency_avg_ms: float | None = None

    model_config = ConfigDict(from_attributes=True)


class UsageTopResponse(BaseModel):
    items: list[UsageTopRow]

    model_config = ConfigDict(from_attributes=True)


class UsageAggregateResponse(BaseModel):
    """Response for manual usage aggregation."""
    status: str
    day: str | None = None
    reason: str | None = None

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


def _normalize_threshold_list(values: list[Any]) -> list[int]:
    if not values:
        raise ValueError("Alert thresholds must not be empty")
    cleaned: list[int] = []
    for val in values:
        try:
            num = int(val)
        except (TypeError, ValueError) as exc:
            raise ValueError("Alert thresholds must be integers") from exc
        if num < 1 or num > 100:
            raise ValueError("Alert thresholds must be between 1 and 100")
        cleaned.append(num)
    return sorted(set(cleaned))


def _validate_usd_precision(value: Any | None) -> float | None:
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
    global_: list[int] | None = Field(default=None, alias="global")
    per_metric: dict[str, list[int] | None] | None = None

    @field_validator("global_")
    @classmethod
    def validate_global_thresholds(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        return _normalize_threshold_list(v)

    @field_validator("per_metric")
    @classmethod
    def validate_per_metric_thresholds(
        cls, v: dict[str, list[int] | None] | None
    ) -> dict[str, list[int] | None] | None:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Per-metric thresholds must be a mapping")
        cleaned: dict[str, list[int] | None] = {}
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
    global_: Literal["none", "soft", "hard"] | None = Field(default=None, alias="global")
    per_metric: dict[str, Literal["none", "soft", "hard"] | None] | None = None

    @field_validator("per_metric")
    @classmethod
    def validate_per_metric_modes(
        cls, v: dict[str, Literal["none", "soft", "hard"] | None] | None
    ) -> dict[str, Literal["none", "soft", "hard"] | None] | None:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("Per-metric enforcement must be a mapping")
        cleaned: dict[str, Literal["none", "soft", "hard"] | None] = {}
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
    budget_day_usd: float | None = Field(None, ge=0)
    budget_month_usd: float | None = Field(None, ge=0)
    budget_day_tokens: int | None = Field(None, ge=0)
    budget_month_tokens: int | None = Field(None, ge=0)
    alert_thresholds: BudgetAlertThresholds | None = None
    enforcement_mode: BudgetEnforcementMode | None = None

    @field_validator("budget_day_usd", "budget_month_usd", mode="before")
    @classmethod
    def validate_usd_precision(cls, v: Any | None) -> float | None:
        return _validate_usd_precision(v)

    @field_validator("alert_thresholds", mode="before")
    @classmethod
    def coerce_alert_thresholds(cls, v: Any | None) -> Any | None:
        if v is None:
            return v
        if isinstance(v, list):
            return {"global": v}
        return v

    @field_validator("enforcement_mode", mode="before")
    @classmethod
    def coerce_enforcement_mode(cls, v: Any | None) -> Any | None:
        if v is None:
            return v
        if isinstance(v, str):
            return {"global": v}
        return v


class OrgBudgetUpdateRequest(BaseModel):
    """Upsert budget settings for an organization."""
    org_id: int = Field(..., ge=1)
    budgets: BudgetSettings | None = None
    clear_budgets: bool = False


class OrgBudgetSelfUpdateRequest(BaseModel):
    """Upsert budget settings for the current organization context."""
    budgets: BudgetSettings | None = None
    clear_budgets: bool = False


class OrgBudgetItem(BaseModel):
    """Budget details for an organization."""
    org_id: int
    org_name: str
    org_slug: str | None = None
    plan_name: str
    plan_display_name: str
    budgets: BudgetSettings = Field(default_factory=BudgetSettings)
    custom_limits: dict[str, Any] = Field(default_factory=dict)
    effective_limits: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OrgBudgetListResponse(BaseModel):
    items: list[OrgBudgetItem]
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
    user_id: int | None = None
    key_id: int | None = None
    endpoint: str | None = None
    operation: str | None = None
    provider: str | None = None
    model: str | None = None
    status: int | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    currency: str | None = None
    estimated: bool | None = None
    request_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LLMUsageLogResponse(BaseModel):
    items: list[LLMUsageLogRow]
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
    latency_avg_ms: float | None = None

    model_config = ConfigDict(from_attributes=True)


class LLMUsageSummaryResponse(BaseModel):
    items: list[LLMUsageSummaryRow]

    model_config = ConfigDict(from_attributes=True)


class LLMTopSpenderRow(BaseModel):
    user_id: int
    total_cost_usd: float
    requests: int

    model_config = ConfigDict(from_attributes=True)


class LLMTopSpendersResponse(BaseModel):
    items: list[LLMTopSpenderRow]

    model_config = ConfigDict(from_attributes=True)


#######################################################################################################################
#
# Tool Permission Schemas (MCP Integration)

class ToolPermissionCreateRequest(BaseModel):
    """Create a tool execute permission.

    If tool_name is "*", creates tools.execute:* (wildcard).
    """
    tool_name: str = Field(..., min_length=1)
    description: str | None = None


class ToolPermissionResponse(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None


class ToolPermissionGrantRequest(BaseModel):
    """Grant a tool execution permission to a role.

    tool_name '*' means tools.execute:*
    """
    tool_name: str = Field(..., min_length=1)


class ToolPermissionBatchRequest(BaseModel):
    """Grant multiple tool execution permissions to a role in one call."""
    tool_names: list[str] = Field(..., min_length=1)


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
    description: str | None = None
    org_id: int | None = None
    team_id: int | None = None
    is_active: bool | None = True


class ToolCatalogResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    org_id: int | None = None
    team_id: int | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ToolCatalogEntryCreateRequest(BaseModel):
    """Add a tool entry to a catalog."""
    tool_name: str = Field(..., min_length=1, max_length=200)
    module_id: str | None = Field(None, max_length=200)


class ToolCatalogEntryResponse(BaseModel):
    catalog_id: int
    tool_name: str
    module_id: str | None = None

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

    llm_enabled: bool | None = Field(default=None)
    default_strategy: Literal['heuristic', 'llm', 'llm_fallback'] | None = Field(default=None)


class NotesTitleSettingsResponse(BaseModel):
    """Response payload for Notes auto-title settings."""
    llm_enabled: bool
    default_strategy: str
    effective_strategy: str
    strategies: list[str]

    model_config = ConfigDict(from_attributes=True)


#
# Cleanup worker settings (admin)

class AdminCleanupSettingsUpdate(BaseModel):
    """Update payload for ephemeral cleanup worker settings.

    - enabled: turn cleanup worker on/off
    - interval_sec: run interval in seconds (60..604800)
    """
    model_config = ConfigDict(extra='forbid')

    enabled: bool | None = Field(default=None)
    interval_sec: int | None = Field(default=None, ge=60, le=604800)


class AdminCleanupSettingsResponse(BaseModel):
    """Response payload for cleanup worker settings."""
    enabled: bool
    interval_sec: int

    model_config = ConfigDict(from_attributes=True)

#
## End of admin_schemas.py
#######################################################################################################################
