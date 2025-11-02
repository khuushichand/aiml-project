# admin_schemas.py
# Description: Pydantic schemas for admin endpoints
from __future__ import annotations

# Imports
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import date

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


class UserSummary(BaseModel):
    """Summary information about a user"""
    id: int
    uuid: str
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
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class RegistrationCodeResponse(BaseModel):
    """Response with registration code details"""
    id: int
    code: str
    max_uses: int
    times_used: int
    expires_at: datetime
    created_at: datetime
    role_to_grant: str
    is_valid: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

    def __init__(self, **data):
        super().__init__(**data)
        # Calculate is_valid if not provided
        if self.is_valid is None:
            self.is_valid = (
                self.times_used < self.max_uses and
                self.expires_at > datetime.utcnow()
            )


class RegistrationCodeListResponse(BaseModel):
    """Response for registration code list"""
    codes: List[RegistrationCodeResponse]

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
    details: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    """Response for audit log endpoint"""
    entries: List[AuditLogEntry]

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
# Rate Limit Admin Schemas

class RateLimitResetRequest(BaseModel):
    """Request to reset rate limit counters.

    Provide either a raw identifier or one of ip/user_id/api_key_hash. Optionally include an endpoint
    to limit the reset to one endpoint; omit to reset all endpoints for the identifier.
    """
    kind: Optional[str] = Field(None, pattern="^(ip|user|api|raw)$")
    identifier: Optional[str] = None
    ip: Optional[str] = None
    user_id: Optional[int] = None
    api_key_hash: Optional[str] = None
    endpoint: Optional[str] = None
    dry_run: Optional[bool] = False


class RateLimitResetResponse(BaseModel):
    ok: bool = True
    identifier: str
    endpoint: Optional[str] = None
    note: Optional[str] = None
    db_rows_deleted: int = 0
    redis_keys_deleted: int = 0

#
## End of admin_schemas.py
#######################################################################################################################
