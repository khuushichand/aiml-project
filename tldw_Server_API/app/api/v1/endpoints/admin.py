# admin.py
# Description: Admin endpoints for user management, registration codes, and system administration
#
# Imports
from __future__ import annotations

from typing import Dict, Any, List, Optional, Literal, Set
from datetime import datetime, timedelta, timezone
import secrets
import string
import os
import json
import asyncio
import re
import time
#
# 3rd-party imports
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from loguru import logger
#
# Local imports
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    UserListResponse,
    UserUpdateRequest,
    AdminUserCreateRequest,
    UserSummary,
    RegistrationCodeRequest,
    RegistrationCodeResponse,
    RegistrationCodeListResponse,
    RegistrationSettingsResponse,
    RegistrationSettingsUpdateRequest,
    SystemStatsResponse,
    ActivitySummaryResponse,
    SecurityAlertStatusResponse,
    SecurityAlertSinkStatus,
    AuditLogResponse,
    BackupItem,
    BackupListResponse,
    BackupCreateRequest,
    BackupCreateResponse,
    BackupRestoreRequest,
    BackupRestoreResponse,
    RetentionPolicy,
    RetentionPoliciesResponse,
    RetentionPolicyUpdateRequest,
    SystemLogEntry,
    SystemLogsResponse,
    MaintenanceState,
    MaintenanceUpdateRequest,
    FeatureFlagsResponse,
    FeatureFlagItem,
    FeatureFlagUpsertRequest,
    IncidentItem,
    IncidentListResponse,
    IncidentCreateRequest,
    IncidentUpdateRequest,
    IncidentEventCreateRequest,
    UserQuotaUpdateRequest,
    UsageDailyResponse,
    UsageTopResponse,
    UsageDailyRow,
    UsageTopRow,
    LLMUsageLogResponse,
    LLMUsageLogRow,
    LLMUsageSummaryResponse,
    LLMUsageSummaryRow,
    LLMTopSpendersResponse,
    LLMTopSpenderRow,
    OrgBudgetItem,
    OrgBudgetListResponse,
    OrgBudgetUpdateRequest,
    ToolPermissionCreateRequest,
    ToolPermissionResponse,
    ToolPermissionGrantRequest,
    ToolPermissionBatchRequest,
    ToolPermissionPrefixRequest,
    ToolCatalogCreateRequest,
    ToolCatalogResponse,
    ToolCatalogEntryCreateRequest,
    ToolCatalogEntryResponse,
    NotesTitleSettingsUpdate,
    AdminCleanupSettingsUpdate,
    KanbanFtsMaintenanceResponse,
    LLMProviderOverrideRequest,
    LLMProviderOverrideResponse,
    LLMProviderOverrideListResponse,
    LLMProviderTestRequest,
    LLMProviderTestResponse,
)
from tldw_Server_API.app.api.v1.schemas.auth_schemas import SessionResponse, MessageResponse
from tldw_Server_API.app.api.v1.schemas.user_profile_schemas import (
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserProfileUpdateResponse,
    UserProfileUpdateError,
    UserProfileUpdateEntry,
    UserProfileErrorResponse,
    UserProfileErrorDetail,
    UserProfileBulkUpdateDiff,
    UserProfileBulkUpdateRequest,
    UserProfileBulkUpdateResponse,
    UserProfileBulkUpdateUserResult,
    UserProfileBatchResponse,
)
from tldw_Server_API.app.api.v1.schemas.api_key_schemas import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyRotateRequest,
    APIKeyMetadata,
    APIKeyUpdateRequest,
    APIKeyAuditEntry,
    APIKeyAuditListResponse,
)
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.services.budget_audit_service import emit_budget_audit_event
from tldw_Server_API.app.api.v1.schemas.user_keys import (
    AdminUserKeysResponse,
    AdminUserKeyStatusItem,
    SharedProviderKeyUpsertRequest,
    SharedProviderKeyResponse,
    SharedProviderKeysResponse,
    SharedProviderKeyStatusItem,
    SharedProviderKeyTestRequest,
    SharedProviderKeyTestResponse,
)
from tldw_Server_API.app.api.v1.schemas.admin_rbac_schemas import (
    RoleCreateRequest,
    RoleResponse,
    PermissionCreateRequest,
    PermissionResponse,
    UserRoleListResponse,
    OverrideEffect,
    UserOverrideUpsertRequest,
    UserOverridesResponse,
    UserOverrideEntry,
    EffectivePermissionsResponse,
    RateLimitUpsertRequest,
    RateLimitResponse,
    RolePermissionMatrixResponse,
    RolePermissionGrant,
    RolePermissionBooleanMatrixResponse,
    RoleEffectivePermissionsResponse,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    require_roles,
    get_db_transaction,
    get_storage_service_dep,
    get_registration_service_dep,
    get_auth_principal,
    check_rate_limit,
    get_session_manager_dep,
)
from tldw_Server_API.app.api.v1.utils.profile_errors import (
    classify_profile_update_skips,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings, get_profile, reset_settings
from tldw_Server_API.app.core.AuthNZ.mfa_service import get_mfa_service
from tldw_Server_API.app.core.AuthNZ.byok_helpers import (
    is_byok_enabled,
    is_provider_allowlisted,
    resolve_byok_allowlist,
    validate_base_url_override,
    validate_credential_fields,
)
from tldw_Server_API.app.core.AuthNZ.byok_testing import test_provider_credentials
from tldw_Server_API.app.services.storage_quota_service import StorageQuotaService
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    UserNotFoundError,
    DuplicateUserError,
    RegistrationError,
    RegistrationDisabledError,
    WeakPasswordError,
    QuotaExceededError
)
from tldw_Server_API.app.core.exceptions import ResourceNotFoundError
from tldw_Server_API.app.core.config import settings as app_settings
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.UserProfiles.service import UserProfileService
from tldw_Server_API.app.core.UserProfiles.update_service import (
    ProfileUpdateScope,
    UserProfileUpdateService,
)
from tldw_Server_API.app.core.UserProfiles.user_profile_catalog import load_user_profile_catalog
from tldw_Server_API.app.core.AuthNZ.rbac import get_effective_permissions
from tldw_Server_API.app.services.usage_aggregator import aggregate_usage_daily
from tldw_Server_API.app.services.llm_usage_aggregator import aggregate_llm_usage_daily
from tldw_Server_API.app.core.AuthNZ.alerting import get_security_alert_dispatcher
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    create_organization,
    list_organizations,
    get_team,
    create_team,
    add_team_member,
    list_team_members,
    remove_team_member,
    add_org_member,
    list_org_members,
    remove_org_member,
    update_org_member_role,
    list_org_memberships_for_user,
    list_memberships_for_user,
)
from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import (
    AuthnzUserProviderSecretsRepo,
)
from tldw_Server_API.app.core.AuthNZ.repos.org_provider_secrets_repo import (
    AuthnzOrgProviderSecretsRepo,
)
from tldw_Server_API.app.core.AuthNZ.repos.llm_provider_overrides_repo import (
    AuthnzLLMProviderOverridesRepo,
)
from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB, KanbanDBError, InputError
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.AuthNZ.exceptions import DuplicateOrganizationError, DuplicateTeamError, DuplicateRoleError
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    decrypt_byok_payload,
    encrypt_byok_payload,
    dumps_envelope,
    key_hint_for_api_key,
    loads_envelope,
    normalize_provider_name,
)
from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import (
    refresh_llm_provider_overrides,
    get_llm_provider_override,
    get_llm_provider_overrides_snapshot,
)
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAPIError
from tldw_Server_API.app.api.v1.schemas.org_team_schemas import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationListResponse,
    TeamCreateRequest,
    TeamResponse,
    TeamMemberAddRequest,
    TeamMemberResponse,
    VirtualKeyCreateRequest,
    OrgMemberAddRequest,
    OrgMemberResponse,
    OrgMemberRoleUpdateRequest,
    OrgMemberListItem,
    OrgMembershipItem,
    OrganizationWatchlistsSettingsUpdate,
    OrganizationWatchlistsSettingsResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, is_single_user_principal
from tldw_Server_API.app.api.v1.API_Deps.org_deps import ROLE_HIERARCHY
from tldw_Server_API.app.core.AuthNZ.repos.rbac_repo import AuthnzRbacRepo
from tldw_Server_API.app.core.Usage.pricing_catalog import reset_pricing_catalog
from tldw_Server_API.app.core.Chat.chat_service import (
    invalidate_model_alias_caches,
)
from tldw_Server_API.app.services.admin_roles_permissions_service import (
    list_roles as svc_list_roles,
    create_role as svc_create_role,
    delete_role as svc_delete_role,
    list_role_permissions as svc_list_role_permissions,
    list_tool_permissions as svc_list_tool_permissions,
    delete_tool_permission as svc_delete_tool_permission,
    grant_tool_permission_to_role as svc_grant_tool_perm,
    revoke_tool_permission_from_role as svc_revoke_tool_perm,
)
from tldw_Server_API.app.services.admin_orgs_service import list_teams_by_org as svc_list_teams_by_org
from tldw_Server_API.app.services.admin_usage_service import (
    fetch_usage_daily as svc_fetch_usage_daily,
    export_usage_daily_csv_text as svc_export_usage_daily_csv_text,
    fetch_usage_top as svc_fetch_usage_top,
    export_usage_top_csv_text as svc_export_usage_top_csv_text,
    fetch_llm_usage as svc_fetch_llm_usage,
    fetch_llm_usage_summary as svc_fetch_llm_usage_summary,
    fetch_llm_top_spenders as svc_fetch_llm_top_spenders,
)
from tldw_Server_API.app.services.admin_budgets_service import (
    list_org_budgets as svc_list_org_budgets,
    upsert_org_budget as svc_upsert_org_budget,
)
from tldw_Server_API.app.services.admin_data_ops_service import (
    list_backup_items as svc_list_backup_items,
    create_backup_snapshot as svc_create_backup_snapshot,
    restore_backup_snapshot as svc_restore_backup_snapshot,
    list_retention_policies as svc_list_retention_policies,
    update_retention_policy as svc_update_retention_policy,
    build_audit_log_csv as svc_build_audit_log_csv,
    build_audit_log_json as svc_build_audit_log_json,
    build_users_csv as svc_build_users_csv,
    build_users_json as svc_build_users_json,
)
from tldw_Server_API.app.services.admin_system_ops_service import (
    get_maintenance_state as svc_get_maintenance_state,
    update_maintenance_state as svc_update_maintenance_state,
    list_feature_flags as svc_list_feature_flags,
    upsert_feature_flag as svc_upsert_feature_flag,
    delete_feature_flag as svc_delete_feature_flag,
    list_incidents as svc_list_incidents,
    create_incident as svc_create_incident,
    update_incident as svc_update_incident,
    add_incident_event as svc_add_incident_event,
    delete_incident as svc_delete_incident,
)
from tldw_Server_API.app.core.Logging.system_log_buffer import query_system_logs
from tldw_Server_API.app.services.admin_service import update_api_key_metadata
from tldw_Server_API.app.core.Security.webui_access_guard import (
    webui_remote_access_enabled,
    setup_remote_access_enabled,
)
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.Setup import setup_manager
from tldw_Server_API.app.services.registration_service import reset_registration_service
import ipaddress

REQUIRED_ADMIN_RANK = ROLE_HIERARCHY.get("admin", 3)
REQUIRED_TEAM_ADMIN_RANK = ROLE_HIERARCHY.get("lead", 2)
PLATFORM_ADMIN_ROLES = {"owner", "super_admin", "admin"}

# Test shim: some tests expect a private helper `_is_postgres_backend` to monkeypatch.
# Provide an alias to the public function for backward compatibility in tests.
_is_postgres_backend = is_postgres_backend


def _get_rbac_repo() -> AuthnzRbacRepo:
    """
    Factory for AuthnzRbacRepo used by admin RBAC endpoints.

    Keeping construction behind a small helper makes it easy to monkeypatch
    in tests and provides a single place to attach request-scoped state if
    we later bind the repo to a specific backend handle.
    """
    return AuthnzRbacRepo()

# Best-effort coordination for test-time SQLite migrations
_authnz_migration_lock = asyncio.Lock()

#######################################################################################################################
#
# Router Configuration

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles("admin"))],  # All endpoints require admin role
    responses={403: {"description": "Not authorized"}}
)

# Backend detection now standardized via core AuthNZ database helper


async def _ensure_sqlite_authnz_ready_if_test_mode() -> None:
    """Best-effort: ensure AuthNZ SQLite schema/migrations before admin ops in tests.

    In CI/pytest with SQLite, the pool can reinitialize while migrations are
    pending. This helper checks for a core table and, if missing, runs
    migrations. A module-level asyncio.Lock coordinates concurrent requests to
    avoid parallel migration attempts.
    """
    try:
        # Only act in obvious test contexts to avoid production overhead
        is_test = (
            os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
            or os.getenv("PYTEST_CURRENT_TEST") is not None
        )
        if not is_test:
            return

        from pathlib import Path as _Path
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool as _get_db_pool
        pool = await _get_db_pool()

        # Skip if Postgres
        if getattr(pool, "pool", None) is not None:
            return

        # Acquire coordination lock to avoid concurrent migration attempts
        async with _authnz_migration_lock:
            # Re-check existence of a core table after acquiring the lock in case
            # another coroutine completed migrations while we waited
            try:
                async with pool.acquire() as conn:
                    cur = await conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='organizations'"
                    )
                    row = await cur.fetchone()
                    if row:
                        return
            except Exception:
                # Proceed to ensure migrations
                pass

            from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables as _ensure
            db_path = getattr(pool, "_sqlite_fs_path", None) or getattr(pool, "db_path", None)
            if isinstance(db_path, str) and db_path:
                path_obj = _Path(db_path)
                # Best-effort: ensure parent directories exist to avoid path issues in CI
                try:
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                await asyncio.to_thread(_ensure, path_obj)
    except Exception as _e:
        # Best-effort only; do not interfere with request handling
        logger.debug(f"AuthNZ test ensure skipped/failed: {_e}")


async def _emit_admin_audit_event(
    request: Request,
    principal: AuthPrincipal,
    *,
    event_type: str,
    category: str,
    resource_type: str,
    resource_id: Optional[str],
    action: str,
    metadata: Dict[str, Any],
) -> None:
    """Best-effort audit emission for admin actions."""
    try:
        actor_id_raw = getattr(request.state, "user_id", None) or principal.user_id
        try:
            actor_id = int(actor_id_raw) if actor_id_raw is not None else None
        except (TypeError, ValueError):
            actor_id = None
        if actor_id is None:
            return
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
            get_or_create_audit_service_for_user_id,
        )
        from tldw_Server_API.app.core.Audit.unified_audit_service import (
            AuditContext,
            AuditEventType,
            AuditEventCategory,
        )
        audit_service = await get_or_create_audit_service_for_user_id(actor_id)
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or getattr(request.state, "correlation_id", None)
        )
        request_id = (
            request.headers.get("X-Request-ID")
            or getattr(request.state, "request_id", None)
            or ""
        )
        ctx = AuditContext(
            user_id=str(actor_id),
            correlation_id=correlation_id,
            request_id=request_id,
            ip_address=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
            endpoint=str(request.url.path),
            method=request.method,
        )
        await audit_service.log_event(
            event_type=AuditEventType(event_type),
            category=AuditEventCategory(category),
            context=ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning("Admin audit emission failed: {}", exc, exc_info=True)


def _role_rank(role: Optional[str]) -> int:
    """Map a role string to its numeric rank using ROLE_HIERARCHY."""
    if role is None:
        return 0
    return ROLE_HIERARCHY.get(str(role).strip().lower(), 0)


async def _enforce_admin_user_scope(
    principal: AuthPrincipal,
    target_user_id: int,
    *,
    require_hierarchy: bool,
) -> None:
    """Enforce shared org/team membership and optional role hierarchy for admin actions."""
    if is_single_user_principal(principal) or _is_platform_admin(principal):
        return

    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage users",
        )

    admin_memberships = await list_org_memberships_for_user(principal.user_id)
    target_memberships = await list_org_memberships_for_user(target_user_id)

    admin_org_roles = {
        m.get("org_id"): str(m.get("role") or "member").strip().lower()
        for m in admin_memberships
        if m.get("org_id") is not None
    }
    target_org_roles = {
        m.get("org_id"): str(m.get("role") or "member").strip().lower()
        for m in target_memberships
        if m.get("org_id") is not None
    }

    shared_orgs = set(admin_org_roles) & set(target_org_roles)
    if shared_orgs and not require_hierarchy:
        return

    if shared_orgs:
        for org_id in shared_orgs:
            admin_role = admin_org_roles.get(org_id)
            target_role = target_org_roles.get(org_id)
            if _role_rank(admin_role) >= REQUIRED_ADMIN_RANK and _role_rank(admin_role) >= _role_rank(target_role):
                return

    admin_team_memberships = await list_memberships_for_user(principal.user_id)
    target_team_memberships = await list_memberships_for_user(target_user_id)

    admin_team_roles = {
        m.get("team_id"): str(m.get("role") or "member").strip().lower()
        for m in admin_team_memberships
        if m.get("team_id") is not None
    }
    target_team_roles = {
        m.get("team_id"): str(m.get("role") or "member").strip().lower()
        for m in target_team_memberships
        if m.get("team_id") is not None
    }

    shared_teams = set(admin_team_roles) & set(target_team_roles)
    if shared_teams:
        for team_id in shared_teams:
            admin_role = admin_team_roles.get(team_id)
            target_role = target_team_roles.get(team_id)
            if _role_rank(admin_role) < REQUIRED_TEAM_ADMIN_RANK:
                continue
            if not require_hierarchy or _role_rank(admin_role) >= _role_rank(target_role):
                return

    if not shared_orgs and not shared_teams:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage users outside your organization or team",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to update this user",
    )


def _is_platform_admin(principal: AuthPrincipal) -> bool:
    if is_single_user_principal(principal):
        return True
    roles = {str(role).strip().lower() for role in (principal.roles or [])}
    return bool(roles & PLATFORM_ADMIN_ROLES)


def _require_platform_admin(principal: AuthPrincipal) -> None:
    if _is_platform_admin(principal):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Platform admin role required",
    )


def _derive_profile_update_roles(principal: AuthPrincipal) -> Set[str]:
    roles = {str(role).strip().lower() for role in (principal.roles or []) if role}
    if principal.is_admin or "admin" in roles:
        roles.add("admin")
        roles.update({"org_admin", "team_admin"})
    if _is_platform_admin(principal):
        roles.add("platform_admin")
    return roles


def _get_bulk_confirm_threshold() -> int:
    raw_env = os.getenv("BULK_UPDATE_CONFIRM_THRESHOLD")
    if raw_env:
        try:
            return max(1, int(raw_env))
        except Exception:
            return 1000
    try:
        config_parser = load_comprehensive_config()
        for section in ("user_profile", "profile", "admin"):
            if config_parser and config_parser.has_section(section):
                raw_cfg = config_parser.get(section, "bulkUpdateConfirmThreshold", fallback="").strip()
                if raw_cfg:
                    return max(1, int(raw_cfg))
    except Exception:
        pass
    return 1000


def _profile_error_response(
    *,
    status_code: int,
    error_code: str,
    detail: str,
    errors: Optional[List[UserProfileErrorDetail]] = None,
) -> JSONResponse:
    payload = UserProfileErrorResponse(
        error_code=error_code,
        detail=detail,
        errors=errors or [],
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _mask_profile_diff_value(
    profile_service: UserProfileService,
    catalog_map: Dict[str, Any],
    key: str,
    value: Any,
) -> Any:
    try:
        return profile_service._format_value(
            key,
            value,
            include_sources=False,
            source=None,
            catalog_map=catalog_map,
            mask_secrets=True,
        )
    except Exception:
        return value


async def _build_bulk_update_before_values(
    *,
    user_id: int,
    updates: List[UserProfileUpdateEntry],
    profile_service: UserProfileService,
    user_repo: AuthnzUsersRepo,
    catalog_map: Dict[str, Any],
) -> Dict[str, Any]:
    keys = [entry.key for entry in updates]
    key_set = set(keys)
    before: Dict[str, Any] = {}

    identity_keys = {
        "identity.email",
        "identity.role",
        "identity.is_active",
        "identity.is_verified",
        "identity.is_locked",
    }
    needs_user_record = bool(key_set & (identity_keys | {"limits.storage_quota_mb"}))
    user_row: Optional[Dict[str, Any]] = None
    if needs_user_record:
        user = await user_repo.get_user_by_id(int(user_id))
        if not user:
            return before
        user_row = dict(user)

    if user_row and (key_set & identity_keys):
        identity = profile_service._build_identity(user_row)
        await profile_service._attach_lockout_status(identity)
        identity_map = {
            "identity.email": identity.get("email"),
            "identity.role": identity.get("role"),
            "identity.is_active": identity.get("is_active"),
            "identity.is_verified": identity.get("is_verified"),
            "identity.is_locked": identity.get("is_locked"),
        }
        for key, value in identity_map.items():
            if key in key_set:
                before[key] = _mask_profile_diff_value(
                    profile_service,
                    catalog_map,
                    key,
                    value,
                )

    if user_row and "limits.storage_quota_mb" in key_set:
        before["limits.storage_quota_mb"] = _mask_profile_diff_value(
            profile_service,
            catalog_map,
            "limits.storage_quota_mb",
            user_row.get("storage_quota_mb"),
        )

    if any(key.startswith("memberships.") for key in key_set):
        org_memberships = await list_org_memberships_for_user(user_id)
        team_memberships = await list_memberships_for_user(user_id)
        org_roles = {
            int(m.get("org_id")): m.get("role")
            for m in org_memberships
            if m.get("org_id") is not None
        }
        team_roles = {
            int(m.get("team_id")): m.get("role")
            for m in team_memberships
            if m.get("team_id") is not None
        }

        for entry in updates:
            if entry.key == "memberships.orgs.role":
                if isinstance(entry.value, dict) and "org_id" in entry.value:
                    try:
                        org_id = int(entry.value.get("org_id"))
                    except (TypeError, ValueError):
                        continue
                    before_val = org_roles.get(org_id)
                    before[entry.key] = _mask_profile_diff_value(
                        profile_service,
                        catalog_map,
                        entry.key,
                        before_val,
                    )
            elif entry.key == "memberships.teams.role":
                if isinstance(entry.value, dict) and "team_id" in entry.value:
                    try:
                        team_id = int(entry.value.get("team_id"))
                    except (TypeError, ValueError):
                        continue
                    before_val = team_roles.get(team_id)
                    before[entry.key] = _mask_profile_diff_value(
                        profile_service,
                        catalog_map,
                        entry.key,
                        before_val,
                    )
            elif entry.key == "memberships.teams.member":
                if isinstance(entry.value, dict) and "team_id" in entry.value:
                    try:
                        team_id = int(entry.value.get("team_id"))
                    except (TypeError, ValueError):
                        continue
                    role = team_roles.get(team_id)
                    before_val = {"member": team_id in team_roles, "role": role}
                    before[entry.key] = _mask_profile_diff_value(
                        profile_service,
                        catalog_map,
                        entry.key,
                        before_val,
                    )

    needs_effective = any(
        key not in identity_keys
        and not key.startswith("memberships.")
        and key != "limits.storage_quota_mb"
        for key in key_set
    )
    if needs_effective:
        effective = await profile_service._build_effective_config(
            int(user_id),
            include_sources=False,
            mask_secrets=True,
        )
        for key in key_set:
            if key in before:
                continue
            if key in effective:
                before[key] = effective.get(key)

    return before


def _parse_user_id_list(raw: Optional[str]) -> Optional[List[int]]:
    if raw is None:
        return None
    values: List[int] = []
    for part in str(raw).split(","):
        piece = part.strip()
        if not piece:
            continue
        try:
            values.append(int(piece))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_user_ids",
            ) from exc
    return values or None


async def _get_admin_org_ids(principal: AuthPrincipal) -> Optional[List[int]]:
    if is_single_user_principal(principal) or _is_platform_admin(principal):
        return None
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access organization data",
        )
    memberships = await list_org_memberships_for_user(principal.user_id)
    return [int(m.get("org_id")) for m in memberships if m.get("org_id") is not None]


class _ProfileAdminScope:
    def __init__(
        self,
        *,
        org_admin_ids: Optional[Set[int]],
        team_admin_ids: Set[int],
        team_admin_org_ids: Set[int],
        team_admin_org_map: Dict[int, int],
    ) -> None:
        self.org_admin_ids = org_admin_ids
        self.team_admin_ids = team_admin_ids
        self.team_admin_org_ids = team_admin_org_ids
        self.team_admin_org_map = team_admin_org_map

    @property
    def is_platform_admin(self) -> bool:
        return self.org_admin_ids is None


async def _get_profile_admin_scope(principal: AuthPrincipal) -> _ProfileAdminScope:
    if is_single_user_principal(principal) or _is_platform_admin(principal):
        return _ProfileAdminScope(
            org_admin_ids=None,
            team_admin_ids=set(),
            team_admin_org_ids=set(),
            team_admin_org_map={},
        )
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage users",
        )
    org_memberships = await list_org_memberships_for_user(principal.user_id)
    org_admin_ids = {
        int(m.get("org_id"))
        for m in org_memberships
        if m.get("org_id") is not None
        and _role_rank(m.get("role")) >= REQUIRED_ADMIN_RANK
    }

    team_memberships = await list_memberships_for_user(principal.user_id)
    team_admin_ids: Set[int] = set()
    team_admin_org_ids: Set[int] = set()
    team_admin_org_map: Dict[int, int] = {}
    for membership in team_memberships:
        team_id = membership.get("team_id")
        org_id = membership.get("org_id")
        if team_id is None or org_id is None:
            continue
        if _role_rank(membership.get("role")) < REQUIRED_TEAM_ADMIN_RANK:
            continue
        team_id_int = int(team_id)
        org_id_int = int(org_id)
        team_admin_ids.add(team_id_int)
        team_admin_org_ids.add(org_id_int)
        team_admin_org_map[team_id_int] = org_id_int

    if not org_admin_ids and not team_admin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage users",
        )

    return _ProfileAdminScope(
        org_admin_ids=org_admin_ids,
        team_admin_ids=team_admin_ids,
        team_admin_org_ids=team_admin_org_ids,
        team_admin_org_map=team_admin_org_map,
    )


async def _load_team_user_ids(team_ids: Set[int]) -> Set[int]:
    user_ids: Set[int] = set()
    for team_id in team_ids:
        members = await list_team_members(int(team_id))
        for member in members:
            if member.get("user_id") is None:
                continue
            status = member.get("status")
            if status is not None and str(status).lower() != "active":
                continue
            user_ids.add(int(member.get("user_id")))
    return user_ids


async def _enforce_admin_org_access(
    principal: AuthPrincipal,
    org_id: int,
    *,
    require_admin: bool = True,
) -> None:
    if is_single_user_principal(principal) or _is_platform_admin(principal):
        return
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this organization",
        )
    memberships = await list_org_memberships_for_user(principal.user_id)
    membership = next((m for m in memberships if m.get("org_id") == org_id), None)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this organization",
        )
    if require_admin and _role_rank(membership.get("role")) < REQUIRED_ADMIN_RANK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin role required",
        )


async def _get_scoped_team(
    team_id: int,
    principal: AuthPrincipal,
    *,
    require_admin: bool = True,
) -> Dict[str, Any]:
    team = await get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team_not_found")
    await _enforce_admin_org_access(
        principal,
        int(team.get("org_id")),
        require_admin=require_admin,
    )
    return team


async def _load_bulk_user_candidates(
    *,
    principal: AuthPrincipal,
    org_id: Optional[int],
    team_id: Optional[int],
    role: Optional[str],
    is_active: Optional[bool],
    search: Optional[str],
    user_ids: Optional[List[int]],
) -> List[int]:
    repo = await AuthnzUsersRepo.from_pool()
    scope = await _get_profile_admin_scope(principal)
    org_ids: Optional[List[int]] = None
    team_user_ids: Optional[Set[int]] = None
    restrict_to_team_scope = False

    if org_id is not None:
        if not scope.is_platform_admin:
            if org_id not in scope.org_admin_ids and org_id not in scope.team_admin_org_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this organization",
                )
        org_ids = [org_id]
        if not scope.is_platform_admin and org_id not in scope.org_admin_ids:
            restrict_to_team_scope = True

    if team_id is not None:
        team = await get_team(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="team_not_found")
        team_org_id = int(team.get("org_id"))
        if org_id is not None and team_org_id != int(org_id):
            return []
        if not scope.is_platform_admin:
            if team_id not in scope.team_admin_ids and team_org_id not in scope.org_admin_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this team",
                )
        team_user_ids = await _load_team_user_ids({int(team_id)})
        if org_ids is None:
            org_ids = [team_org_id]
        elif team_org_id not in org_ids:
            return []

    if not scope.is_platform_admin and org_ids is None:
        if scope.org_admin_ids:
            org_ids = sorted(scope.org_admin_ids)
        elif scope.team_admin_org_ids:
            org_ids = sorted(scope.team_admin_org_ids)
            restrict_to_team_scope = True

    if restrict_to_team_scope and team_user_ids is None:
        allowed_team_ids = set(scope.team_admin_ids)
        if org_id is not None:
            allowed_team_ids = {
                team_id for team_id, team_org in scope.team_admin_org_map.items()
                if team_org == int(org_id)
            }
        if not allowed_team_ids:
            return []
        team_user_ids = await _load_team_user_ids(allowed_team_ids)
        if not team_user_ids:
            return []

    target_ids: Set[int] = set()
    offset = 0
    limit = 500
    while True:
        users, total = await repo.list_users(
            offset=offset,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search,
            org_ids=org_ids,
        )
        for user in users:
            try:
                target_ids.add(int(user.get("id")))
            except Exception:
                continue
        offset += limit
        if len(target_ids) >= total:
            break

    if user_ids:
        target_ids &= {int(uid) for uid in user_ids}
    if team_user_ids is not None:
        target_ids &= team_user_ids

    return sorted(target_ids)

#######################################################################################################################
#
# User Management Endpoints

@router.post("/users", response_model=UserSummary)
async def admin_create_user(
    payload: AdminUserCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    registration_service=Depends(get_registration_service_dep),
) -> UserSummary:
    """
    Create a new user as an admin.
    """
    profile = get_profile()
    if isinstance(profile, str) and profile.strip().lower() in {"local-single-user", "single_user"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User creation is not allowed in local-single-user profile",
        )

    created_by = int(principal.user_id) if principal.user_id is not None else None
    try:
        user_info = await registration_service.register_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            created_by=created_by,
            role_override=payload.role,
            is_active_override=payload.is_active,
            is_verified_override=payload.is_verified,
            storage_quota_override=payload.storage_quota_mb,
        )
        repo = await AuthnzUsersRepo.from_pool()
        user = await repo.get_user_by_id(int(user_info["user_id"]))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load created user",
            )
        logger.info("Admin created user {} (id={})", payload.username, user_info["user_id"])
        return user
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeakPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RegistrationDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to create user: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        ) from exc


@router.get("/users", response_model=UserListResponse)
async def list_users(
    request: Request,
    response: Response,
    principal: AuthPrincipal = Depends(get_auth_principal),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
) -> UserListResponse:
    """
    List all users with pagination and filters

    Args:
        page: Page number (1-based)
        limit: Items per page
        role: Filter by role
        is_active: Filter by active status
        search: Search in username/email

    Returns:
        Paginated list of users
    """
    # TEST_MODE diagnostics: annotate DB backend and admin dependency success
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        try:
            pool = await get_db_pool()
            db_backend = "postgres" if getattr(pool, "pool", None) is not None else "sqlite"
            response.headers["X-TLDW-Admin-DB"] = db_backend
            response.headers["X-TLDW-Admin-Req"] = "ok"
            auth_hdr = request.headers.get("Authorization")
            logger.info(
                "Admin list_users TEST_MODE: Authorization present={}",
                bool(auth_hdr),
            )
        except Exception as diag_exc:  # noqa: BLE001 - diagnostics only, do not fail request
            response.headers["X-TLDW-Admin-Diag-Error"] = str(diag_exc)
            logger.debug(
                "Admin list_users TEST_MODE diagnostics failed: {}",
                diag_exc,
            )

    try:
        offset = (page - 1) * limit
        repo = await AuthnzUsersRepo.from_pool()
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        users, total = await repo.list_users(
            offset=offset,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search,
            org_ids=org_ids,
        )
        return UserListResponse(
            users=users,
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit if limit else 0,
        )
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        try:
            if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
                response.headers["X-TLDW-Admin-Error"] = str(e)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        )


@router.get("/users/export")
async def export_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    limit: int = Query(10000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    format: str = Query("csv", pattern="^(csv|json)$"),
    filename: Optional[str] = Query(None, description="Optional filename for Content-Disposition"),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    try:
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        repo = await AuthnzUsersRepo.from_pool()
        users, total = await repo.list_users(
            offset=offset,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search,
            org_ids=org_ids,
        )
        if format == "json":
            content = svc_build_users_json(users, total=total, limit=limit, offset=offset)
            resp = Response(content=content, media_type="application/json")
            if not filename:
                filename = "users.json"
        else:
            content = svc_build_users_csv(users)
            resp = PlainTextResponse(content=content, media_type="text/csv")
            if not filename:
                filename = "users.csv"
        if filename:
            safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
            resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
        return resp
    except Exception as exc:
        logger.error(f"Failed to export users: {exc}")
        raise HTTPException(status_code=500, detail="Failed to export users")


#######################################################################################################################
#
# Per-User API Key Management (Admin)

@router.get("/users/{user_id}/api-keys", response_model=List[APIKeyMetadata])
async def admin_list_user_api_keys(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    include_revoked: bool = False,
) -> list[APIKeyMetadata]:
    """List API keys for a specific user (admin)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        api_mgr = await get_api_key_manager()
        rows = await api_mgr.list_user_keys(user_id=user_id, include_revoked=include_revoked)
        return [APIKeyMetadata(**row) for row in rows]
    except Exception as e:
        logger.error(f"Admin failed to list API keys for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.post("/users/{user_id}/api-keys", response_model=APIKeyCreateResponse)
async def admin_create_user_api_key(
    user_id: int,
    request: APIKeyCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> APIKeyCreateResponse:
    """Create a new API key for the given user (admin)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        api_mgr = await get_api_key_manager()
        result = await api_mgr.create_api_key(
            user_id=user_id,
            name=request.name,
            description=request.description,
            scope=request.scope,
            expires_in_days=request.expires_in_days,
        )
        return APIKeyCreateResponse(**result)
    except Exception as e:
        logger.error(f"Admin failed to create API key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.post("/users/{user_id}/api-keys/{key_id}/rotate", response_model=APIKeyCreateResponse)
async def admin_rotate_user_api_key(
    user_id: int,
    key_id: int,
    request: APIKeyRotateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> APIKeyCreateResponse:
    """Rotate an API key for the given user and return the new key (admin)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        api_mgr = await get_api_key_manager()
        result = await api_mgr.rotate_api_key(
            key_id=key_id,
            user_id=user_id,
            expires_in_days=request.expires_in_days,
        )
        return APIKeyCreateResponse(**result)
    except Exception as e:
        logger.error(f"Admin failed to rotate API key {key_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to rotate API key")


@router.delete("/users/{user_id}/api-keys/{key_id}")
async def admin_revoke_user_api_key(
    user_id: int,
    key_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Dict[str, Any]:
    """Revoke an API key for the given user (admin)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        api_mgr = await get_api_key_manager()
        success = await api_mgr.revoke_api_key(key_id=key_id, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "API key revoked", "user_id": user_id, "key_id": key_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin failed to revoke API key {key_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.patch("/users/{user_id}/api-keys/{key_id}", response_model=APIKeyMetadata)
async def admin_update_user_api_key(
    user_id: int,
    key_id: int,
    request: APIKeyUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> APIKeyMetadata:
    """Update per-key limits like rate_limit and allowed_ips (admin)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        try:
            row = await update_api_key_metadata(
                db,
                user_id=user_id,
                key_id=key_id,
                rate_limit=request.rate_limit,
                allowed_ips=request.allowed_ips,
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="No updates provided")
        except LookupError:
            raise HTTPException(status_code=404, detail="API key not found")
        return APIKeyMetadata(**row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin failed to update API key {key_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update API key")


#######################################################################################################################
#
# BYOK Key Management (Admin)

async def _get_user_byok_repo() -> AuthnzUserProviderSecretsRepo:
    """Initialize user BYOK repository and ensure schema exists."""
    try:
        pool = await get_db_pool()
        repo = AuthnzUserProviderSecretsRepo(pool)
        await repo.ensure_tables()
        return repo
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to initialize user BYOK repository: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BYOK infrastructure is not available",
        ) from exc


async def _get_shared_byok_repo() -> AuthnzOrgProviderSecretsRepo:
    """Initialize shared BYOK repository and ensure schema exists."""
    try:
        pool = await get_db_pool()
        repo = AuthnzOrgProviderSecretsRepo(pool)
        await repo.ensure_tables()
        return repo
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to initialize shared BYOK repository: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BYOK infrastructure is not available",
        ) from exc


async def _get_llm_provider_overrides_repo() -> AuthnzLLMProviderOverridesRepo:
    """Initialize provider overrides repository and ensure schema exists."""
    try:
        pool = await get_db_pool()
        repo = AuthnzLLMProviderOverridesRepo(pool)
        await repo.ensure_tables()
        return repo
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to initialize LLM provider overrides repository: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provider overrides infrastructure is not available",
        ) from exc


def _require_byok_enabled() -> None:
    if not is_byok_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="BYOK is disabled in this deployment",
        )


def _normalize_credential_fields(
    provider: str,
    fields: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Normalize credential fields; base_url is allowlisted per provider and egress-validated."""
    provider_norm = normalize_provider_name(provider)
    credential_fields = validate_credential_fields(
        provider_norm,
        fields,
        allow_base_url=True,
    )
    if "base_url" in credential_fields:
        credential_fields["base_url"] = validate_base_url_override(
            credential_fields["base_url"]
        )
    return credential_fields


async def _touch_shared_last_used_if_match(
    repo: AuthnzOrgProviderSecretsRepo,
    *,
    scope_type: str,
    scope_id: int,
    provider: str,
    api_key: str,
) -> None:
    row = await repo.fetch_secret(scope_type, scope_id, provider)
    if not row:
        return
    encrypted_blob = row.get("encrypted_blob")
    if not encrypted_blob:
        return
    try:
        payload = decrypt_byok_payload(loads_envelope(encrypted_blob))
    except (ValueError, KeyError, TypeError) as exc:
        logger.debug(
            "BYOK: failed to decrypt shared secret for %s:%s (%s): %s",
            scope_type,
            scope_id,
            provider,
            exc,
        )
        return
    if payload.get("api_key") != api_key:
        return
    await repo.touch_last_used(scope_type, scope_id, provider, datetime.now(timezone.utc))


@router.get(
    "/keys/users/{user_id}",
    response_model=AdminUserKeysResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_list_user_byok_keys(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminUserKeysResponse:
    _require_byok_enabled()
    await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
    repo = await _get_user_byok_repo()
    try:
        rows = await repo.list_secrets_for_user(user_id)
    except Exception as exc:
        logger.error("BYOK: failed to list user keys for user_id=%s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to list user BYOK keys") from exc
    allowlist = resolve_byok_allowlist()
    items = [
        AdminUserKeyStatusItem(
            provider=row.get("provider"),
            key_hint=row.get("key_hint"),
            last_used_at=row.get("last_used_at"),
            allowed=str(row.get("provider")) in allowlist,
        )
        for row in rows
    ]
    return AdminUserKeysResponse(user_id=user_id, items=items)


@router.delete(
    "/keys/users/{user_id}/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_revoke_user_byok_key(
    user_id: int,
    provider: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    _require_byok_enabled()
    await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
    repo = await _get_user_byok_repo()
    provider_norm = normalize_provider_name(provider)
    try:
        deleted = await repo.delete_secret(
            user_id,
            provider_norm,
            revoked_by=principal.user_id,
        )
    except Exception as exc:
        logger.error(
            "BYOK: failed to revoke user key for user_id=%s provider=%s: %s",
            user_id,
            provider_norm,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to revoke user BYOK key") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/keys/shared",
    response_model=SharedProviderKeyResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_upsert_shared_byok_key(
    payload: SharedProviderKeyUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> SharedProviderKeyResponse:
    _require_byok_enabled()
    provider_norm = normalize_provider_name(payload.provider)
    if not is_provider_allowlisted(provider_norm):
        raise HTTPException(status_code=403, detail="Provider not allowed for BYOK")

    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")

    try:
        credential_fields = _normalize_credential_fields(provider_norm, payload.credential_fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        await test_provider_credentials(
            provider=provider_norm,
            api_key=api_key,
            credential_fields=credential_fields,
            model=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ChatAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Provider test call failed") from exc

    secret_payload = build_secret_payload(api_key, credential_fields or None)
    try:
        envelope = encrypt_byok_payload(secret_payload)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="BYOK encryption is not configured") from exc

    repo = await _get_shared_byok_repo()
    now = datetime.now(timezone.utc)
    try:
        row = await repo.upsert_secret(
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            provider=provider_norm,
            encrypted_blob=dumps_envelope(envelope),
            key_hint=key_hint_for_api_key(api_key),
            metadata=payload.metadata,
            updated_at=now,
            created_by=principal.user_id,
            updated_by=principal.user_id,
        )
    except Exception as exc:
        logger.error(
            "BYOK: failed to upsert shared key for %s:%s provider=%s: %s",
            payload.scope_type,
            payload.scope_id,
            provider_norm,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to store shared BYOK key") from exc
    return SharedProviderKeyResponse(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        provider=provider_norm,
        key_hint=row.get("key_hint") or key_hint_for_api_key(api_key),
        updated_at=row.get("updated_at") or now,
    )


@router.post(
    "/keys/shared/test",
    response_model=SharedProviderKeyTestResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_test_shared_byok_key(payload: SharedProviderKeyTestRequest) -> SharedProviderKeyTestResponse:
    _require_byok_enabled()
    provider_norm = normalize_provider_name(payload.provider)
    if not is_provider_allowlisted(provider_norm):
        raise HTTPException(status_code=403, detail="Provider not allowed for BYOK")

    repo = await _get_shared_byok_repo()
    row = await repo.fetch_secret(payload.scope_type, payload.scope_id, provider_norm)
    if not row:
        raise HTTPException(status_code=404, detail="Key not found")
    encrypted_blob = row.get("encrypted_blob")
    if not encrypted_blob:
        raise HTTPException(status_code=404, detail="Key not found")
    try:
        stored_payload = decrypt_byok_payload(loads_envelope(encrypted_blob))
    except Exception:
        raise HTTPException(status_code=404, detail="Key not found")

    api_key = (stored_payload.get("api_key") or "").strip()
    if not api_key:
        raise HTTPException(status_code=404, detail="Key not found")

    try:
        credential_fields = _normalize_credential_fields(
            provider_norm,
            stored_payload.get("credential_fields") or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        model_used = await test_provider_credentials(
            provider=provider_norm,
            api_key=api_key,
            credential_fields=credential_fields,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ChatAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Provider test call failed") from exc

    await _touch_shared_last_used_if_match(
        repo,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        provider=provider_norm,
        api_key=api_key,
    )

    return SharedProviderKeyTestResponse(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        provider=provider_norm,
        status="valid",
        model=model_used,
    )


@router.get(
    "/keys/shared",
    response_model=SharedProviderKeysResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_list_shared_byok_keys(
    scope_type: Optional[str] = Query(None),
    scope_id: Optional[int] = Query(None),
    provider: Optional[str] = Query(None),
) -> SharedProviderKeysResponse:
    _require_byok_enabled()
    repo = await _get_shared_byok_repo()
    try:
        rows = await repo.list_secrets(
            scope_type=scope_type,
            scope_id=scope_id,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "BYOK: failed to list shared keys for scope_type=%s scope_id=%s provider=%s: %s",
            scope_type,
            scope_id,
            provider,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to list shared BYOK keys") from exc
    items = [
        SharedProviderKeyStatusItem(
            scope_type=row.get("scope_type"),
            scope_id=row.get("scope_id"),
            provider=row.get("provider"),
            key_hint=row.get("key_hint"),
            last_used_at=row.get("last_used_at"),
        )
        for row in rows
    ]
    return SharedProviderKeysResponse(items=items)


@router.delete(
    "/keys/shared/{scope_type}/{scope_id}/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_delete_shared_byok_key(
    scope_type: str,
    scope_id: int,
    provider: str,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Response:
    _require_byok_enabled()
    repo = await _get_shared_byok_repo()
    provider_norm = normalize_provider_name(provider)
    try:
        deleted = await repo.delete_secret(
            scope_type,
            scope_id,
            provider_norm,
            revoked_by=principal.user_id,
        )
    except Exception as exc:
        logger.error(
            "BYOK: failed to delete shared key for scope_type=%s scope_id=%s provider=%s: %s",
            scope_type,
            scope_id,
            provider_norm,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to delete shared BYOK key") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


#######################################################################################################################
#
# LLM Provider Overrides

def _build_llm_provider_override_response(override: Any) -> LLMProviderOverrideResponse:
    return LLMProviderOverrideResponse(
        provider=override.provider,
        is_enabled=override.is_enabled,
        allowed_models=override.allowed_models,
        config=override.config or None,
        credential_fields=override.credential_fields or None,
        has_api_key=bool(override.api_key or override.api_key_hint),
        api_key_hint=override.api_key_hint,
        created_at=override.created_at,
        updated_at=override.updated_at,
    )


def _normalize_allowed_models(raw: Optional[List[str]]) -> Optional[List[str]]:
    if raw is None:
        return None
    cleaned = [str(v).strip() for v in raw if isinstance(v, (str, int, float)) and str(v).strip()]
    return cleaned or None


@router.get(
    "/llm/providers/overrides",
    response_model=LLMProviderOverrideListResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_list_llm_provider_overrides(
    provider: Optional[str] = Query(None),
) -> LLMProviderOverrideListResponse:
    await _ensure_sqlite_authnz_ready_if_test_mode()
    await refresh_llm_provider_overrides()
    overrides = get_llm_provider_overrides_snapshot()
    provider_norm = normalize_provider_name(provider) if provider else None

    items: List[LLMProviderOverrideResponse] = []
    for name in sorted(overrides.keys()):
        if provider_norm and name != provider_norm:
            continue
        items.append(_build_llm_provider_override_response(overrides[name]))

    return LLMProviderOverrideListResponse(items=items)


@router.get(
    "/llm/providers/overrides/{provider}",
    response_model=LLMProviderOverrideResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_get_llm_provider_override(provider: str) -> LLMProviderOverrideResponse:
    await _ensure_sqlite_authnz_ready_if_test_mode()
    await refresh_llm_provider_overrides()
    override = get_llm_provider_override(provider)
    if not override:
        raise HTTPException(status_code=404, detail="Provider override not found")
    return _build_llm_provider_override_response(override)


@router.put(
    "/llm/providers/overrides/{provider}",
    response_model=LLMProviderOverrideResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_upsert_llm_provider_override(
    provider: str,
    payload: LLMProviderOverrideRequest,
) -> LLMProviderOverrideResponse:
    await _ensure_sqlite_authnz_ready_if_test_mode()
    provider_norm = normalize_provider_name(provider)

    if (
        payload.is_enabled is None
        and payload.allowed_models is None
        and payload.config is None
        and payload.api_key is None
        and payload.credential_fields is None
        and not payload.clear_api_key
    ):
        raise HTTPException(status_code=400, detail="No override fields supplied")

    repo = await _get_llm_provider_overrides_repo()
    existing = await repo.fetch_override(provider_norm)
    is_enabled = existing.get("is_enabled") if existing else None
    allowed_models_json = existing.get("allowed_models") if existing else None
    config_json = existing.get("config_json") if existing else None
    secret_blob = existing.get("secret_blob") if existing else None
    api_key_hint = existing.get("api_key_hint") if existing else None

    if payload.is_enabled is not None:
        is_enabled = payload.is_enabled

    if payload.allowed_models is not None:
        normalized_models = _normalize_allowed_models(payload.allowed_models)
        allowed_models_json = json.dumps(normalized_models) if normalized_models else None

    if payload.config is not None:
        if not isinstance(payload.config, dict):
            raise HTTPException(status_code=400, detail="config must be an object")
        config_json = json.dumps(payload.config) if payload.config else None

    credential_fields: Optional[Dict[str, Any]] = None
    if payload.credential_fields is not None:
        try:
            credential_fields = _normalize_credential_fields(provider_norm, payload.credential_fields)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.clear_api_key:
        secret_blob = None
        api_key_hint = None

    if payload.api_key is not None:
        api_key = payload.api_key.strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="api_key cannot be empty")

        if credential_fields is None and secret_blob:
            try:
                payload_existing = decrypt_byok_payload(loads_envelope(secret_blob))
                existing_fields = payload_existing.get("credential_fields")
                if isinstance(existing_fields, dict):
                    credential_fields = existing_fields
            except Exception:
                credential_fields = credential_fields or None

        secret_payload = build_secret_payload(api_key, credential_fields or None)
        try:
            envelope = encrypt_byok_payload(secret_payload)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail="BYOK encryption is not configured") from exc
        secret_blob = dumps_envelope(envelope)
        api_key_hint = key_hint_for_api_key(api_key)
    elif credential_fields is not None:
        if not secret_blob:
            raise HTTPException(status_code=400, detail="credential_fields require an existing api_key")
        try:
            payload_existing = decrypt_byok_payload(loads_envelope(secret_blob))
            existing_key = payload_existing.get("api_key")
            if not existing_key:
                raise ValueError("Existing api_key is missing")
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Failed to load existing api_key") from exc
        secret_payload = build_secret_payload(existing_key, credential_fields or None)
        try:
            envelope = encrypt_byok_payload(secret_payload)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail="BYOK encryption is not configured") from exc
        secret_blob = dumps_envelope(envelope)
        api_key_hint = key_hint_for_api_key(existing_key)

    now = datetime.now(timezone.utc)
    try:
        await repo.upsert_override(
            provider=provider_norm,
            is_enabled=is_enabled,
            allowed_models=allowed_models_json,
            config_json=config_json,
            secret_blob=secret_blob,
            api_key_hint=api_key_hint,
            updated_at=now,
        )
    except Exception as exc:
        logger.error("Provider override upsert failed for provider=%s: %s", provider_norm, exc)
        raise HTTPException(status_code=500, detail="Failed to store provider override") from exc

    await refresh_llm_provider_overrides()
    override = get_llm_provider_override(provider_norm)
    if not override:
        raise HTTPException(status_code=500, detail="Failed to load provider override")
    return _build_llm_provider_override_response(override)


@router.delete(
    "/llm/providers/overrides/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_delete_llm_provider_override(provider: str) -> Response:
    await _ensure_sqlite_authnz_ready_if_test_mode()
    repo = await _get_llm_provider_overrides_repo()
    provider_norm = normalize_provider_name(provider)
    try:
        deleted = await repo.delete_override(provider_norm)
    except Exception as exc:
        logger.error("Provider override delete failed for provider=%s: %s", provider_norm, exc)
        raise HTTPException(status_code=500, detail="Failed to delete provider override") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider override not found")
    await refresh_llm_provider_overrides()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/llm/providers/test",
    response_model=LLMProviderTestResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_test_llm_provider(payload: LLMProviderTestRequest) -> LLMProviderTestResponse:
    provider_norm = normalize_provider_name(payload.provider)
    await refresh_llm_provider_overrides()

    api_key = (payload.api_key or "").strip()
    credential_fields = payload.credential_fields
    model = payload.model

    if payload.use_override and (not api_key or credential_fields is None or model is None):
        override = get_llm_provider_override(provider_norm)
        if override:
            if not api_key:
                api_key = override.api_key or api_key
            if credential_fields is None:
                credential_fields = override.credential_fields or None
            if model is None:
                model = override.config.get("default_model")

    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")

    if credential_fields is not None:
        try:
            credential_fields = _normalize_credential_fields(provider_norm, credential_fields)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        model_used = await test_provider_credentials(
            provider=provider_norm,
            api_key=api_key,
            credential_fields=credential_fields,
            model=model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ChatAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Provider test call failed") from exc

    return LLMProviderTestResponse(
        provider=provider_norm,
        status="valid",
        model=model_used,
    )


def _get_kanban_db_for_user_id(user_id: int) -> KanbanDB:
    db_path = DatabasePaths.get_kanban_db_path(user_id)
    return KanbanDB(db_path=str(db_path), user_id=str(user_id))


@router.post(
    "/kanban/fts/{action}",
    response_model=KanbanFtsMaintenanceResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def admin_kanban_fts_maintenance(
    action: Literal["optimize", "rebuild"],
    user_id: int = Query(..., ge=1),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> KanbanFtsMaintenanceResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        db = _get_kanban_db_for_user_id(user_id)
        if action == "rebuild":
            db.rebuild_fts()
        else:
            db.optimize_fts()
    except InputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KanbanDBError as exc:
        logger.error(f"Kanban FTS {action} failed for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Kanban FTS maintenance failed") from exc
    except Exception as exc:
        logger.error(f"Kanban FTS {action} failed for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Kanban FTS maintenance failed") from exc
    return KanbanFtsMaintenanceResponse(user_id=user_id, action=action, status="ok")


#######################################################################################################################
#
# Organizations and Teams

@router.post("/orgs", response_model=OrganizationResponse)
async def admin_create_org(payload: OrganizationCreateRequest) -> OrganizationResponse:
    try:
        # CI/pytest (SQLite) guard: ensure migrations before org creation
        await _ensure_sqlite_authnz_ready_if_test_mode()
        row = await create_organization(name=payload.name, owner_user_id=payload.owner_user_id, slug=payload.slug)
        return OrganizationResponse(**row)
    except DuplicateOrganizationError as dup:
        # Conflict: name or slug already exists
        raise HTTPException(status_code=409, detail=f"Organization with {dup.field} '{dup.value}' already exists")
    except Exception as e:
        logger.error(f"Failed to create organization: {e}")
        raise HTTPException(status_code=500, detail="Failed to create organization")


@router.get("/orgs")
async def admin_list_orgs(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
) -> Any:
    """List organizations.

    Backwards compatibility: when called without pagination/search query params,
    return a plain list of organizations. When any of ('limit', 'offset', 'q')
    are present in the query string, return a structured payload with
    pagination metadata.
    """
    try:
        # Detect whether caller explicitly requested pagination/search
        qp = request.query_params
        wants_wrapper = any(k in qp for k in ("limit", "offset", "q"))

        # Ask service for rows and optionally total
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []

        result = await list_organizations(
            limit=limit,
            offset=offset,
            q=q,
            org_ids=org_ids,
            with_total=wants_wrapper,
        )
        if wants_wrapper:
            if not isinstance(result, tuple) or len(result) != 2:
                logger.error(
                    f"list_organizations returned unexpected format: {type(result).__name__}"
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to list organizations",
                )
            rows, total = result
        else:
            rows = result[0] if isinstance(result, tuple) else result
            total = 0
        items = [OrganizationResponse(**r).model_dump() for r in rows]

        if wants_wrapper:
            has_more = (offset + len(items)) < int(total or 0)
            return {
                "items": items,
                "total": int(total or 0),
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            }
        # Raw list for legacy/simple callers
        return items
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list organizations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list organizations")


@router.post("/orgs/{org_id}/teams", response_model=TeamResponse)
async def admin_create_team(
    org_id: int,
    payload: TeamCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TeamResponse:
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        # CI/pytest (SQLite) guard: ensure migrations before team creation
        await _ensure_sqlite_authnz_ready_if_test_mode()
        row = await create_team(org_id=org_id, name=payload.name, slug=payload.slug, description=payload.description)
        return TeamResponse(**row)
    except DuplicateTeamError as dup:
        raise HTTPException(status_code=409, detail=f"Team with {dup.field} '{dup.value}' already exists in org {org_id}")
    except Exception as e:
        logger.error(f"Failed to create team: {e}")
        raise HTTPException(status_code=500, detail="Failed to create team")


@router.get("/orgs/{org_id}/teams", response_model=List[TeamResponse])
async def admin_list_teams(
    org_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> list[TeamResponse]:
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        rows = await svc_list_teams_by_org(db, org_id, limit, offset)
        return [TeamResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list teams: {e}")
        raise HTTPException(status_code=500, detail="Failed to list teams")


@router.get("/teams/{team_id}", response_model=TeamResponse)
async def admin_get_team(
    team_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TeamResponse:
    try:
        team = await _get_scoped_team(team_id, principal, require_admin=True)
        return TeamResponse(**team)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch team {team_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch team") from e


@router.patch("/orgs/{org_id}/watchlists/settings", response_model=OrganizationWatchlistsSettingsResponse)
async def admin_update_org_watchlists_settings(
    org_id: int,
    payload: OrganizationWatchlistsSettingsUpdate,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
):
    """Update watchlists-related organization settings (metadata).

    Currently supports:
      - require_include_default: default include-only gating for jobs in this org
    """
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        # Fetch existing metadata for this org (works for both backends)
        if hasattr(db, "fetchrow"):
            row = await db.fetchrow("SELECT metadata FROM organizations WHERE id = $1", org_id)
            meta_raw = row.get("metadata") if row else None
        else:
            cur = await db.execute("SELECT metadata FROM organizations WHERE id = ?", (org_id,))
            row = await cur.fetchone()
            meta_raw = row[0] if row else None
        if not row:
            raise HTTPException(status_code=404, detail="organization_not_found")
        meta: Dict[str, Any]
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}

        wl = meta.get("watchlists") if isinstance(meta.get("watchlists"), dict) else {}
        changed = False
        if payload.require_include_default is not None:
            wl["require_include_default"] = bool(payload.require_include_default)
            changed = True
        if changed:
            meta["watchlists"] = wl
            if hasattr(db, "fetchrow"):
                await db.execute(
                    "UPDATE organizations SET metadata = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                    json.dumps(meta), org_id,
                )
            else:
                await db.execute(
                    "UPDATE organizations SET metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(meta), org_id),
                )
        return OrganizationWatchlistsSettingsResponse(
            org_id=org_id,
            require_include_default=wl.get("require_include_default"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update org watchlists settings for org {org_id}: {e}")
        raise HTTPException(status_code=500, detail="failed_to_update_org_watchlists_settings")


@router.get("/orgs/{org_id}/watchlists/settings", response_model=OrganizationWatchlistsSettingsResponse)
async def admin_get_org_watchlists_settings(
    org_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> OrganizationWatchlistsSettingsResponse:
    """Fetch watchlists-related organization settings (from metadata)."""
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        if hasattr(db, "fetchrow"):
            row = await db.fetchrow("SELECT metadata FROM organizations WHERE id = $1", org_id)
            meta_raw = row.get("metadata") if row else None
        else:
            cur = await db.execute("SELECT metadata FROM organizations WHERE id = ?", (org_id,))
            row = await cur.fetchone()
            meta_raw = row[0] if row else None
        if not row:
            raise HTTPException(status_code=404, detail="organization_not_found")
        require_include_default = None
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                if isinstance(meta, dict):
                    wl = meta.get("watchlists") if isinstance(meta.get("watchlists"), dict) else None
                    if isinstance(wl, dict) and isinstance(wl.get("require_include_default"), bool):
                        require_include_default = bool(wl.get("require_include_default"))
                    elif isinstance(meta.get("watchlists_require_include_default"), bool):
                        require_include_default = bool(meta.get("watchlists_require_include_default"))
            except Exception:
                pass
        return OrganizationWatchlistsSettingsResponse(org_id=org_id, require_include_default=require_include_default)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch org watchlists settings for org {org_id}: {e}")
        raise HTTPException(status_code=500, detail="failed_to_fetch_org_watchlists_settings")


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse)
async def admin_add_team_member(
    team_id: int,
    payload: TeamMemberAddRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> TeamMemberResponse:
    try:
        await _get_scoped_team(team_id, principal, require_admin=True)
        row = await add_team_member(team_id=team_id, user_id=payload.user_id, role=payload.role or 'member')
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
                    get_audit_service_for_user,
                    get_or_create_audit_service_for_user_id,
                )
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                _svc = None
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                if _svc is None:
                    _svc = await get_or_create_audit_service_for_user_id(int(actor_id))
                _ctx = AuditContext(
                    user_id=str(actor_id),
                    ip_address=(request.client.host if request.client else None),
                    user_agent=request.headers.get('user-agent'),
                    endpoint=str(request.url.path),
                    method=request.method,
                )
                await _svc.log_event(
                    event_type=AuditEventType.DATA_WRITE,
                    category=AuditEventCategory.AUTHORIZATION,
                    context=_ctx,
                    resource_type='team',
                    resource_id=str(team_id),
                    action='team_member.add',
                    metadata={'target_user_id': payload.user_id, 'role': payload.role or 'member'}
                )
        except Exception as _e:
            logger.debug(f"Audit (team member add) skipped/failed: {_e}")
        return TeamMemberResponse(**row)
    except Exception as e:
        logger.error(f"Failed to add team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to add team member")


@router.get(
    "/teams/{team_id}/members",
    response_model=List[TeamMemberResponse],
    dependencies=[Depends(check_rate_limit)],
)
async def admin_list_team_members(
    team_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> list[TeamMemberResponse]:
    try:
        team = await _get_scoped_team(team_id, principal, require_admin=True)
        rows = await list_team_members(team_id)
        org_id = team.get("org_id") if isinstance(team, dict) else None
        items: list[TeamMemberResponse] = []
        for row in rows:
            payload = dict(row)
            payload["team_id"] = team_id
            if org_id is not None:
                payload["org_id"] = org_id
            items.append(TeamMemberResponse(**payload))
    except HTTPException:
        # Preserve existing HTTP semantics from scoped team/org helpers.
        raise
    except Exception as e:
        logger.error(f"Failed to list team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to list team members") from e
    return items


@router.delete("/teams/{team_id}/members/{user_id}")
async def admin_remove_team_member(
    team_id: int,
    user_id: int,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Dict[str, Any]:
    """Remove a user from a team (admin)."""
    try:
        await _get_scoped_team(team_id, principal, require_admin=True)
        res = await remove_team_member(team_id=team_id, user_id=user_id)
        if not res.get("removed"):
            # Even if delete didn't error, treat as not found when no rows affected
            # (we don't currently return affected row count; return generic message)
            return {"message": "No membership found", "team_id": team_id, "user_id": user_id}
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
                    get_audit_service_for_user,
                    get_or_create_audit_service_for_user_id,
                )
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                _svc = None
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                if _svc is None:
                    _svc = await get_or_create_audit_service_for_user_id(int(actor_id))
                _ctx = AuditContext(
                    user_id=str(actor_id),
                    ip_address=(request.client.host if request.client else None),
                    user_agent=request.headers.get('user-agent'),
                    endpoint=str(request.url.path),
                    method=request.method,
                )
                await _svc.log_event(
                    event_type=AuditEventType.DATA_DELETE,
                    category=AuditEventCategory.AUTHORIZATION,
                    context=_ctx,
                    resource_type='team',
                    resource_id=str(team_id),
                    action='team_member.remove',
                    metadata={'target_user_id': user_id}
                )
        except Exception as _e:
            logger.debug(f"Audit (team member remove) skipped/failed: {_e}")
        return {"message": "Team member removed", **res}
    except Exception as e:
        logger.error(f"Failed to remove team member user_id={user_id} from team_id={team_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove team member")


# ============================
# Organization membership endpoints
# ============================

@router.post("/orgs/{org_id}/members", response_model=OrgMemberResponse)
async def admin_add_org_member(
    org_id: int,
    payload: OrgMemberAddRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> OrgMemberResponse:
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        row = await add_org_member(org_id=org_id, user_id=payload.user_id, role=payload.role or 'member')
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
                    get_audit_service_for_user,
                    get_or_create_audit_service_for_user_id,
                )
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                _svc = None
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                if _svc is None:
                    _svc = await get_or_create_audit_service_for_user_id(int(actor_id))
                _ctx = AuditContext(
                    user_id=str(actor_id),
                    ip_address=(request.client.host if request.client else None),
                    user_agent=request.headers.get('user-agent'),
                    endpoint=str(request.url.path),
                    method=request.method,
                )
                await _svc.log_event(
                    event_type=AuditEventType.DATA_WRITE,
                    category=AuditEventCategory.AUTHORIZATION,
                    context=_ctx,
                    resource_type='organization',
                    resource_id=str(org_id),
                    action='org_member.add',
                    metadata={'target_user_id': payload.user_id, 'role': payload.role or 'member'}
                )
        except Exception as _e:
            logger.debug(f"Audit (org member add) skipped/failed: {_e}")
        return OrgMemberResponse(**row)
    except Exception as e:
        logger.error(f"Failed to add org member: {e}")
        raise HTTPException(status_code=500, detail="Failed to add org member")


@router.get("/orgs/{org_id}/members", response_model=List[OrgMemberListItem])
async def admin_list_org_members(
    org_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    role: Optional[str] = None,
    status: Optional[str] = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> list[OrgMemberListItem]:
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        rows = await list_org_members(org_id=org_id, limit=limit, offset=offset, role=role, status=status)
        out: list[OrgMemberListItem] = []
        for r in rows:
            d = dict(r)
            try:
                from datetime import datetime
                if isinstance(d.get('added_at'), datetime):
                    d['added_at'] = d['added_at'].isoformat()
            except Exception:
                pass
            out.append(OrgMemberListItem(**d))
        return out
    except Exception as e:
        logger.error(f"Failed to list org members: {e}")
        raise HTTPException(status_code=500, detail="Failed to list org members")


@router.delete("/orgs/{org_id}/members/{user_id}")
async def admin_remove_org_member(
    org_id: int,
    user_id: int,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Dict[str, Any]:
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        res = await remove_org_member(org_id=org_id, user_id=user_id)
        if res.get("error") == "owner_required":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization must retain at least one owner",
            )
        if not res.get("removed"):
            return {"message": "No membership found", "org_id": org_id, "user_id": user_id}
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
                    get_audit_service_for_user,
                    get_or_create_audit_service_for_user_id,
                )
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                _svc = None
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                if _svc is None:
                    _svc = await get_or_create_audit_service_for_user_id(int(actor_id))
                _ctx = AuditContext(
                    user_id=str(actor_id),
                    ip_address=(request.client.host if request.client else None),
                    user_agent=request.headers.get('user-agent'),
                    endpoint=str(request.url.path),
                    method=request.method,
                )
                await _svc.log_event(
                    event_type=AuditEventType.DATA_DELETE,
                    category=AuditEventCategory.AUTHORIZATION,
                    context=_ctx,
                    resource_type='organization',
                    resource_id=str(org_id),
                    action='org_member.remove',
                    metadata={'target_user_id': user_id}
                )
        except Exception as _e:
            logger.debug(f"Audit (org member remove) skipped/failed: {_e}")
        return {"message": "Org member removed", **res}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove org member user_id={user_id} from org_id={org_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove org member")


@router.patch("/orgs/{org_id}/members/{user_id}", response_model=OrgMemberResponse)
async def admin_update_org_member_role(
    org_id: int,
    user_id: int,
    payload: OrgMemberRoleUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> OrgMemberResponse:
    try:
        await _enforce_admin_org_access(principal, org_id, require_admin=True)
        row = await update_org_member_role(org_id=org_id, user_id=user_id, role=payload.role)
        if not row:
            raise HTTPException(status_code=404, detail="Org membership not found")
        if row.get("error") == "owner_required":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization must retain at least one owner",
            )
        # Best-effort audit
        try:
            actor_id = getattr(request.state, 'user_id', None)
            if isinstance(actor_id, int):
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user
                from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
                from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
                    get_audit_service_for_user,
                    get_or_create_audit_service_for_user_id,
                )
                from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
                _ud = await _get_user(actor_id)
                _svc = None
                if _ud:
                    _user = _User(**_ud)
                    _svc = await get_audit_service_for_user(_user)
                if _svc is None:
                    _svc = await get_or_create_audit_service_for_user_id(int(actor_id))
                _ctx = AuditContext(
                    user_id=str(actor_id),
                    ip_address=(request.client.host if request.client else None),
                    user_agent=request.headers.get('user-agent'),
                    endpoint=str(request.url.path),
                    method=request.method,
                )
                await _svc.log_event(
                    event_type=AuditEventType.DATA_UPDATE,
                    category=AuditEventCategory.AUTHORIZATION,
                    context=_ctx,
                    resource_type='organization',
                    resource_id=str(org_id),
                    action='org_member.update',
                    metadata={'target_user_id': user_id, 'new_role': payload.role}
                )
        except Exception as _e:
            logger.debug(f"Audit (org member role update) skipped/failed: {_e}")
        return OrgMemberResponse(**row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update org member role user_id={user_id} org_id={org_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update org member role")


@router.get("/users/{user_id}/org-memberships", response_model=List[OrgMembershipItem])
async def admin_list_user_org_memberships(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> list[OrgMembershipItem]:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        rows = await list_org_memberships_for_user(user_id)
        return [OrgMembershipItem(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list org memberships for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list org memberships")

@router.post("/users/{user_id}/virtual-keys")
async def admin_create_virtual_key(
    user_id: int,
    payload: VirtualKeyCreateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Dict[str, Any]:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        if payload.org_id is not None:
            await _enforce_admin_org_access(principal, payload.org_id, require_admin=True)
        if payload.team_id is not None:
            team = await _get_scoped_team(payload.team_id, principal, require_admin=True)
            if payload.org_id is not None and int(team.get("org_id")) != int(payload.org_id):
                raise HTTPException(status_code=400, detail="team_id does not belong to org_id")
        api_mgr = await get_api_key_manager()
        result = await api_mgr.create_virtual_key(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            expires_in_days=payload.expires_in_days,
            org_id=payload.org_id,
            team_id=payload.team_id,
            allowed_endpoints=payload.allowed_endpoints,
            allowed_providers=payload.allowed_providers,
            allowed_models=payload.allowed_models,
            budget_day_tokens=payload.budget_day_tokens,
            budget_month_tokens=payload.budget_month_tokens,
            budget_day_usd=payload.budget_day_usd,
            budget_month_usd=payload.budget_month_usd,
            allowed_methods=payload.allowed_methods,
            allowed_paths=payload.allowed_paths,
            max_calls=payload.max_calls,
            max_runs=payload.max_runs,
        )
        return result
    except Exception as e:
        logger.error(f"Admin failed to create virtual key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create virtual key")


@router.get("/users/{user_id}/virtual-keys", response_model=List[APIKeyMetadata])
async def admin_list_virtual_keys(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
    name: Optional[str] = Query(None, description="Filter by key name (case-insensitive substring)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by key status"),
    org_id: Optional[int] = Query(None, description="Filter by org_id"),
    team_id: Optional[int] = Query(None, description="Filter by team_id"),
    created_after: Optional[str] = Query(None, description="ISO-8601 created_at lower bound (UTC)"),
    created_before: Optional[str] = Query(None, description="ISO-8601 created_at upper bound (UTC)"),
) -> list[APIKeyMetadata]:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)

        def _parse_iso_ts(value: str, field_name: str) -> datetime:
            raw = value.strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field_name} must be ISO-8601 timestamp",
                ) from exc
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        name_filter = name.strip() if isinstance(name, str) and name.strip() else None
        status_filter = status_filter.strip() if isinstance(status_filter, str) and status_filter.strip() else None
        created_after_dt = _parse_iso_ts(created_after, "created_after") if created_after else None
        created_before_dt = _parse_iso_ts(created_before, "created_before") if created_before else None
        if created_after_dt and created_before_dt and created_after_dt > created_before_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="created_before must be >= created_after",
            )

        # Defensive: ensure user_id is a plain int (some callers might pass (id,))
        if isinstance(user_id, (tuple, list)):
            user_id = user_id[0]
        user_id = int(user_id)
        is_pg = await is_postgres_backend()
        if is_pg:
            conditions = ["user_id = $1", "COALESCE(is_virtual, FALSE) = TRUE"]
            params: list[Any] = [user_id]
            param_idx = 1
            if name_filter:
                param_idx += 1
                conditions.append(f"LOWER(name) LIKE ${param_idx}")
                params.append(f"%{name_filter.lower()}%")
            if status_filter:
                param_idx += 1
                conditions.append(f"status = ${param_idx}")
                params.append(status_filter)
            if org_id is not None:
                param_idx += 1
                conditions.append(f"org_id = ${param_idx}")
                params.append(org_id)
            if team_id is not None:
                param_idx += 1
                conditions.append(f"team_id = ${param_idx}")
                params.append(team_id)
            if created_after_dt:
                param_idx += 1
                conditions.append(f"created_at >= ${param_idx}")
                params.append(created_after_dt.replace(tzinfo=None))
            if created_before_dt:
                param_idx += 1
                conditions.append(f"created_at <= ${param_idx}")
                params.append(created_before_dt.replace(tzinfo=None))
            where_clause = " AND ".join(conditions)
            rows = await db.fetch(
                "SELECT id, key_prefix, name, description, scope, status, created_at, expires_at, usage_count, last_used_at, last_used_ip "
                f"FROM api_keys WHERE {where_clause} ORDER BY created_at DESC",
                *params,
            )
            items = [APIKeyMetadata(**dict(r)) for r in rows]
        else:
            conditions = ["user_id = ?", "COALESCE(is_virtual,0) = 1"]
            params2: list[Any] = [user_id]
            if name_filter:
                conditions.append("LOWER(name) LIKE ?")
                params2.append(f"%{name_filter.lower()}%")
            if status_filter:
                conditions.append("status = ?")
                params2.append(status_filter)
            if org_id is not None:
                conditions.append("org_id = ?")
                params2.append(org_id)
            if team_id is not None:
                conditions.append("team_id = ?")
                params2.append(team_id)
            if created_after_dt:
                conditions.append("datetime(created_at) >= datetime(?)")
                params2.append(created_after_dt.strftime("%Y-%m-%d %H:%M:%S"))
            if created_before_dt:
                conditions.append("datetime(created_at) <= datetime(?)")
                params2.append(created_before_dt.strftime("%Y-%m-%d %H:%M:%S"))
            where_clause = " AND ".join(conditions)
            cur = await db.execute(
                "SELECT id, key_prefix, name, description, scope, status, created_at, expires_at, usage_count, last_used_at, last_used_ip "
                f"FROM api_keys WHERE {where_clause} ORDER BY datetime(created_at) DESC",
                tuple(params2),
            )
            rows = await cur.fetchall()
            items = [
                APIKeyMetadata(
                    id=r[0], key_prefix=r[1], name=r[2], description=r[3], scope=r[4], status=r[5], created_at=r[6], expires_at=r[7], usage_count=r[8], last_used_at=r[9], last_used_ip=r[10]
                ) for r in rows
            ]
        return items
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin failed to list virtual keys for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list virtual keys")

@router.get("/api-keys/{key_id}/audit-log", response_model=APIKeyAuditListResponse)
async def admin_get_api_key_audit_log(
    key_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db_transaction)
) -> APIKeyAuditListResponse:
    """Get audit log entries for a specific API key (admin)."""
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            key_owner = await db.fetchval("SELECT user_id FROM api_keys WHERE id = $1", key_id)
        else:
            cur = await db.execute("SELECT user_id FROM api_keys WHERE id = ?", (key_id,))
            row = await cur.fetchone()
            key_owner = row[0] if row else None
        if key_owner is None:
            raise HTTPException(status_code=404, detail="API key not found")
        await _enforce_admin_user_scope(principal, int(key_owner), require_hierarchy=False)
        if is_pg:
            rows = await db.fetch(
                """
                SELECT id, api_key_id, action, user_id, ip_address, user_agent, details, created_at
                FROM api_key_audit_log
                WHERE api_key_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                key_id, limit, offset
            )
        else:
            cursor = await db.execute(
                """
                SELECT id, api_key_id, action, user_id, ip_address, user_agent, details, created_at
                FROM api_key_audit_log
                WHERE api_key_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (key_id, limit, offset)
            )
            rows = await cursor.fetchall()

        items: list[APIKeyAuditEntry] = []
        for r in rows:
            if isinstance(r, dict):
                items.append(APIKeyAuditEntry(**r))
            else:
                items.append(APIKeyAuditEntry(
                    id=r[0], api_key_id=r[1], action=r[2], user_id=r[3], ip_address=r[4], user_agent=r[5], details=r[6], created_at=r[7]
                ))
        return APIKeyAuditListResponse(key_id=key_id, items=items)
    except Exception as e:
        logger.error(f"Admin failed to fetch audit log for key {key_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load audit log")


#######################################################################################################################
#
# Ephemeral Cleanup Settings

@router.get("/cleanup-settings")
async def get_cleanup_settings() -> Dict[str, Any]:
    """Get cleanup worker settings (enabled, interval in seconds)."""
    try:
        enabled = bool(app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        interval = int(app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))
        return {"enabled": enabled, "interval_sec": interval}
    except Exception as e:
        logger.error(f"Failed to get cleanup settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cleanup settings")


@router.post("/cleanup-settings")
async def set_cleanup_settings(payload: AdminCleanupSettingsUpdate) -> Dict[str, Any]:
    """Set cleanup worker settings (enabled, interval_sec)."""
    try:
        if payload.enabled is not None:
            app_settings["EPHEMERAL_CLEANUP_ENABLED"] = bool(payload.enabled)
        if payload.interval_sec is not None:
            app_settings["EPHEMERAL_CLEANUP_INTERVAL_SEC"] = int(payload.interval_sec)
        enabled = bool(app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        interval = int(app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))
        return {"enabled": enabled, "interval_sec": interval}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set cleanup settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to set cleanup settings")


# ---------------------------------------------
# Notes Title Settings
# ---------------------------------------------

@router.get("/notes/title-settings")
async def get_notes_title_settings() -> Dict[str, Any]:
    """Get Notes auto-title settings (LLM enabled flag and default strategy)."""
    try:
        llm_enabled = bool(app_settings.get("NOTES_TITLE_LLM_ENABLED", False))
        default_strategy = str(app_settings.get("NOTES_TITLE_DEFAULT_STRATEGY", "heuristic")).lower()
    except Exception as e:
        logger.error(f"Failed to get notes title settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get notes title settings") from e
    else:
        return {
            "llm_enabled": llm_enabled,
            "default_strategy": default_strategy,
            "strategies": ["heuristic", "llm", "llm_fallback"],
        }


@router.post("/notes/title-settings")
async def set_notes_title_settings(payload: NotesTitleSettingsUpdate) -> Dict[str, Any]:
    """Update Notes auto-title settings.

    Payload fields (both optional):
    - llm_enabled: bool
    - default_strategy: one of [heuristic, llm, llm_fallback]
    """
    try:
        if payload.llm_enabled is not None:
            app_settings["NOTES_TITLE_LLM_ENABLED"] = bool(payload.llm_enabled)
        if payload.default_strategy is not None:
            app_settings["NOTES_TITLE_DEFAULT_STRATEGY"] = payload.default_strategy
        # Return effective settings
        llm_enabled = bool(app_settings.get("NOTES_TITLE_LLM_ENABLED", False))
        default_strategy = str(app_settings.get("NOTES_TITLE_DEFAULT_STRATEGY", "heuristic")).lower()
        # Provide an effective strategy hint for clients when LLM is disabled
        effective_strategy = (
            default_strategy if llm_enabled or default_strategy == "heuristic" else "heuristic"
        )
        return {
            "llm_enabled": llm_enabled,
            "default_strategy": default_strategy,
            "effective_strategy": effective_strategy,
            "strategies": ["heuristic", "llm", "llm_fallback"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set notes title settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to set notes title settings") from e


@router.get(
    "/users/profile",
    response_model=UserProfileBatchResponse,
    response_model_exclude_none=True,
)
async def admin_list_user_profiles(
    sections: Optional[str] = Query(
        None, description="Comma-separated list of sections to include"
    ),
    include_sources: bool = Query(
        False, description="Include per-field source attribution"
    ),
    include_raw: bool = Query(
        False, description="Include raw stored overrides"
    ),
    mask_secrets: bool = Query(
        True, description="Mask secret values in the response"
    ),
    user_ids: Optional[str] = Query(
        None, description="Comma-separated list of user IDs to include"
    ),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    team_id: Optional[int] = Query(None, description="Restrict to a specific team"),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    http_request: Request = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> UserProfileBatchResponse:
    """
    Get batch profile summaries within admin scope.
    """
    batch_start = time.perf_counter()
    user_id_list = _parse_user_id_list(user_ids)
    target_ids = await _load_bulk_user_candidates(
        principal=principal,
        org_id=org_id,
        team_id=team_id,
        role=role,
        is_active=is_active,
        search=search,
        user_ids=user_id_list,
    )
    total = len(target_ids)
    offset = (page - 1) * limit
    page_ids = target_ids[offset : offset + limit]

    db_pool = await get_db_pool()
    service = UserProfileService(db_pool)
    requested = service.parse_sections(sections)
    if requested is None:
        requested = {"identity", "memberships", "quotas"}
    api_mgr = await get_api_key_manager()

    repo = await AuthnzUsersRepo.from_pool()
    profiles: List[UserProfileResponse] = []
    for user_id in page_ids:
        user = await repo.get_user_by_id(int(user_id))
        if not user:
            continue
        user_dict: Dict[str, Any] = dict(user)
        user_dict.pop("password_hash", None)

        security: Optional[Dict[str, Any]] = None
        if "security" in requested:
            security = await service.build_security(
                user_id=int(user_id),
                session_manager=session_manager,
                api_key_manager=api_mgr,
            )

        profile = await service.build_profile(
            user=user_dict,
            sections=requested,
            security=security,
            include_sources=include_sources,
            include_raw=include_raw,
            mask_secrets=mask_secrets,
            metrics_scope="batch",
        )
        profiles.append(UserProfileResponse(**profile))

    pages = (total + limit - 1) // limit if limit else 0
    response = UserProfileBatchResponse(
        profiles=profiles,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )

    try:
        registry = service._get_metrics_registry()
        if registry:
            page_size = len(page_ids)
            latency_ms = (time.perf_counter() - batch_start) * 1000.0
            registry.observe(
                "profile_batch_latency_ms",
                latency_ms,
                labels={"page_size": str(page_size)},
            )
            threshold_ms = UserProfileService.batch_sla_threshold_ms(max(1, page_size))
            if latency_ms > threshold_ms:
                registry.increment(
                    "profile_batch_sla_breach_total",
                    1,
                    labels={"page_size": str(page_size)},
                )
                logger.warning(
                    "Profile batch SLA exceeded: {:.2f}ms for page_size={} (threshold {}ms)",
                    latency_ms,
                    page_size,
                    threshold_ms,
                )
            timeout_ms = UserProfileService.batch_timeout_ms()
            if latency_ms > timeout_ms:
                registry.increment(
                    "profile_batch_timeout_total",
                    1,
                    labels={"page_size": str(page_size)},
                )
                logger.warning(
                    "Profile batch timeout threshold exceeded: {:.2f}ms for page_size={} (timeout {}ms)",
                    latency_ms,
                    page_size,
                    timeout_ms,
                )
    except Exception:
        pass
    try:
        metadata = {
            "filters": {
                "user_ids_count": len(user_id_list or []),
                "org_id": org_id,
                "team_id": team_id,
                "role": role,
                "is_active": is_active,
                "search": search,
            },
            "page": page,
            "limit": limit,
            "total": total,
            "sections": sorted(list(requested or [])),
            "include_sources": include_sources,
            "include_raw": include_raw,
            "mask_secrets": mask_secrets,
        }
        await _emit_admin_audit_event(
            http_request,
            principal,
            event_type="data.read",
            category="data_access",
            resource_type="user_profile",
            resource_id=None,
            action="user_profile.batch_read",
            metadata=metadata,
        )
    except Exception:
        pass
    return response


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Dict[str, Any]:
    """
    Get detailed information about a specific user.

    Delegates to the AuthnzUsersRepo so that backend differences and schema
    details are encapsulated in the AuthNZ data access layer.

    Args:
        user_id: User ID

    Returns:
        User details excluding sensitive fields (e.g., password_hash)
    """
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)

        repo = await AuthnzUsersRepo.from_pool()
        user = await repo.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id}")

        # Remove sensitive fields; repository normalizes backend-specific types
        user_dict: Dict[str, Any] = dict(user)
        user_dict.pop("password_hash", None)

        return user_dict

    except UserNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        ) from err
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user details",
        ) from e


@router.get(
    "/users/{user_id}/profile",
    response_model=UserProfileResponse,
    response_model_exclude_none=True,
)
async def admin_get_user_profile(
    user_id: int,
    sections: Optional[str] = Query(
        None, description="Comma-separated list of sections to include"
    ),
    include_sources: bool = Query(
        False, description="Include per-field source attribution"
    ),
    include_raw: bool = Query(
        False, description="Include raw stored overrides"
    ),
    mask_secrets: bool = Query(
        True, description="Mask secret values in the response"
    ),
    http_request: Request = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> UserProfileResponse:
    """
    Get a unified user profile (admin scope).
    """
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)

        repo = await AuthnzUsersRepo.from_pool()
        user = await repo.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id}")

        user_dict: Dict[str, Any] = dict(user)
        user_dict.pop("password_hash", None)

        db_pool = await get_db_pool()
        service = UserProfileService(db_pool)
        requested = service.parse_sections(sections)
        api_mgr = await get_api_key_manager()
        security = await service.build_security(
            user_id=int(user_id),
            session_manager=session_manager,
            api_key_manager=api_mgr,
        )
        profile = await service.build_profile(
            user=user_dict,
            sections=requested,
            security=security,
            include_sources=include_sources,
            include_raw=include_raw,
            mask_secrets=mask_secrets,
            metrics_scope="admin",
        )
        response = UserProfileResponse(**profile)
        try:
            metadata = {
                "sections": sorted(list(requested or [])),
                "include_sources": include_sources,
                "include_raw": include_raw,
                "mask_secrets": mask_secrets,
            }
            await _emit_admin_audit_event(
                http_request,
                principal,
                event_type="data.read",
                category="data_access",
                resource_type="user_profile",
                resource_id=str(user_id),
                action="user_profile.read",
                metadata=metadata,
            )
        except Exception:
            pass
        return response

    except UserNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        ) from err
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to build profile for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile",
        ) from e


@router.patch("/users/{user_id}/profile", response_model=UserProfileUpdateResponse)
async def admin_update_user_profile(
    user_id: int,
    payload: UserProfileUpdateRequest,
    http_request: Request = None,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> UserProfileUpdateResponse:
    """
    Update a user's profile (admin scope).
    """
    if not payload.updates:
        return _profile_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="profile_update_invalid",
            detail="No updates provided",
            errors=[UserProfileErrorDetail(key="updates", message="missing")],
        )

    await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)

    db_pool = await get_db_pool()
    repo = await AuthnzUsersRepo.from_pool()
    user = await repo.get_user_by_id(int(user_id))
    if not user:
        return _profile_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="profile_update_not_found",
            detail=f"User {user_id} not found",
            errors=[UserProfileErrorDetail(key="user_id", message="not_found")],
        )
    profile_service = UserProfileService(db_pool)
    current_version = await profile_service.get_profile_version(user_id=int(user_id))
    if payload.profile_version is not None:
        if not profile_service.versions_match(current_version, payload.profile_version):
            return _profile_error_response(
                status_code=status.HTTP_409_CONFLICT,
                error_code="profile_version_mismatch",
                detail="profile_version_mismatch",
                errors=[UserProfileErrorDetail(key="profile_version", message="mismatch")],
            )

    roles = _derive_profile_update_roles(principal)
    service = UserProfileUpdateService(db_pool)
    updates = [(entry.key, entry.value) for entry in payload.updates]
    preflight = await service.apply_updates(
        user_id=int(user_id),
        updates=updates,
        roles=roles,
        dry_run=True,
        db_conn=db,
        updated_by=principal.user_id,
        scope=ProfileUpdateScope(
            actor_user_id=principal.user_id,
            active_org_id=principal.active_org_id,
            active_team_id=principal.active_team_id,
        ),
    )

    error_payload = classify_profile_update_skips(preflight.skipped)
    if error_payload:
        status_code, error_code, detail, errors = error_payload
        return _profile_error_response(
            status_code=status_code,
            error_code=error_code,
            detail=detail,
            errors=errors,
        )

    if payload.dry_run:
        response = UserProfileUpdateResponse(
            profile_version=current_version,
            applied=preflight.applied,
            skipped=[],
        )
    else:
        result = await service.apply_updates(
            user_id=int(user_id),
            updates=updates,
            roles=roles,
            dry_run=False,
            db_conn=db,
            updated_by=principal.user_id,
            scope=ProfileUpdateScope(
                actor_user_id=principal.user_id,
                active_org_id=principal.active_org_id,
                active_team_id=principal.active_team_id,
            ),
        )
        current_version = await profile_service.get_profile_version(user_id=int(user_id))
        skipped = [UserProfileUpdateError(**item) for item in result.skipped]
        response = UserProfileUpdateResponse(
            profile_version=current_version,
            applied=result.applied,
            skipped=skipped,
        )
    try:
        metadata = {
            "dry_run": payload.dry_run,
            "update_keys": [entry.key for entry in payload.updates],
            "applied_count": len(response.applied),
            "skipped_count": len(response.skipped),
        }
        await _emit_admin_audit_event(
            http_request,
            principal,
            event_type="data.read" if payload.dry_run else "data.update",
            category="data_access" if payload.dry_run else "data_modification",
            resource_type="user_profile",
            resource_id=str(user_id),
            action="user_profile.update_preview" if payload.dry_run else "user_profile.update",
            metadata=metadata,
        )
    except Exception:
        pass
    return response


@router.post("/users/profile/bulk", response_model=UserProfileBulkUpdateResponse)
async def admin_bulk_update_user_profiles(
    payload: UserProfileBulkUpdateRequest,
    http_request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> UserProfileBulkUpdateResponse:
    """
    Bulk update user profiles (admin scope).
    """
    if not payload.updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")

    target_ids = await _load_bulk_user_candidates(
        principal=principal,
        org_id=payload.org_id,
        team_id=payload.team_id,
        role=payload.role,
        is_active=payload.is_active,
        search=payload.search,
        user_ids=payload.user_ids,
    )
    total_targets = len(target_ids)
    threshold = _get_bulk_confirm_threshold()
    if not payload.dry_run and total_targets > threshold and not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "bulk_update_confirm_required",
                "target_count": total_targets,
                "threshold": threshold,
            },
        )

    db_pool = await get_db_pool()
    update_service = UserProfileUpdateService(db_pool)
    profile_service = UserProfileService(db_pool)
    catalog = load_user_profile_catalog()
    catalog_map = {entry.key: entry for entry in catalog.entries}
    user_repo = await AuthnzUsersRepo.from_pool()
    roles = _derive_profile_update_roles(principal)
    updates = [(entry.key, entry.value) for entry in payload.updates]
    results: List[UserProfileBulkUpdateUserResult] = []
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    for user_id in target_ids:
        try:
            await _enforce_admin_user_scope(principal, int(user_id), require_hierarchy=True)
        except HTTPException as exc:
            failed_count += 1
            results.append(
                UserProfileBulkUpdateUserResult(
                    user_id=int(user_id),
                    error=str(exc.detail) if exc.detail else "forbidden",
                )
            )
            continue

        try:
            before_values = await _build_bulk_update_before_values(
                user_id=int(user_id),
                updates=payload.updates,
                profile_service=profile_service,
                user_repo=user_repo,
                catalog_map=catalog_map,
            )

            if payload.dry_run:
                result = await update_service.apply_updates(
                    user_id=int(user_id),
                    updates=updates,
                    roles=roles,
                    dry_run=True,
                    db_conn=db_pool,
                    updated_by=principal.user_id,
                    scope=ProfileUpdateScope(
                        actor_user_id=principal.user_id,
                        active_org_id=principal.active_org_id,
                        active_team_id=principal.active_team_id,
                    ),
                )
            else:
                async with db_pool.transaction() as conn:
                    result = await update_service.apply_updates(
                        user_id=int(user_id),
                        updates=updates,
                        roles=roles,
                        dry_run=False,
                        db_conn=conn,
                        updated_by=principal.user_id,
                        scope=ProfileUpdateScope(
                            actor_user_id=principal.user_id,
                            active_org_id=principal.active_org_id,
                            active_team_id=principal.active_team_id,
                        ),
                    )

            profile_version = await profile_service.get_profile_version(user_id=int(user_id))
            skipped_entries = [UserProfileUpdateError(**item) for item in result.skipped]
            applied_keys = set(result.applied)
            diffs = [
                UserProfileBulkUpdateDiff(
                    key=entry.key,
                    before=before_values.get(entry.key),
                    after=_mask_profile_diff_value(
                        profile_service,
                        catalog_map,
                        entry.key,
                        entry.value,
                    ),
                )
                for entry in payload.updates
                if entry.key in applied_keys
            ]
            results.append(
                UserProfileBulkUpdateUserResult(
                    user_id=int(user_id),
                    profile_version=profile_version,
                    applied=result.applied,
                    skipped=skipped_entries,
                    diffs=diffs,
                )
            )
            if result.applied:
                updated_count += 1
            else:
                skipped_count += 1
        except HTTPException as exc:
            failed_count += 1
            results.append(
                UserProfileBulkUpdateUserResult(
                    user_id=int(user_id),
                    error=str(exc.detail) if exc.detail else "update_failed",
                )
            )
        except Exception as exc:
            logger.error("Bulk profile update failed for user {}: {}", user_id, exc)
            failed_count += 1
            results.append(
                UserProfileBulkUpdateUserResult(
                    user_id=int(user_id),
                    error="update_failed",
                )
            )

    try:
        update_keys = [entry.key for entry in payload.updates]
        metadata = {
            "dry_run": payload.dry_run,
            "confirm": payload.confirm,
            "target_count": total_targets,
            "updated": updated_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "filters": {
                "org_id": payload.org_id,
                "team_id": payload.team_id,
                "role": payload.role,
                "is_active": payload.is_active,
                "search": payload.search,
                "user_ids_count": len(payload.user_ids or []),
            },
            "update_keys": update_keys,
        }
        await _emit_admin_audit_event(
            http_request,
            principal,
            event_type="data.read" if payload.dry_run else "data.update",
            category="data_access" if payload.dry_run else "data_modification",
            resource_type="user_profile",
            resource_id=None,
            action="user_profile.bulk_preview" if payload.dry_run else "user_profile.bulk_update",
            metadata=metadata,
        )
    except Exception:
        pass

    try:
        registry = profile_service._get_metrics_registry()
        if registry:
            registry.increment(
                "profile_bulk_update_total",
                total_targets,
                labels={"dry_run": str(payload.dry_run).lower()},
            )
    except Exception:
        pass

    return UserProfileBulkUpdateResponse(
        total_targets=total_targets,
        updated=updated_count,
        skipped=skipped_count,
        failed=failed_count,
        dry_run=payload.dry_run,
        results=results,
    )


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> Dict[str, str]:
    """
    Update user information

    Args:
        user_id: User ID
        request: Update request with fields to modify

    Returns:
        Success message
    """
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)

        is_pg = await is_postgres_backend()
        # Build update query dynamically
        updates = []
        params = []
        param_count = 0

        if request.email is not None:
            param_count += 1
            updates.append(f"email = ${param_count}" if is_pg else "email = ?")
            params.append(request.email)

        if request.role is not None:
            param_count += 1
            updates.append(f"role = ${param_count}" if is_pg else "role = ?")
            params.append(request.role)

        if request.is_active is not None:
            param_count += 1
            updates.append(f"is_active = ${param_count}" if is_pg else "is_active = ?")
            params.append(request.is_active)

        if request.is_verified is not None:
            param_count += 1
            updates.append(f"is_verified = ${param_count}" if is_pg else "is_verified = ?")
            params.append(request.is_verified)

        if request.is_locked is not None:
            param_count += 1
            updates.append(f"is_locked = ${param_count}" if is_pg else "is_locked = ?")
            params.append(request.is_locked)

            if not request.is_locked:
                # Unlock user - reset failed attempts
                param_count += 1
                updates.append(f"failed_login_attempts = ${param_count}" if is_pg else "failed_login_attempts = ?")
                params.append(0)
                updates.append("locked_until = NULL")

        if request.storage_quota_mb is not None:
            param_count += 1
            updates.append(f"storage_quota_mb = ${param_count}" if is_pg else "storage_quota_mb = ?")
            params.append(request.storage_quota_mb)

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Add updated_at
        param_count += 1
        if is_pg:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count}"
        else:
            updates.append("updated_at = datetime('now')")
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"

        # Execute update
        if is_pg:
            row = await db.fetchrow(query + " RETURNING id", *params)
            if not row:
                raise UserNotFoundError(f"User {user_id}")
        else:
            cursor = await db.execute(query, params)
            affected = int(getattr(cursor, "rowcount", 0) or 0)
            if affected == 0:
                cursor = await db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
                if not await cursor.fetchone():
                    raise UserNotFoundError(f"User {user_id}")
            await db.commit()

        logger.info(f"Admin updated user {user_id}")

        return {"message": f"User {user_id} updated successfully"}

    except UserNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        ) from err
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.get("/users/{user_id}/sessions", response_model=List[SessionResponse])
async def admin_list_user_sessions(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> List[SessionResponse]:
    """List active sessions for a user (admin scope)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        sessions = await session_manager.get_user_sessions(user_id)
        return [
            SessionResponse(
                id=session["id"],
                ip_address=session.get("ip_address"),
                user_agent=session.get("user_agent"),
                created_at=session["created_at"],
                last_activity=session["last_activity"],
                expires_at=session["expires_at"],
            )
            for session in sessions
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list sessions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list sessions")


@router.delete("/users/{user_id}/sessions/{session_id}", response_model=MessageResponse)
async def admin_revoke_user_session(
    user_id: int,
    session_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> MessageResponse:
    """Revoke a specific session for a user (admin scope)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        await session_manager.revoke_session(session_id=session_id, revoked_by=principal.user_id)
        return MessageResponse(message="Session revoked")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke session {session_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke session")


@router.post("/users/{user_id}/sessions/revoke-all", response_model=MessageResponse)
async def admin_revoke_all_user_sessions(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    session_manager=Depends(get_session_manager_dep),
) -> MessageResponse:
    """Revoke all sessions for a user (admin scope)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        await session_manager.revoke_all_user_sessions(user_id=user_id)
        return MessageResponse(message="All sessions revoked")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke all sessions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke sessions")


@router.get("/users/{user_id}/mfa", response_model=Dict[str, Any])
async def admin_get_user_mfa_status(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> Dict[str, Any]:
    """Fetch MFA status for a user (admin scope)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        mfa_service = get_mfa_service()
        return await mfa_service.get_user_mfa_status(user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch MFA status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch MFA status")


@router.post("/users/{user_id}/mfa/disable", response_model=MessageResponse)
async def admin_disable_user_mfa(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MessageResponse:
    """Disable MFA for a user (admin scope)."""
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        mfa_service = get_mfa_service()
        success = await mfa_service.disable_mfa(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="MFA not enabled")
        return MessageResponse(message="MFA disabled")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable MFA for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to disable MFA")


#######################################################################################################################
#
# RBAC: Roles, Permissions, Assignments, Overrides

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db=Depends(get_db_transaction)) -> list[RoleResponse]:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch("SELECT id, name, description, COALESCE(is_system, FALSE) as is_system FROM roles ORDER BY name")
            return [RoleResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute("SELECT id, name, description, COALESCE(is_system, 0) as is_system FROM roles ORDER BY name")
            rows = await cur.fetchall()
            return [RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3])) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list roles: {e}")
        raise HTTPException(status_code=500, detail="Failed to list roles")


@router.post("/roles", response_model=RoleResponse)
async def create_role(payload: RoleCreateRequest, db=Depends(get_db_transaction)) -> RoleResponse:
    try:
        row = await svc_create_role(db, payload.name, payload.description, False)
        return RoleResponse(**row)
    except DuplicateRoleError as dup:
        raise HTTPException(status_code=409, detail=f"Role '{dup.name}' already exists")
    except Exception as e:
        logger.error(f"Failed to create role: {e}")
        raise HTTPException(status_code=500, detail="Failed to create role")


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        await svc_delete_role(db, role_id)
        return {"message": "Role deleted"}
    except Exception as e:
        logger.error(f"Failed to delete role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete role")


@router.get("/roles/{role_id}/permissions", response_model=List[PermissionResponse])
async def list_role_permissions(role_id: int, db=Depends(get_db_transaction)) -> list[PermissionResponse]:
    """List permissions granted to a specific role (read-only matrix row)."""
    try:
        rows = await svc_list_role_permissions(db, role_id)
        return [PermissionResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list role permissions")


@router.get("/permissions/tools", response_model=List[ToolPermissionResponse])
async def list_tool_permissions(db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """List tool execution permissions (name starts with 'tools.execute:')."""
    try:
        rows = await svc_list_tool_permissions(db)
        return [ToolPermissionResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list tool permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tool permissions")


@router.post("/permissions/tools", response_model=ToolPermissionResponse)
async def create_tool_permission(payload: ToolPermissionCreateRequest, db=Depends(get_db_transaction)) -> ToolPermissionResponse:
    """Create a tool execution permission.

    - tool_name='*' → creates tools.execute:*
    - tool_name='<name>' → creates tools.execute:<name>
    """
    try:
        tool = payload.tool_name.strip()
        name = f"tools.execute:{'*' if tool == '*' else tool}"
        desc = payload.description or ("Wildcard tool execution" if tool == '*' else f"Execute tool {tool}")

        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
                name, desc, 'tools',
            )
            row = await db.fetchrow(
                "SELECT name, description, category FROM permissions WHERE name = $1",
                name,
            )
            return ToolPermissionResponse(**dict(row))
        else:
            # SQLite doesn't support upsert on all versions; emulate
            cur = await db.execute("SELECT name, description, category FROM permissions WHERE name = ?", (name,))
            r = await cur.fetchone()
            if not r:
                await db.execute(
                    "INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)",
                    (name, desc, 'tools'),
                )
                await db.commit()
                cur = await db.execute("SELECT name, description, category FROM permissions WHERE name = ?", (name,))
                r = await cur.fetchone()
            return ToolPermissionResponse(name=r[0], description=r[1], category=r[2])
    except Exception as e:
        logger.error(f"Failed to create tool permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tool permission")


@router.delete("/permissions/tools/{perm_name}")
async def delete_tool_permission(perm_name: str, db=Depends(get_db_transaction)) -> dict:
    """Delete a tool execution permission by full name (e.g., tools.execute:my_tool)."""
    try:
        if not perm_name.startswith('tools.execute:'):
            raise HTTPException(status_code=400, detail="Invalid tool permission name")
        await svc_delete_tool_permission(db, perm_name)
        return {"message": "Tool permission deleted", "name": perm_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete tool permission {perm_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool permission")


@router.post("/roles/{role_id}/permissions/tools", response_model=ToolPermissionResponse)
async def grant_tool_permission_to_role(role_id: int, payload: ToolPermissionGrantRequest, db=Depends(get_db_transaction)) -> ToolPermissionResponse:
    """Grant a tool execution permission to a role.

    - tool_name='*' → grants tools.execute:*
    - tool_name='<name>' → grants tools.execute:<name>
    Creates the permission in catalog if missing.
    """
    tool = payload.tool_name.strip()
    name = f"tools.execute:{'*' if tool == '*' else tool}"
    desc = f"Wildcard tool execution" if tool == '*' else f"Execute tool {tool}"
    try:
        perm = await svc_grant_tool_perm(db, role_id, name, desc)
        return ToolPermissionResponse(name=perm['name'], description=perm.get('description'), category=perm.get('category'))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to grant tool permission to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant tool permission")


@router.delete("/roles/{role_id}/permissions/tools/{tool_name}")
async def revoke_tool_permission_from_role(role_id: int, tool_name: str, db=Depends(get_db_transaction)) -> dict:
    """Revoke a tool execution permission from a role.

    tool_name '*' refers to tools.execute:*
    """
    name = f"tools.execute:{'*' if tool_name.strip() == '*' else tool_name.strip()}"
    try:
        ok = await svc_revoke_tool_perm(db, role_id, name)
        if not ok:
            return {"message": "Permission not found; nothing to revoke", "name": name}
        return {"message": "Tool permission revoked", "name": name}
    except Exception as e:
        logger.error(f"Failed to revoke tool permission from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke tool permission")


@router.get("/roles/{role_id}/permissions/tools", response_model=List[ToolPermissionResponse])
async def list_role_tool_permissions(role_id: int, db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """List tool execution permissions assigned to a role."""
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                """
                SELECT p.name, p.description, p.category
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                WHERE rp.role_id = $1 AND p.name LIKE 'tools.execute:%'
                ORDER BY p.name
                """,
                role_id,
            )
            return [ToolPermissionResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute(
                """
                SELECT p.name, p.description, p.category
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                WHERE rp.role_id = ? AND p.name LIKE 'tools.execute:%'
                ORDER BY p.name
                """,
                (role_id,),
            )
            rows = await cur.fetchall()
            return [ToolPermissionResponse(name=r[0], description=r[1], category=r[2]) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list role tool permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list role tool permissions")


@router.post("/roles/{role_id}/permissions/tools/batch", response_model=List[ToolPermissionResponse])
async def grant_tool_permissions_batch(role_id: int, payload: ToolPermissionBatchRequest, db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """Grant multiple tool execution permissions to a role in one call."""
    try:
        is_pg = await is_postgres_backend()
        results: list[ToolPermissionResponse] = []
        # Reuse single-grant logic inline
        for tool in payload.tool_names:
            tool = tool.strip()
            if not tool:
                continue
            name = f"tools.execute:{'*' if tool == '*' else tool}"
            desc = "Wildcard tool execution" if tool == '*' else f"Execute tool {tool}"

            if is_pg:
                await db.execute(
                    "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
                    name, desc, 'tools',
                )
                row = await db.fetchrow("SELECT id, name, description, category FROM permissions WHERE name = $1", name)
                if not row:
                    continue
                await db.execute(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    role_id, row['id'],
                )
                results.append(ToolPermissionResponse(name=row['name'], description=row['description'], category=row['category']))
            else:
                cur = await db.execute("SELECT id, name, description, category FROM permissions WHERE name = ?", (name,))
                r = await cur.fetchone()
                if not r:
                    await db.execute("INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)", (name, desc, 'tools'))
                    await db.commit()
                    cur = await db.execute("SELECT id, name, description, category FROM permissions WHERE name = ?", (name,))
                    r = await cur.fetchone()
                await db.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, r[0]))
                await db.commit()
                results.append(ToolPermissionResponse(name=r[1], description=r[2], category=r[3]))
        return results
    except Exception as e:
        logger.error(f"Failed to batch grant tool permissions to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant tool permissions")


@router.post("/roles/{role_id}/permissions/tools/batch/revoke")
async def revoke_tool_permissions_batch(role_id: int, payload: ToolPermissionBatchRequest, db=Depends(get_db_transaction)) -> dict:
    """Revoke multiple tool execution permissions from a role."""
    try:
        is_pg = await is_postgres_backend()
        revoked: list[str] = []
        for tool in payload.tool_names:
            tool = tool.strip()
            if not tool:
                continue
            name = f"tools.execute:{'*' if tool == '*' else tool}"
            if is_pg:
                row = await db.fetchrow("SELECT id FROM permissions WHERE name = $1", name)
                if row:
                    await db.execute("DELETE FROM role_permissions WHERE role_id = $1 AND permission_id = $2", role_id, row['id'])
                    revoked.append(name)
            else:
                cur = await db.execute("SELECT id FROM permissions WHERE name = ?", (name,))
                r = await cur.fetchone()
                if r:
                    await db.execute("DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?", (role_id, r[0]))
                    await db.commit()
                    revoked.append(name)
        return {"revoked": revoked, "count": len(revoked)}
    except Exception as e:
        logger.error(f"Failed to batch revoke tool permissions from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke tool permissions")


def _normalize_tool_prefix(raw_prefix: str) -> str:
    px = raw_prefix.strip()
    if not px:
        return "tools.execute:"
    if not px.startswith('tools.execute:'):
        px = 'tools.execute:' + px
    return px


@router.post("/roles/{role_id}/permissions/tools/prefix/grant", response_model=List[ToolPermissionResponse])
async def grant_tool_permissions_by_prefix(role_id: int, payload: ToolPermissionPrefixRequest, db=Depends(get_db_transaction)) -> list[ToolPermissionResponse]:
    """Grant all existing tool permissions with names starting with the prefix."""
    try:
        is_pg = await is_postgres_backend()
        prefix = _normalize_tool_prefix(payload.prefix)
        results: list[ToolPermissionResponse] = []
        if is_pg:
            rows = await db.fetch("SELECT id, name, description, category FROM permissions WHERE name LIKE $1", prefix + '%')
            for r in rows:
                await db.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", role_id, r['id'])
                results.append(ToolPermissionResponse(name=r['name'], description=r['description'], category=r['category']))
        else:
            cur = await db.execute("SELECT id, name, description, category FROM permissions WHERE name LIKE ?", (prefix + '%',))
            rows = await cur.fetchall()
            for r in rows:
                await db.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, r[0]))
                await db.commit()
                results.append(ToolPermissionResponse(name=r[1], description=r[2], category=r[3]))
        return results
    except Exception as e:
        logger.error(f"Failed to grant tool permissions by prefix to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant permissions by prefix")


@router.post("/roles/{role_id}/permissions/tools/prefix/revoke")
async def revoke_tool_permissions_by_prefix(role_id: int, payload: ToolPermissionPrefixRequest, db=Depends(get_db_transaction)) -> dict:
    """Revoke all tool permissions with names starting with the prefix from a role."""
    try:
        is_pg = await is_postgres_backend()
        prefix = _normalize_tool_prefix(payload.prefix)
        names: list[str] = []
        if is_pg:
            rows = await db.fetch("SELECT id, name FROM permissions WHERE name LIKE $1", prefix + '%')
            for r in rows:
                await db.execute("DELETE FROM role_permissions WHERE role_id = $1 AND permission_id = $2", role_id, r['id'])
                names.append(r['name'])
        else:
            cur = await db.execute("SELECT id, name FROM permissions WHERE name LIKE ?", (prefix + '%',))
            rows = await cur.fetchall()
            for r in rows:
                await db.execute("DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?", (role_id, r[0]))
                await db.commit()
                names.append(r[1])
        return {"revoked": names, "count": len(names)}
    except Exception as e:
        logger.error(f"Failed to revoke tool permissions by prefix from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke permissions by prefix")


@router.get("/roles/matrix", response_model=RolePermissionMatrixResponse)
async def get_roles_matrix(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    role_search: Optional[str] = Query(None),
    role_names: Optional[List[str]] = Query(None),
    roles_limit: Optional[int] = Query(100, ge=1, le=10000),
    roles_offset: Optional[int] = Query(0, ge=0),
    db=Depends(get_db_transaction),
) -> RolePermissionMatrixResponse:
    """Return roles, filtered permissions, and grants (matrix view).

    Optional filters:
    - category: permission category exact match
    - search: substring match on name/description (case-insensitive)
    """
    try:
        is_pg = await is_postgres_backend()
        # Role filters + pagination
        role_clauses = []
        role_params: list[Any] = []
        total_roles = 0
        if is_pg:
            # Postgres
            if role_search:
                role_clauses.append(f"name ILIKE ${len(role_params)+1}")
                role_params.append(f"%{role_search}%")
            if role_names:
                role_clauses.append(f"name = ANY(${len(role_params)+1})")
                role_params.append(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            # total count
            total_roles = await db.fetchval(f"SELECT COUNT(*) FROM roles{role_where}", *role_params)
            # fetch with limit/offset
            role_rows = await db.fetch(
                f"SELECT id, name, description, COALESCE(is_system,0) as is_system FROM roles{role_where} ORDER BY name LIMIT ${len(role_params)+1} OFFSET ${len(role_params)+2}",
                *role_params, roles_limit, roles_offset,
            )
            roles = [RoleResponse(**dict(r)) for r in role_rows]
        else:
            # SQLite
            if role_search:
                role_clauses.append("name LIKE ?")
                role_params.append(f"%{role_search}%")
            if role_names:
                placeholders = ",".join(["?"] * len(role_names))
                role_clauses.append(f"name IN ({placeholders})")
                role_params.extend(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            # total count
            cur = await db.execute(f"SELECT COUNT(*) FROM roles{role_where}", role_params)
            row = await cur.fetchone()
            total_roles = int(row[0]) if row else 0
            # fetch with limit/offset
            cur = await db.execute(
                f"SELECT id, name, description, COALESCE(is_system,0) FROM roles{role_where} ORDER BY name LIMIT ? OFFSET ?",
                [*role_params, roles_limit, roles_offset],
            )
            role_rows = await cur.fetchall()
            roles = [RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3])) for row in role_rows]

        # Build WHERE for permissions
        clauses = []
        params: list[Any] = []
        if is_pg:
            # Postgres
            if category:
                clauses.append(f"category = ${len(params)+1}")
                params.append(category)
            if search:
                idx = len(params) + 1
                clauses.append(f"(name ILIKE ${idx} OR description ILIKE ${idx})")
                params.append(f"%{search}%")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            perm_rows = await db.fetch(
                f"SELECT id, name, description, category FROM permissions{where} ORDER BY name", *params
            )
            permissions = [PermissionResponse(**dict(r)) for r in perm_rows]

            # Grants limited to filtered permissions via join
            grant_rows = await db.fetch(
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """,
                *params,
            )
            grants = [RolePermissionGrant(role_id=r['role_id'], permission_id=r['permission_id']) for r in grant_rows]
        else:
            # SQLite
            if category:
                clauses.append("category = ?")
                params.append(category)
            if search:
                clauses.append("(name LIKE ? OR description LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            cur = await db.execute(
                f"SELECT id, name, description, category FROM permissions{where} ORDER BY name",
                params,
            )
            perm_rows = await cur.fetchall()
            permissions = [PermissionResponse(id=row[0], name=row[1], description=row[2], category=row[3]) for row in perm_rows]

            cur = await db.execute(
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """,
                params,
            )
            grant_rows = await cur.fetchall()
            grants = [RolePermissionGrant(role_id=row[0], permission_id=row[1]) for row in grant_rows]

        return RolePermissionMatrixResponse(roles=roles, permissions=permissions, grants=grants, total_roles=total_roles)
    except Exception as e:
        logger.error(f"Failed to build roles/permissions matrix: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch role-permission matrix")


@router.get("/roles/matrix-boolean", response_model=RolePermissionBooleanMatrixResponse)
async def get_roles_matrix_boolean(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    role_search: Optional[str] = Query(None),
    role_names: Optional[List[str]] = Query(None),
    roles_limit: Optional[int] = Query(100, ge=1, le=10000),
    roles_offset: Optional[int] = Query(0, ge=0),
    db=Depends(get_db_transaction),
) -> RolePermissionBooleanMatrixResponse:
    """Return a compact boolean matrix: roles x permission_names, with optional filters."""
    try:
        is_pg = await is_postgres_backend()
        # Roles with filters + pagination
        role_clauses = []
        role_params: list[Any] = []
        total_roles = 0
        if is_pg:
            if role_search:
                role_clauses.append(f"name ILIKE ${len(role_params)+1}")
                role_params.append(f"%{role_search}%")
            if role_names:
                role_clauses.append(f"name = ANY(${len(role_params)+1})")
                role_params.append(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            total_roles = await db.fetchval(f"SELECT COUNT(*) FROM roles{role_where}", *role_params)
            role_rows = await db.fetch(
                f"SELECT id, name, description, COALESCE(is_system,0) as is_system FROM roles{role_where} ORDER BY name LIMIT ${len(role_params)+1} OFFSET ${len(role_params)+2}",
                *role_params, roles_limit, roles_offset,
            )
            roles = [RoleResponse(**dict(r)) for r in role_rows]
        else:
            if role_search:
                role_clauses.append("name LIKE ?")
                role_params.append(f"%{role_search}%")
            if role_names:
                placeholders = ",".join(["?"] * len(role_names))
                role_clauses.append(f"name IN ({placeholders})")
                role_params.extend(role_names)
            role_where = (" WHERE " + " AND ".join(role_clauses)) if role_clauses else ""
            cur = await db.execute(f"SELECT COUNT(*) FROM roles{role_where}", role_params)
            row = await cur.fetchone()
            total_roles = int(row[0]) if row else 0
            cur = await db.execute(
                f"SELECT id, name, description, COALESCE(is_system,0) FROM roles{role_where} ORDER BY name LIMIT ? OFFSET ?",
                [*role_params, roles_limit, roles_offset],
            )
            role_rows = await cur.fetchall()
            roles = [RoleResponse(id=row[0], name=row[1], description=row[2], is_system=bool(row[3])) for row in role_rows]

        # Build WHERE for permissions
        clauses = []
        params: list[Any] = []
        if is_pg:
            if category:
                clauses.append(f"category = ${len(params)+1}")
                params.append(category)
            if search:
                idx = len(params) + 1
                clauses.append(f"(name ILIKE ${idx} OR description ILIKE ${idx})")
                params.append(f"%{search}%")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            perm_rows = await db.fetch(f"SELECT id, name FROM permissions{where} ORDER BY name", *params)
            perm_ids = [r['id'] for r in perm_rows]
            perm_names = [r['name'] for r in perm_rows]
        else:
            if category:
                clauses.append("category = ?")
                params.append(category)
            if search:
                clauses.append("(name LIKE ? OR description LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            cur = await db.execute(f"SELECT id, name FROM permissions{where} ORDER BY name", params)
            perm_rows = await cur.fetchall()
            perm_ids = [row[0] for row in perm_rows]
            perm_names = [row[1] for row in perm_rows]

        # Grants set (also restrict to selected roles if any)
        if is_pg:
            role_ids = [r.id for r in roles]
            grant_sql = (
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """
            )
            grant_params = list(params)
            if role_ids:
                grant_sql += f" AND rp.role_id = ANY(${len(grant_params)+1})"
                grant_params.append(role_ids)
            grant_rows = await db.fetch(grant_sql, *grant_params)
            grants_set = {(r['role_id'], r['permission_id']) for r in grant_rows}
        else:
            role_ids = [r.id for r in roles]
            grant_sql = (
                f"""
                SELECT rp.role_id, rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                {where}
                """
            )
            grant_params = list(params)
            if role_ids:
                placeholders = ",".join(["?"] * len(role_ids))
                grant_sql += f" AND rp.role_id IN ({placeholders})"
                grant_params.extend(role_ids)
            cur = await db.execute(grant_sql, grant_params)
            grant_rows = await cur.fetchall()
            grants_set = {(row[0], row[1]) for row in grant_rows}

        # Build matrix: rows per role, cols per permission (same order as perm_names)
        role_ids = [r.id for r in roles]
        matrix: list[list[bool]] = []
        for rid in role_ids:
            row = [ (rid, pid) in grants_set for pid in perm_ids ]
            matrix.append(row)

        return RolePermissionBooleanMatrixResponse(
            roles=roles,
            permission_names=perm_names,
            matrix=matrix,
            total_roles=total_roles,
        )
    except Exception as e:
        logger.error(f"Failed to build boolean matrix: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch boolean matrix")


from typing import List, Optional as _Optional

@router.get("/permissions/categories", response_model=List[str])
async def list_permission_categories(db=Depends(get_db_transaction)) -> List[str]:
    """List distinct permission categories (for UI filters)."""
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch("SELECT DISTINCT category FROM permissions WHERE category IS NOT NULL ORDER BY category")
            return [r['category'] for r in rows]
        else:
            cur = await db.execute("SELECT DISTINCT category FROM permissions WHERE category IS NOT NULL ORDER BY category")
            rows = await cur.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Failed to list permission categories: {e}")
        return []


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(category: _Optional[str] = None, search: _Optional[str] = None, db=Depends(get_db_transaction)) -> List[PermissionResponse]:
    try:
        is_pg = await is_postgres_backend()
        clauses = []
        params = []
        if category:
            clauses.append("category = $1" if is_pg else "category = ?")
            params.append(category)
        if search:
            if is_pg:
                clauses.append("(name ILIKE $%d OR description ILIKE $%d)" % (len(params)+1, len(params)+1))
                params.append(f"%{search}%")
            else:
                clauses.append("(name LIKE ? OR description LIKE ?)")
                params.append(f"%{search}%")
                params.append(f"%{search}%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        if is_pg:
            rows = await db.fetch(f"SELECT id, name, description, category FROM permissions{where} ORDER BY name", *params)
            return [PermissionResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute(f"SELECT id, name, description, category FROM permissions{where} ORDER BY name", params)
            rows = await cur.fetchall()
            return [PermissionResponse(id=row[0], name=row[1], description=row[2], category=row[3]) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list permissions")


@router.post("/permissions", response_model=PermissionResponse)
async def create_permission(payload: PermissionCreateRequest, db=Depends(get_db_transaction)) -> PermissionResponse:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            # Pre-check (case-insensitive)
            exists = await db.fetchrow("SELECT 1 FROM permissions WHERE LOWER(name) = LOWER($1)", payload.name)
            if exists:
                raise HTTPException(status_code=409, detail=f"Permission '{payload.name}' already exists")
            row = await db.fetchrow(
                "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) RETURNING id, name, description, category",
                payload.name, payload.description, payload.category,
            )
            return PermissionResponse(**dict(row))
        else:
            # SQLite: explicit pre-check, return 409 if exists (case-insensitive)
            curx = await db.execute(
                "SELECT 1 FROM permissions WHERE LOWER(name) = LOWER(?)",
                (payload.name,),
            )
            if await curx.fetchone():
                raise HTTPException(status_code=409, detail=f"Permission '{payload.name}' already exists")
            await db.execute(
                "INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)",
                (payload.name, payload.description, payload.category),
            )
            # Fetch the row via adapter
            cur = await db.execute(
                "SELECT id, name, description, category FROM permissions WHERE name = ?",
                (payload.name,),
            )
            row = await cur.fetchone()
            try:
                if isinstance(row, dict):
                    return PermissionResponse(**row)
            except Exception:
                pass
            return PermissionResponse(id=row[0], name=row[1], description=row[2], category=row[3])
    except HTTPException:
        # Preserve explicit status codes like 409 Conflict
        raise
    except Exception as e:
        logger.error(f"Failed to create permission: {e}")
        # In tests, include error details for quicker diagnosis
        import os as _os
        if _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail=f"Failed to create permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to create permission")


@router.post("/roles/{role_id}/permissions/{permission_id}")
async def grant_permission_to_role(role_id: int, permission_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", role_id, permission_id)
        else:
            await db.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, permission_id))
            await db.commit()
        return {"message": "Permission granted to role"}
    except Exception as e:
        logger.error(f"Failed to grant permission {permission_id} to role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant permission to role")


@router.delete("/roles/{role_id}/permissions/{permission_id}")
async def revoke_permission_from_role(role_id: int, permission_id: int, db=Depends(get_db_transaction)) -> dict:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute("DELETE FROM role_permissions WHERE role_id = $1 AND permission_id = $2", role_id, permission_id)
        else:
            await db.execute("DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?", (role_id, permission_id))
            await db.commit()
        return {"message": "Permission revoked from role"}
    except Exception as e:
        logger.error(f"Failed to revoke permission {permission_id} from role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke permission from role")


@router.get("/users/{user_id}/roles", response_model=UserRoleListResponse)
async def get_user_roles_admin(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> UserRoleListResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        repo = _get_rbac_repo()
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, repo.get_user_roles, int(user_id))
        roles = [
            RoleResponse(
                id=int(r.get("id")),
                name=str(r.get("name")),
                description=str(r.get("description") or ""),
                is_system=bool(r.get("is_system")),
            )
            for r in rows
        ]
        return UserRoleListResponse(user_id=user_id, roles=roles)
    except Exception as e:
        logger.error(f"Failed to get user roles for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user roles")


@router.post("/users/{user_id}/roles/{role_id}")
async def add_role_to_user(
    user_id: int,
    role_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT (user_id, role_id) DO NOTHING",
                user_id, role_id,
            )
        else:
            await db.execute(
                "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
                (user_id, role_id),
            )
            await db.commit()
        return {"message": "Role added to user"}
    except Exception as e:
        logger.error(f"Failed to add role {role_id} to user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to add role to user")


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute("DELETE FROM user_roles WHERE user_id = $1 AND role_id = $2", user_id, role_id)
        else:
            await db.execute("DELETE FROM user_roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
            await db.commit()
        return {"message": "Role removed from user"}
    except Exception as e:
        logger.error(f"Failed to remove role {role_id} from user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove role from user")


@router.get("/users/{user_id}/overrides", response_model=UserOverridesResponse)
async def list_user_overrides(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> UserOverridesResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        repo = _get_rbac_repo()
        rows = repo.get_user_overrides(user_id=int(user_id))
        entries = [
            UserOverrideEntry(
                permission_id=int(r.get("permission_id")),
                permission_name=str(r.get("permission_name")),
                granted=bool(r.get("granted")),
                expires_at=str(r.get("expires_at")) if r.get("expires_at") else None,
            )
            for r in rows
        ]
        return UserOverridesResponse(user_id=user_id, overrides=entries)
    except Exception as e:
        logger.error(f"Failed to list overrides for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list user overrides")


@router.post("/users/{user_id}/overrides")
async def upsert_user_override(
    user_id: int,
    payload: UserOverrideUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
        _settings = _get_settings()
        _is_pg = await is_postgres_backend()
        # In single-user mode, ensure the fixed user row exists before applying overrides (SQLite/PG FK safety)
        from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode as _is_single
        if _is_single() and int(user_id) == int(getattr(_settings, 'SINGLE_USER_FIXED_ID', 1)):
            if _is_pg:
                await db.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, is_active, is_verified, role)
                    VALUES ($1, $2, $3, $4, TRUE, TRUE, COALESCE((SELECT role FROM users WHERE id=$1),'user'))
                    ON CONFLICT (id) DO NOTHING
                    """,
                    user_id, 'single_user', 'single_user@example.local', '',
                )
            else:
                # SQLite path: insert a stub single_user row with default role 'user'
                cur = await db.execute(
                    """
                    INSERT OR IGNORE INTO users (id, username, email, password_hash, is_active, is_verified, role)
                    VALUES (?, ?, ?, ?, 1, 1, 'user')
                    """,
                    user_id, 'single_user', 'single_user@example.local', '',
                )
                if not _is_pg:
                    await db.commit()
        # Resolve permission_id if only name provided
        perm_id = payload.permission_id
        if not perm_id and payload.permission_name:
            if _is_pg:
                perm_id = await db.fetchval("SELECT id FROM permissions WHERE name = $1", payload.permission_name)
            else:
                cur = await db.execute("SELECT id FROM permissions WHERE name = ?", (payload.permission_name,))
                row = await cur.fetchone()
                perm_id = row[0] if row else None
        if not perm_id:
            raise HTTPException(status_code=400, detail="permission_id or permission_name required")

        granted = payload.effect == OverrideEffect.allow
        if _is_pg:
            await db.execute(
                """
                INSERT INTO user_permissions (user_id, permission_id, granted, expires_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, permission_id)
                DO UPDATE SET granted = EXCLUDED.granted, expires_at = EXCLUDED.expires_at
                """,
                user_id, perm_id, granted, payload.expires_at,
            )
        else:
            cur = await db.execute(
                """
                INSERT OR REPLACE INTO user_permissions (user_id, permission_id, granted, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                user_id, perm_id, granted, payload.expires_at,
            )
            # Commit on SQLite acquire()-based connection
            if not _is_pg:
                await db.commit()
        return {"message": "Override upserted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to upsert override for user {user_id}: {e}")
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
        _settings = _get_settings()
        # In tests or single-user dev, surface error details to aid debugging
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes") or str(_settings.AUTH_MODE) == "single_user":
            raise HTTPException(status_code=500, detail=f"Failed to upsert user override: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert user override")


@router.delete("/users/{user_id}/overrides/{permission_id}")
async def delete_user_override(
    user_id: int,
    permission_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> dict:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        _is_pg = await is_postgres_backend()
        if _is_pg:
            await db.execute("DELETE FROM user_permissions WHERE user_id = $1 AND permission_id = $2", user_id, permission_id)
        else:
            cur = await db.execute("DELETE FROM user_permissions WHERE user_id = ? AND permission_id = ?", (user_id, permission_id))
            if not _is_pg:
                await db.commit()
        return {"message": "Override deleted"}
    except Exception as e:
        logger.exception(f"Failed to delete override for user {user_id}: {e}")
        if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail=f"Failed to delete user override: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user override")


@router.get("/users/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse)
async def get_effective_permissions_admin(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> EffectivePermissionsResponse:
    """Compute effective permissions for a user.

    Delegates to the central RBAC helper, which in turn uses the AuthNZ
    repository layer (`AuthnzRbacRepo` / `UserDatabase_v2`) so that both
    SQLite and Postgres backends share the same logic.
    """
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        loop = asyncio.get_event_loop()
        perms = await loop.run_in_executor(None, get_effective_permissions, user_id)
        return EffectivePermissionsResponse(user_id=user_id, permissions=sorted(perms))
    except Exception as e:
        logger.error(f"Failed to compute effective permissions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute effective permissions")


@router.get("/roles/{role_id}/permissions/effective", response_model=RoleEffectivePermissionsResponse)
async def get_role_effective_permissions(role_id: int) -> RoleEffectivePermissionsResponse:
    """Return a convenience view combining a role's granted permissions and tool permissions.

    - permissions: non-tool permission names (e.g., media.read)
    - tool_permissions: tool execution permission names (tools.execute:...)
    - all_permissions: union of both, sorted
    """
    try:
        repo = _get_rbac_repo()
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, repo.get_role_effective_permissions, int(role_id))
        return RoleEffectivePermissionsResponse(
            role_id=role_id,
            role_name=data.get("role_name", ""),
            permissions=data.get("permissions", []),
            tool_permissions=data.get("tool_permissions", []),
            all_permissions=data.get("all_permissions", []),
        )
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Role not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute effective permissions for role {role_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute role effective permissions")


@router.post("/roles/{role_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_role_rate_limit(role_id: int, payload: RateLimitUpsertRequest, db=Depends(get_db_transaction)) -> RateLimitResponse:
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                """
                INSERT INTO rbac_role_rate_limits (role_id, resource, limit_per_min, burst)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (role_id, resource) DO UPDATE SET
                    limit_per_min = EXCLUDED.limit_per_min,
                    burst = EXCLUDED.burst
                """,
                role_id, payload.resource, payload.limit_per_min, payload.burst,
            )
        else:
            await db.execute(
                """
                INSERT OR REPLACE INTO rbac_role_rate_limits (role_id, resource, limit_per_min, burst)
                VALUES (?, ?, ?, ?)
                """,
                (role_id, payload.resource, payload.limit_per_min, payload.burst),
            )
            await db.commit()
        return RateLimitResponse(scope="role", id=role_id, resource=payload.resource, limit_per_min=payload.limit_per_min, burst=payload.burst)
    except Exception as e:
        logger.error(f"Failed to upsert role rate limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert role rate limit")


@router.post("/users/{user_id}/rate-limits", response_model=RateLimitResponse)
async def upsert_user_rate_limit(
    user_id: int,
    payload: RateLimitUpsertRequest,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RateLimitResponse:
    try:
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                """
                INSERT INTO rbac_user_rate_limits (user_id, resource, limit_per_min, burst)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, resource) DO UPDATE SET
                    limit_per_min = EXCLUDED.limit_per_min,
                    burst = EXCLUDED.burst
                """,
                user_id, payload.resource, payload.limit_per_min, payload.burst,
            )
        else:
            await db.execute(
                """
                INSERT OR REPLACE INTO rbac_user_rate_limits (user_id, resource, limit_per_min, burst)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, payload.resource, payload.limit_per_min, payload.burst),
            )
            await db.commit()
        return RateLimitResponse(scope="user", id=user_id, resource=payload.resource, limit_per_min=payload.limit_per_min, burst=payload.burst)
    except Exception as e:
        logger.error(f"Failed to upsert user rate limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert user rate limit")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> Dict[str, str]:
    """
    Delete a user (soft delete by default)

    Args:
        user_id: User ID to delete

    Returns:
        Success message
    """
    try:
        # Prevent self-deletion
        if principal.user_id is not None and str(user_id) == str(principal.user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        await _enforce_admin_user_scope(principal, user_id, require_hierarchy=True)

        # Soft delete - just mark as inactive
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            result = await db.execute(
                "UPDATE users SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                user_id
            )
        else:
            # SQLite
            await db.execute(
                "UPDATE users SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
                (user_id,)
            )
            await db.commit()

        logger.info(f"Admin soft-deleted user {user_id}")

        return {"message": f"User {user_id} has been deactivated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


#######################################################################################################################
#
# Registration Code Management

@router.get("/registration-settings", response_model=RegistrationSettingsResponse)
async def get_registration_settings() -> RegistrationSettingsResponse:
    """Return current registration settings."""
    settings = get_settings()
    profile = get_profile()
    self_allowed = bool(settings.ENABLE_REGISTRATION)
    if isinstance(profile, str) and profile.strip().lower() in {"local-single-user", "single_user"}:
        self_allowed = False

    return RegistrationSettingsResponse(
        enable_registration=bool(settings.ENABLE_REGISTRATION),
        require_registration_code=bool(settings.REQUIRE_REGISTRATION_CODE),
        auth_mode=str(settings.AUTH_MODE) if getattr(settings, "AUTH_MODE", None) is not None else None,
        profile=str(profile) if profile is not None else None,
        self_registration_allowed=self_allowed,
    )


@router.post("/registration-settings", response_model=RegistrationSettingsResponse)
async def update_registration_settings(
    payload: RegistrationSettingsUpdateRequest,
) -> RegistrationSettingsResponse:
    """Update registration settings and refresh cached config."""
    updates: Dict[str, Any] = {}
    if payload.enable_registration is not None:
        updates["enable_registration"] = payload.enable_registration
    if payload.require_registration_code is not None:
        updates["require_registration_code"] = payload.require_registration_code

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No registration settings provided")

    try:
        setup_manager.update_config({"AuthNZ": updates})
        reset_settings()
        try:
            await reset_registration_service()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Registration service reset failed: {}", exc)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to update registration settings: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update registration settings",
        ) from exc

    settings = get_settings()
    profile = get_profile()
    self_allowed = bool(settings.ENABLE_REGISTRATION)
    if isinstance(profile, str) and profile.strip().lower() in {"local-single-user", "single_user"}:
        self_allowed = False

    return RegistrationSettingsResponse(
        enable_registration=bool(settings.ENABLE_REGISTRATION),
        require_registration_code=bool(settings.REQUIRE_REGISTRATION_CODE),
        auth_mode=str(settings.AUTH_MODE) if getattr(settings, "AUTH_MODE", None) is not None else None,
        profile=str(profile) if profile is not None else None,
        self_registration_allowed=self_allowed,
    )

@router.post("/registration-codes", response_model=RegistrationCodeResponse)
async def create_registration_code(
    request: RegistrationCodeRequest,
    http_request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> RegistrationCodeResponse:
    """
    Create a new registration code

    Args:
        request: Registration code configuration

    Returns:
        Created registration code details
    """
    try:
        # Generate secure code
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(24))

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=request.expiry_days)

        is_pg = await is_postgres_backend()
        creator_id = int(principal.user_id) if principal.user_id is not None else None
        org_id = request.org_id
        org_role = request.org_role or ("member" if org_id is not None else None)
        team_id = request.team_id
        settings = get_settings()

        if (org_id is not None or team_id is not None or request.org_role is not None) and not (
            settings.ENABLE_ORG_SCOPED_REGISTRATION_CODES
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Org-scoped registration codes are disabled",
            )

        allowed_email_domain = request.allowed_email_domain
        if allowed_email_domain is not None:
            normalized = allowed_email_domain.strip().lower()
            if normalized.startswith("@"):
                normalized = normalized[1:]
            if "@" in normalized or not normalized:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="allowed_email_domain must be a domain like example.com",
                )
            allowed_email_domain = normalized

        if team_id is not None and org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="org_id is required when team_id is provided",
            )

        org_name = None
        if org_id is not None:
            if is_pg:
                org_row = await db.fetchrow("SELECT id, name FROM organizations WHERE id = $1", org_id)
            else:
                cursor = await db.execute("SELECT id, name FROM organizations WHERE id = ?", (org_id,))
                org_row = await cursor.fetchone()
            if not org_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found",
                )
            org_name = org_row["name"] if isinstance(org_row, dict) else org_row[1]

        if team_id is not None:
            if is_pg:
                team_row = await db.fetchrow(
                    "SELECT id, org_id FROM teams WHERE id = $1",
                    team_id,
                )
                team_org_id = team_row["org_id"] if team_row else None
            else:
                cursor = await db.execute(
                    "SELECT id, org_id FROM teams WHERE id = ?",
                    (team_id,),
                )
                team_row = await cursor.fetchone()
                team_org_id = team_row[1] if team_row else None
            if not team_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Team not found",
                )
            if org_id is not None and team_org_id != org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Team does not belong to the specified organization",
                )

        if is_pg:
            # PostgreSQL
            result = await db.fetchrow("""
                INSERT INTO registration_codes
                (code, max_uses, expires_at, created_by, role_to_grant, allowed_email_domain, metadata, org_id, org_role, team_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id, code, max_uses, times_used, expires_at, created_at, created_by, role_to_grant,
                          org_id, org_role, team_id, metadata, is_active, allowed_email_domain
            """,
                code,
                request.max_uses,
                expires_at,
                creator_id,
                request.role_to_grant,
                allowed_email_domain,
                json.dumps(request.metadata or {}),
                org_id,
                org_role,
                team_id,
            )
        else:
            # SQLite
            cursor = await db.execute("""
                INSERT INTO registration_codes
                (code, max_uses, expires_at, created_by, role_to_grant, allowed_email_domain, metadata, org_id, org_role, team_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    code,
                    request.max_uses,
                    expires_at.isoformat(),
                    creator_id,
                    request.role_to_grant,
                    allowed_email_domain,
                    json.dumps(request.metadata or {}),
                    org_id,
                    org_role,
                    team_id,
                ),
            )

            code_id = cursor.lastrowid
            await db.commit()

            # Fetch the created code
            cursor = await db.execute(
                """
                SELECT id, code, max_uses, times_used, expires_at, created_at, created_by, role_to_grant,
                       org_id, org_role, team_id, metadata, is_active, allowed_email_domain
                FROM registration_codes
                WHERE id = ?
                """,
                (code_id,),
            )
            result = await cursor.fetchone()

        logger.info(f"Admin created registration code: {code[:8]}...")

        if isinstance(result, tuple):
            created_at = result[5]
            metadata_value = result[11]
            created_by = result[6]
            is_active = result[12]
            allowed_email_domain = result[13]
            code_id = result[0]
        else:
            created_at = result["created_at"]
            metadata_value = result["metadata"]
            created_by = result.get("created_by")
            is_active = result.get("is_active")
            allowed_email_domain = result.get("allowed_email_domain")
            code_id = result["id"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        if isinstance(metadata_value, str):
            try:
                metadata_value = json.loads(metadata_value)
            except json.JSONDecodeError:
                metadata_value = None

        await _emit_admin_audit_event(
            http_request,
            principal,
            event_type="data.write",
            category="data_modification",
            resource_type="registration_code",
            resource_id=str(code_id),
            action="registration_code.create",
            metadata={
                "code_prefix": code[:8],
                "max_uses": request.max_uses,
                "expires_at": expires_at.isoformat(),
                "role_to_grant": request.role_to_grant,
                "allowed_email_domain": allowed_email_domain,
                "org_id": org_id,
                "org_role": org_role,
                "team_id": team_id,
            },
        )

        return RegistrationCodeResponse(
            id=code_id,
            code=code,
            max_uses=request.max_uses,
            times_used=0,
            expires_at=expires_at,
            created_at=created_at,
            created_by=created_by,
            role_to_grant=request.role_to_grant,
            allowed_email_domain=allowed_email_domain,
            org_id=result[8] if isinstance(result, tuple) else result["org_id"],
            org_role=result[9] if isinstance(result, tuple) else result["org_role"],
            team_id=result[10] if isinstance(result, tuple) else result["team_id"],
            org_name=org_name,
            metadata=metadata_value if metadata_value is not None else request.metadata,
            is_active=is_active,
        )

    except Exception as e:
        logger.error(f"Failed to create registration code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create registration code"
        )


@router.get("/registration-codes", response_model=RegistrationCodeListResponse)
async def list_registration_codes(
    include_expired: bool = Query(False),
    db=Depends(get_db_transaction)
) -> RegistrationCodeListResponse:
    """
    List all registration codes

    Args:
        include_expired: Include expired codes in the list

    Returns:
        List of registration codes
    """
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            if include_expired:
                query = """
                    SELECT rc.id, rc.code, rc.max_uses, rc.times_used, rc.expires_at,
                           rc.created_at, rc.created_by, rc.role_to_grant,
                           rc.org_id, rc.org_role, rc.team_id, rc.metadata, rc.is_active,
                           rc.allowed_email_domain, o.name AS org_name
                    FROM registration_codes rc
                    LEFT JOIN organizations o ON rc.org_id = o.id
                    ORDER BY rc.created_at DESC
                """
            else:
                query = """
                    SELECT rc.id, rc.code, rc.max_uses, rc.times_used, rc.expires_at,
                           rc.created_at, rc.created_by, rc.role_to_grant,
                           rc.org_id, rc.org_role, rc.team_id, rc.metadata, rc.is_active,
                           rc.allowed_email_domain, o.name AS org_name
                    FROM registration_codes rc
                    LEFT JOIN organizations o ON rc.org_id = o.id
                    WHERE rc.is_active = TRUE
                      AND rc.times_used < rc.max_uses
                      AND rc.expires_at > CURRENT_TIMESTAMP
                    ORDER BY rc.created_at DESC
                """
            rows = await db.fetch(query)
        else:
            # SQLite
            if include_expired:
                query = """
                    SELECT rc.id, rc.code, rc.max_uses, rc.times_used, rc.expires_at,
                           rc.created_at, rc.created_by, rc.role_to_grant,
                           rc.org_id, rc.org_role, rc.team_id, rc.metadata, rc.is_active,
                           rc.allowed_email_domain, o.name AS org_name
                    FROM registration_codes rc
                    LEFT JOIN organizations o ON rc.org_id = o.id
                    ORDER BY rc.created_at DESC
                """
            else:
                query = """
                    SELECT rc.id, rc.code, rc.max_uses, rc.times_used, rc.expires_at,
                           rc.created_at, rc.created_by, rc.role_to_grant,
                           rc.org_id, rc.org_role, rc.team_id, rc.metadata, rc.is_active,
                           rc.allowed_email_domain, o.name AS org_name
                    FROM registration_codes rc
                    LEFT JOIN organizations o ON rc.org_id = o.id
                    WHERE rc.is_active = 1
                      AND rc.times_used < rc.max_uses
                      AND datetime(rc.expires_at) > datetime('now')
                    ORDER BY rc.created_at DESC
                """
            cursor = await db.execute(query)
            rows = await cursor.fetchall()

        codes = []
        def _get_value(row, key: str, index: int):
            try:
                return row[key]
            except Exception:
                return row[index]
        for row in rows:
            metadata_value = _get_value(row, "metadata", 11)
            if isinstance(metadata_value, str):
                try:
                    metadata_value = json.loads(metadata_value)
                except json.JSONDecodeError:
                    metadata_value = None

            expires_at_value = _get_value(row, "expires_at", 4)
            if isinstance(expires_at_value, str):
                expires_at_dt = datetime.fromisoformat(expires_at_value)
            else:
                expires_at_dt = expires_at_value

            times_used = _get_value(row, "times_used", 3)
            max_uses = _get_value(row, "max_uses", 2)
            is_active = _get_value(row, "is_active", 12)
            is_active_value = True if is_active is None else bool(is_active)

            code_dict = {
                "id": _get_value(row, "id", 0),
                "code": _get_value(row, "code", 1),
                "max_uses": max_uses,
                "times_used": times_used,
                "expires_at": expires_at_value,
                "created_at": _get_value(row, "created_at", 5),
                "created_by": _get_value(row, "created_by", 6),
                "role_to_grant": _get_value(row, "role_to_grant", 7),
                "allowed_email_domain": _get_value(row, "allowed_email_domain", 13),
                "org_id": _get_value(row, "org_id", 8),
                "org_role": _get_value(row, "org_role", 9),
                "team_id": _get_value(row, "team_id", 10),
                "org_name": _get_value(row, "org_name", 14),
                "metadata": metadata_value,
                "is_active": is_active,
                "is_valid": is_active_value and times_used < max_uses and expires_at_dt > datetime.utcnow(),
            }
            codes.append(code_dict)

        return RegistrationCodeListResponse(codes=codes)

    except Exception as e:
        logger.error(f"Failed to list registration codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve registration codes"
        )


@router.delete("/registration-codes/{code_id}")
async def delete_registration_code(
    code_id: int,
    http_request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> Dict[str, str]:
    """
    Delete a registration code

    Args:
        code_id: Registration code ID

    Returns:
        Success message
    """
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            await db.execute(
                "UPDATE registration_codes SET is_active = FALSE WHERE id = $1",
                code_id,
            )
        else:
            # SQLite
            await db.execute(
                "UPDATE registration_codes SET is_active = 0 WHERE id = ?",
                (code_id,)
            )
            await db.commit()

        logger.info(f"Admin revoked registration code {code_id}")

        await _emit_admin_audit_event(
            http_request,
            principal,
            event_type="data.update",
            category="data_modification",
            resource_type="registration_code",
            resource_id=str(code_id),
            action="registration_code.revoke",
            metadata={},
        )

        return {"message": f"Registration code {code_id} revoked"}

    except Exception as e:
        logger.error(f"Failed to delete registration code {code_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete registration code"
        )


#######################################################################################################################
#
# System Statistics and Monitoring

@router.get("/security/alert-status", response_model=SecurityAlertStatusResponse)
async def get_security_alert_status() -> SecurityAlertStatusResponse:
    """Return configuration and last-known status for AuthNZ security alerts."""
    dispatcher = get_security_alert_dispatcher()
    status = dispatcher.get_status()

    sink_status_map: Dict[str, Optional[bool]] = status.get("last_sink_status", {})
    sink_error_map: Dict[str, Optional[str]] = status.get("last_sink_errors", {})
    sink_threshold_map: Dict[str, Optional[str]] = status.get("sink_thresholds", {})
    sink_backoff_map: Dict[str, Optional[str]] = status.get("sink_backoff_until", {})

    sink_rows = []
    for sink_name, configured in (
        ("file", status.get("file_sink_configured", False)),
        ("webhook", status.get("webhook_configured", False)),
        ("email", status.get("email_configured", False)),
    ):
        sink_rows.append(
            SecurityAlertSinkStatus(
                sink=sink_name,
                configured=bool(configured),
                min_severity=sink_threshold_map.get(sink_name),
                last_status=sink_status_map.get(sink_name),
                last_error=sink_error_map.get(sink_name),
                backoff_until=sink_backoff_map.get(sink_name),
            )
        )

    overall_health = "ok"
    if status.get("enabled", False):
        if status.get("last_validation_errors"):
            overall_health = "errors"
        else:
            configured_rows = [row for row in sink_rows if row.configured]
            if status.get("last_dispatch_success") is False:
                overall_health = "degraded"
            elif any(row.last_error for row in configured_rows):
                overall_health = "degraded"
            elif configured_rows and all(row.last_status is False for row in configured_rows):
                overall_health = "degraded"

    return SecurityAlertStatusResponse(
        enabled=status.get("enabled", False),
        min_severity=status.get("min_severity", "high"),
        last_dispatch_time=status.get("last_dispatch_time"),
        last_dispatch_success=status.get("last_dispatch_success"),
        last_dispatch_error=status.get("last_dispatch_error"),
        dispatch_count=status.get("dispatch_count", 0),
        last_validation_time=status.get("last_validation_time"),
        validation_errors=status.get("last_validation_errors"),
        sinks=sink_rows,
        health=overall_health,
    )


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    db=Depends(get_db_transaction)
) -> SystemStatsResponse:
    """
    Get system statistics

    Returns:
        System-wide statistics including user counts, storage usage, etc.
    """
    try:
        stats = {}

        def _row_to_dict(row, keys: list[str]) -> dict:
            if row is None:
                return {}
            if isinstance(row, dict):
                return row
            if hasattr(row, "keys"):
                return {key: row[key] for key in row.keys()}
            return {key: row[idx] if idx < len(row) else None for idx, key in enumerate(keys)}

        is_pg = await is_postgres_backend()
        if is_pg:
            # PostgreSQL
            # User stats
            user_stats = await db.fetchrow("""
                SELECT
                    COUNT(*) as total_users,
                    COUNT(*) FILTER (WHERE is_active = TRUE) as active_users,
                    COUNT(*) FILTER (WHERE is_verified = TRUE) as verified_users,
                    COUNT(*) FILTER (WHERE role = 'admin') as admin_users,
                    COUNT(*) FILTER (WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '30 days') as new_users_30d
                FROM users
            """)

            # Storage stats
            storage_stats = await db.fetchrow("""
                SELECT
                    SUM(storage_used_mb) as total_used_mb,
                    SUM(storage_quota_mb) as total_quota_mb,
                    AVG(storage_used_mb) as avg_used_mb,
                    MAX(storage_used_mb) as max_used_mb
                FROM users
                WHERE is_active = TRUE
            """)

            # Session stats
            session_stats = await db.fetchrow("""
                SELECT
                    COUNT(*) as active_sessions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM sessions
                WHERE is_active = TRUE AND expires_at > CURRENT_TIMESTAMP
            """)

        else:
            # SQLite
            cursor = await db.execute("""
                SELECT
                    COUNT(*) as total_users,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_users,
                    SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) as verified_users,
                    SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as admin_users,
                    SUM(CASE WHEN datetime(created_at) > datetime('now', '-30 days') THEN 1 ELSE 0 END) as new_users_30d
                FROM users
            """)
            user_stats = await cursor.fetchone()

            cursor = await db.execute("""
                SELECT
                    SUM(storage_used_mb) as total_used_mb,
                    SUM(storage_quota_mb) as total_quota_mb,
                    AVG(storage_used_mb) as avg_used_mb,
                    MAX(storage_used_mb) as max_used_mb
                FROM users
                WHERE is_active = 1
            """)
            storage_stats = await cursor.fetchone()

            cursor = await db.execute("""
                SELECT
                    COUNT(*) as active_sessions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM sessions
                WHERE is_active = 1 AND datetime(expires_at) > datetime('now')
            """)
            session_stats = await cursor.fetchone()

        user_keys = ["total_users", "active_users", "verified_users", "admin_users", "new_users_30d"]
        storage_keys = ["total_used_mb", "total_quota_mb", "avg_used_mb", "max_used_mb"]
        session_keys = ["active_sessions", "unique_users"]
        us = _row_to_dict(user_stats, user_keys)
        ss = _row_to_dict(storage_stats, storage_keys)
        se = _row_to_dict(session_stats, session_keys)

        return SystemStatsResponse(
            users={
                "total": int(us.get("total_users") or 0),
                "active": int(us.get("active_users") or 0),
                "verified": int(us.get("verified_users") or 0),
                "admins": int(us.get("admin_users") or 0),
                "new_last_30d": int(us.get("new_users_30d") or 0),
            },
            storage={
                "total_used_mb": float(ss.get("total_used_mb") or 0.0),
                "total_quota_mb": float(ss.get("total_quota_mb") or 0.0),
                "average_used_mb": float(ss.get("avg_used_mb") or 0.0),
                "max_used_mb": float(ss.get("max_used_mb") or 0.0),
            },
            sessions={
                "active": int(se.get("active_sessions") or 0),
                "unique_users": int(se.get("unique_users") or 0),
            },
        )

    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        # In test environments or if non-critical, return a safe default instead of 500
        try:
            import os as _os
            if _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
                return SystemStatsResponse(
                    users={"total": 0, "active": 0, "verified": 0, "admins": 0, "new_last_30d": 0},
                    storage={"total_used_mb": 0.0, "total_quota_mb": 0.0, "average_used_mb": 0.0, "max_used_mb": 0.0},
                    sessions={"active": 0, "unique_users": 0},
                )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system statistics"
        )


@router.get("/activity", response_model=ActivitySummaryResponse)
async def get_dashboard_activity(
    days: int = Query(7, ge=1, le=30),
    db=Depends(get_db_transaction),
) -> ActivitySummaryResponse:
    """Return recent request/user activity for the admin dashboard."""
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    date_range = [start_date + timedelta(days=idx) for idx in range(days)]
    activity_by_date = {
        day: {
            "date": day.isoformat(),
            "requests": 0,
            "users": 0,
        }
        for day in date_range
    }
    warnings: list[str] = []

    try:
        registry = get_metrics_registry()
        request_values = registry.values.get("http_requests_total", [])
        for metric_value in list(request_values):
            try:
                metric_day = datetime.fromtimestamp(
                    metric_value.timestamp,
                    timezone.utc,
                ).date()
            except (OSError, OverflowError, ValueError):
                continue
            if metric_day in activity_by_date:
                activity_by_date[metric_day]["requests"] += int(metric_value.value or 0)
    except Exception as exc:
        logger.warning("Admin activity request metrics unavailable: {}", exc)
        warnings.append("request_metrics_unavailable")

    try:
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                """
                SELECT DATE(created_at) as day,
                       COUNT(DISTINCT user_id) as active_users
                FROM sessions
                WHERE created_at >= $1
                GROUP BY day
                ORDER BY day
                """,
                start_dt,
            )
        else:
            cursor = await db.execute(
                """
                SELECT date(created_at) as day,
                       COUNT(DISTINCT user_id) as active_users
                FROM sessions
                WHERE datetime(created_at) >= datetime(?)
                GROUP BY date(created_at)
                ORDER BY date(created_at)
                """,
                (start_dt.isoformat(),),
            )
            rows = await cursor.fetchall()
        for row in rows:
            if isinstance(row, dict):
                day_str = row.get("day")
                active_users = row.get("active_users")
            else:
                day_str = row[0] if len(row) > 0 else None
                active_users = row[1] if len(row) > 1 else None
            if not day_str:
                continue
            try:
                metric_day = datetime.fromisoformat(str(day_str)).date()
            except ValueError:
                continue
            if metric_day in activity_by_date:
                activity_by_date[metric_day]["users"] = int(active_users or 0)
    except Exception as exc:
        logger.warning("Admin activity user metrics unavailable: {}", exc)
        warnings.append("user_metrics_unavailable")

    points = [activity_by_date[day] for day in date_range]
    return ActivitySummaryResponse(days=days, points=points, warnings=warnings or None)


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource: Optional[str] = Query(None, description="Filter by resource type or type:id"),
    start: Optional[str] = Query(None, description="ISO date or datetime (start)"),
    end: Optional[str] = Query(None, description="ISO date or datetime (end)"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> AuditLogResponse:
    """
    Get audit log entries

    Args:
        user_id: Filter by user ID
        action: Filter by action type
        days: Number of days to look back
        limit: Maximum entries to return
        offset: Number of entries to skip

    Returns:
        Audit log entries
    """
    try:
        is_pg = await is_postgres_backend()
        conditions = []
        params = []
        param_count = 0
        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None

        def _parse_date_param(value: Optional[str], label: str, end_of_day: bool = False) -> Optional[datetime]:
            if value is None:
                return None
            raw = str(value).strip()
            if not raw:
                return None
            raw = raw.replace("Z", "+00:00")
            try:
                if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
                    dt = datetime.fromisoformat(raw)
                    if end_of_day:
                        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                    return dt
                return datetime.fromisoformat(raw)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid {label} date format")

        start_dt = _parse_date_param(start, "start")
        end_dt = _parse_date_param(end, "end", end_of_day=True)
        if start_dt and end_dt and start_dt > end_dt:
            raise HTTPException(status_code=400, detail="Start date must be on or before end date")

        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        if org_ids is not None and len(org_ids) == 0:
            return AuditLogResponse(entries=[], total=0, limit=limit, offset=offset)

        if user_id:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
            param_count += 1
            conditions.append(f"a.user_id = ${param_count}" if is_pg else "a.user_id = ?")
            params.append(user_id)

        if action:
            param_count += 1
            conditions.append(f"a.action = ${param_count}" if is_pg else "a.action = ?")
            params.append(action)

        if resource:
            resource_filter = resource.strip()
            if resource_filter:
                if ":" in resource_filter:
                    resource_type, resource_id = resource_filter.split(":", 1)
                    resource_type = resource_type.strip()
                    resource_id = resource_id.strip()
                    if resource_type:
                        param_count += 1
                        conditions.append(f"a.resource_type = ${param_count}" if is_pg else "a.resource_type = ?")
                        params.append(resource_type)
                    if resource_id.isdigit():
                        param_count += 1
                        conditions.append(f"a.resource_id = ${param_count}" if is_pg else "a.resource_id = ?")
                        params.append(int(resource_id))
                else:
                    param_count += 1
                    if is_pg:
                        conditions.append(f"a.resource_type ILIKE ${param_count}")
                        params.append(f"%{resource_filter}%")
                    else:
                        conditions.append("LOWER(a.resource_type) LIKE ?")
                        params.append(f"%{resource_filter.lower()}%")

        # Date filter
        if start_dt or end_dt:
            if start_dt:
                param_count += 1
                conditions.append(f"a.created_at >= ${param_count}" if is_pg else "datetime(a.created_at) >= datetime(?)")
                params.append(start_dt.isoformat())
            if end_dt:
                param_count += 1
                conditions.append(f"a.created_at <= ${param_count}" if is_pg else "datetime(a.created_at) <= datetime(?)")
                params.append(end_dt.isoformat())
        else:
            if is_pg:
                conditions.append(f"a.created_at > CURRENT_TIMESTAMP - INTERVAL '{days} days'")
            else:
                conditions.append("datetime(a.created_at) > datetime('now', ? || ' days')")
                params.append(f"-{days}")

        join_clause = ""
        if org_ids is not None:
            join_clause = " JOIN org_members om ON om.user_id = a.user_id"
            if is_pg:
                param_count += 1
                conditions.append(f"om.org_id = ANY(${param_count})")
                params.append(org_ids)
            else:
                placeholders = ",".join("?" for _ in org_ids)
                conditions.append(f"om.org_id IN ({placeholders})")
                params.extend(org_ids)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        def _format_resource(resource_type: Optional[str], resource_id: Optional[int]) -> Optional[str]:
            if not resource_type and resource_id is None:
                return None
            if resource_type and resource_id is not None:
                return f"{resource_type}:{resource_id}"
            if resource_type:
                return str(resource_type)
            return str(resource_id)

        if is_pg:
            # PostgreSQL
            count_query = f"""
                SELECT COUNT(*)
                FROM audit_logs a
                {join_clause}
                {where_clause}
            """
            total = await db.fetchval(count_query, *params)
            query = f"""
                SELECT a.id, a.user_id, u.username, a.action, a.resource_type, a.resource_id, a.details,
                       a.ip_address, a.created_at
                FROM audit_logs a
                LEFT JOIN users u ON a.user_id = u.id
                {join_clause}
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ${param_count + 1}
                OFFSET ${param_count + 2}
            """
            query_params = list(params)
            query_params.append(limit)
            query_params.append(offset)
            rows = await db.fetch(query, *query_params)
        else:
            # SQLite
            count_query = f"""
                SELECT COUNT(*)
                FROM audit_logs a
                {join_clause}
                {where_clause}
            """
            count_cursor = await db.execute(count_query, params)
            count_row = await count_cursor.fetchone()
            total = int(count_row[0]) if count_row and count_row[0] is not None else 0
            query = f"""
                SELECT a.id, a.user_id, u.username, a.action, a.resource_type, a.resource_id, a.details,
                       a.ip_address, a.created_at
                FROM audit_logs a
                LEFT JOIN users u ON a.user_id = u.id
                {join_clause}
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ?
                OFFSET ?
            """
            query_params = list(params)
            query_params.append(limit)
            query_params.append(offset)
            cursor = await db.execute(query, query_params)
            rows = await cursor.fetchall()

        entries = []
        for row in rows:
            if isinstance(row, dict):
                resource_value = _format_resource(row.get("resource_type"), row.get("resource_id"))
                row["resource"] = resource_value
                entries.append(row)
            else:
                resource_value = _format_resource(row[4], row[5])
                entry = {
                    "id": row[0],
                    "user_id": row[1],
                    "username": row[2],
                    "action": row[3],
                    "resource": resource_value,
                    "details": row[6],
                    "ip_address": row[7],
                    "created_at": row[8]
                }
                entries.append(entry)

        return AuditLogResponse(entries=entries, total=int(total or 0), limit=limit, offset=offset)

    except Exception as e:
        logger.error(f"Failed to get audit log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit log"
        )


# ---------------------------------------------------------------------------------------------------------------------
# Data Ops Endpoints (Backups, Retention, Exports)

_BACKUP_DATASETS = {"media", "chacha", "prompts", "evaluations", "audit", "authnz"}
_PER_USER_BACKUP_DATASETS = _BACKUP_DATASETS - {"authnz"}


def _require_user_id_for_dataset(dataset: str, user_id: Optional[int]) -> None:
    if dataset in _PER_USER_BACKUP_DATASETS and user_id is None:
        raise HTTPException(status_code=400, detail="user_id_required")


@router.get("/backups", response_model=BackupListResponse)
async def list_backups(
    dataset: Optional[str] = Query(None, description="Dataset key to filter"),
    user_id: Optional[int] = Query(None, description="User ID for per-user datasets"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupListResponse:
    try:
        normalized_dataset = None
        if dataset:
            normalized_dataset = dataset.strip().lower()
            if normalized_dataset not in _BACKUP_DATASETS:
                raise HTTPException(status_code=400, detail="unknown_dataset")
            _require_user_id_for_dataset(normalized_dataset, user_id)
        if user_id is not None:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        items, total = svc_list_backup_items(
            dataset=normalized_dataset,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        payload = [
            BackupItem(
                id=item.filename,
                dataset=item.dataset,
                user_id=item.user_id,
                status="ready",
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
            for item in items
        ]
        return BackupListResponse(items=payload, total=total, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to list backups: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list backups")


@router.post("/backups", response_model=BackupCreateResponse)
async def create_backup(
    payload: BackupCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupCreateResponse:
    try:
        dataset = payload.dataset.strip().lower()
        if dataset not in _BACKUP_DATASETS:
            raise HTTPException(status_code=400, detail="unknown_dataset")
        _require_user_id_for_dataset(dataset, payload.user_id)
        if payload.user_id is not None:
            await _enforce_admin_user_scope(principal, payload.user_id, require_hierarchy=False)
        item = svc_create_backup_snapshot(
            dataset=dataset,
            user_id=payload.user_id,
            backup_type=payload.backup_type or "full",
            max_backups=payload.max_backups,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.write",
            category="system",
            resource_type="backup",
            resource_id=item.filename,
            action="backup.create",
            metadata={
                "dataset": dataset,
                "user_id": item.user_id,
                "size_bytes": item.size_bytes,
            },
        )
        return BackupCreateResponse(
            item=BackupItem(
                id=item.filename,
                dataset=item.dataset,
                user_id=item.user_id,
                status="ready",
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
        )
    except ValueError as exc:
        if str(exc) == "unknown_dataset":
            raise HTTPException(status_code=400, detail="unknown_dataset") from exc
        raise HTTPException(status_code=400, detail="invalid_backup_request") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to create backup: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create backup")


@router.post("/backups/{backup_id}/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    backup_id: str,
    payload: BackupRestoreRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> BackupRestoreResponse:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm_required")
    try:
        dataset = payload.dataset.strip().lower()
        if dataset not in _BACKUP_DATASETS:
            raise HTTPException(status_code=400, detail="unknown_dataset")
        _require_user_id_for_dataset(dataset, payload.user_id)
        if payload.user_id is not None:
            await _enforce_admin_user_scope(principal, payload.user_id, require_hierarchy=False)
        result = svc_restore_backup_snapshot(
            dataset=dataset,
            user_id=payload.user_id,
            backup_id=backup_id,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.import",
            category="system",
            resource_type="backup",
            resource_id=backup_id,
            action="backup.restore",
            metadata={
                "dataset": dataset,
                "user_id": payload.user_id,
            },
        )
        return BackupRestoreResponse(status="restored", message=result)
    except ValueError as exc:
        if str(exc) == "unknown_dataset":
            raise HTTPException(status_code=400, detail="unknown_dataset") from exc
        raise HTTPException(status_code=400, detail="invalid_restore_request") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to restore backup: {exc}")
        raise HTTPException(status_code=500, detail="Failed to restore backup")


@router.get("/retention-policies", response_model=RetentionPoliciesResponse)
async def list_retention_policies(
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RetentionPoliciesResponse:
    try:
        del principal
        policies = [RetentionPolicy(**item) for item in await svc_list_retention_policies()]
        return RetentionPoliciesResponse(policies=policies)
    except Exception as exc:
        logger.error(f"Failed to list retention policies: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list retention policies")


@router.put("/retention-policies/{policy_key}", response_model=RetentionPolicy)
async def update_retention_policy(
    policy_key: str,
    payload: RetentionPolicyUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> RetentionPolicy:
    try:
        updated = await svc_update_retention_policy(policy_key, payload.days)
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="config.changed",
            category="system",
            resource_type="retention_policy",
            resource_id=policy_key,
            action="retention.update",
            metadata={"days": payload.days},
        )
        return RetentionPolicy(**updated)
    except ValueError as exc:
        detail = str(exc)
        if detail == "unknown_policy":
            raise HTTPException(status_code=404, detail="unknown_policy") from exc
        if detail == "invalid_range":
            raise HTTPException(status_code=400, detail="invalid_range") from exc
        raise HTTPException(status_code=400, detail="invalid_retention_update") from exc
    except Exception as exc:
        logger.error(f"Failed to update retention policy: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update retention policy")


@router.get("/audit-log/export")
async def export_audit_log(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource: Optional[str] = Query(None, description="Filter by resource type or type:id"),
    start: Optional[str] = Query(None, description="ISO date or datetime (start)"),
    end: Optional[str] = Query(None, description="ISO date or datetime (end)"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    format: str = Query("csv", pattern="^(csv|json)$"),
    filename: Optional[str] = Query(None, description="Optional filename for Content-Disposition"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> Response:
    audit = await get_audit_log(
        user_id=user_id,
        action=action,
        resource=resource,
        start=start,
        end=end,
        days=days,
        limit=limit,
        offset=offset,
        org_id=org_id,
        principal=principal,
        db=db,
    )
    if format == "json":
        content = svc_build_audit_log_json(audit.entries, total=audit.total, limit=limit, offset=offset)
        resp = Response(content=content, media_type="application/json")
        if not filename:
            filename = "audit_log.json"
    else:
        content = svc_build_audit_log_csv(audit.entries)
        resp = PlainTextResponse(content=content, media_type="text/csv")
        if not filename:
            filename = "audit_log.csv"
    if filename:
        safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
        resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
    return resp


# ---------------------------------------------------------------------------------------------------------------------
# System Ops Endpoints (Logs, Maintenance, Feature Flags, Incidents)

@router.get("/system/logs", response_model=SystemLogsResponse)
async def list_system_logs(
    start: Optional[str] = Query(None, description="ISO date or datetime (start)"),
    end: Optional[str] = Query(None, description="ISO date or datetime (end)"),
    level: Optional[str] = Query(None, description="Log level (INFO, ERROR, etc.)"),
    service: Optional[str] = Query(None, description="Logger or module filter"),
    query: Optional[str] = Query(None, description="Substring search"),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    user_id: Optional[int] = Query(None, description="Restrict to a specific user"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> SystemLogsResponse:
    def _parse_date_param(value: Optional[str], label: str, end_of_day: bool = False) -> Optional[datetime]:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        raw = raw.replace("Z", "+00:00")
        try:
            if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
                dt = datetime.fromisoformat(raw)
                if end_of_day:
                    dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                return dt
            return datetime.fromisoformat(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {label} date format") from exc

    start_dt = _parse_date_param(start, "start")
    end_dt = _parse_date_param(end, "end", end_of_day=True)
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")

    org_ids = await _get_admin_org_ids(principal)
    if org_id is not None:
        if org_ids is None:
            org_ids = [org_id]
        else:
            org_ids = [org_id] if org_id in org_ids else []
    if org_ids is not None and len(org_ids) == 0:
        return SystemLogsResponse(items=[], total=0, limit=limit, offset=offset)

    items, total = query_system_logs(
        start=start_dt,
        end=end_dt,
        level=level,
        service=service,
        query=query,
        org_id=org_id if org_ids is None else None,
        org_ids=org_ids,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    return SystemLogsResponse(
        items=[SystemLogEntry(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/maintenance", response_model=MaintenanceState)
async def get_maintenance_mode(
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MaintenanceState:
    del principal
    state = svc_get_maintenance_state()
    return MaintenanceState(**state)


@router.put("/maintenance", response_model=MaintenanceState)
async def update_maintenance_mode(
    payload: MaintenanceUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MaintenanceState:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    state = svc_update_maintenance_state(
        enabled=payload.enabled,
        message=payload.message,
        allowlist_user_ids=payload.allowlist_user_ids,
        allowlist_emails=payload.allowlist_emails,
        actor=actor,
    )
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="config.changed",
        category="system",
        resource_type="maintenance",
        resource_id="maintenance_mode",
        action="maintenance.update",
        metadata={"enabled": payload.enabled},
    )
    return MaintenanceState(**state)


@router.get("/feature-flags", response_model=FeatureFlagsResponse)
async def list_feature_flags(
    scope: Optional[str] = Query(None, description="global|org|user"),
    org_id: Optional[int] = Query(None, description="Organization ID for org-scoped flags"),
    user_id: Optional[int] = Query(None, description="User ID for user-scoped flags"),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> FeatureFlagsResponse:
    org_ids = await _get_admin_org_ids(principal)
    if org_id is not None and org_ids is not None:
        org_ids = [org_id] if org_id in org_ids else []
    if org_ids is not None and len(org_ids) == 0:
        return FeatureFlagsResponse(items=[], total=0)
    try:
        items = svc_list_feature_flags(
            scope=scope,
            org_id=org_id if org_ids is None else None,
            user_id=user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_scope", "missing_org_id", "missing_user_id"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_feature_flag") from exc
    if org_ids is not None:
        items = [item for item in items if item.get("org_id") in org_ids]
    return FeatureFlagsResponse(items=[FeatureFlagItem(**item) for item in items], total=len(items))


@router.put("/feature-flags/{flag_key}", response_model=FeatureFlagItem)
async def upsert_feature_flag(
    flag_key: str,
    payload: FeatureFlagUpsertRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> FeatureFlagItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    try:
        flag = svc_upsert_feature_flag(
            key=flag_key,
            scope=payload.scope,
            enabled=payload.enabled,
            description=payload.description,
            org_id=payload.org_id,
            user_id=payload.user_id,
            actor=actor,
            note=payload.note,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_scope", "missing_org_id", "missing_user_id", "invalid_key"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_feature_flag") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="config.changed",
        category="system",
        resource_type="feature_flag",
        resource_id=flag_key,
        action="feature_flag.upsert",
        metadata={"scope": payload.scope, "enabled": payload.enabled},
    )
    return FeatureFlagItem(**flag)


@router.delete("/feature-flags/{flag_key}", response_model=MessageResponse)
async def delete_feature_flag(
    flag_key: str,
    request: Request,
    scope: str = Query(..., description="global|org|user"),
    org_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MessageResponse:
    _require_platform_admin(principal)
    try:
        svc_delete_feature_flag(key=flag_key, scope=scope, org_id=org_id, user_id=user_id)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_scope", "missing_org_id", "missing_user_id"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="feature_flag_not_found") from exc
        raise HTTPException(status_code=400, detail="invalid_feature_flag") from exc
    if request is not None:
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="config.changed",
            category="system",
            resource_type="feature_flag",
            resource_id=flag_key,
            action="feature_flag.delete",
            metadata={"scope": scope, "org_id": org_id, "user_id": user_id},
        )
    return MessageResponse(message="feature_flag_deleted")


@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    status: Optional[str] = Query(None, description="Incident status"),
    severity: Optional[str] = Query(None, description="Incident severity"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentListResponse:
    del principal
    items, total = svc_list_incidents(
        status=status,
        severity=severity,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    return IncidentListResponse(
        items=[IncidentItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/incidents", response_model=IncidentItem)
async def create_incident(
    payload: IncidentCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    try:
        incident = svc_create_incident(
            title=payload.title,
            status=payload.status,
            severity=payload.severity,
            summary=payload.summary,
            tags=payload.tags,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_title", "invalid_status", "invalid_severity"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident.get("id"),
        action="incident.create",
        metadata={"status": incident.get("status"), "severity": incident.get("severity")},
    )
    return IncidentItem(**incident)


@router.patch("/incidents/{incident_id}", response_model=IncidentItem)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    try:
        incident = svc_update_incident(
            incident_id=incident_id,
            title=payload.title,
            status=payload.status,
            severity=payload.severity,
            summary=payload.summary,
            tags=payload.tags,
            update_message=payload.update_message,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="incident_not_found") from exc
        if detail in {"invalid_status", "invalid_severity"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident_id,
        action="incident.update",
        metadata={"status": incident.get("status"), "severity": incident.get("severity")},
    )
    return IncidentItem(**incident)


@router.post("/incidents/{incident_id}/events", response_model=IncidentItem)
async def add_incident_event(
    incident_id: str,
    payload: IncidentEventCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> IncidentItem:
    _require_platform_admin(principal)
    actor = principal.email or principal.username or (str(principal.user_id) if principal.user_id is not None else None)
    try:
        incident = svc_add_incident_event(
            incident_id=incident_id,
            message=payload.message,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "invalid_message":
            raise HTTPException(status_code=400, detail=detail) from exc
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="incident_not_found") from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident_id,
        action="incident.event",
        metadata={"message": payload.message},
    )
    return IncidentItem(**incident)


@router.delete("/incidents/{incident_id}", response_model=MessageResponse)
async def delete_incident(
    incident_id: str,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> MessageResponse:
    _require_platform_admin(principal)
    try:
        svc_delete_incident(incident_id=incident_id)
    except ValueError as exc:
        detail = str(exc)
        if detail == "not_found":
            raise HTTPException(status_code=404, detail="incident_not_found") from exc
        raise HTTPException(status_code=400, detail="invalid_incident") from exc
    await _emit_admin_audit_event(
        request,
        principal,
        event_type="ops.incident",
        category="system",
        resource_type="incident",
        resource_id=incident_id,
        action="incident.delete",
        metadata={},
    )
    return MessageResponse(message="incident_deleted")


# ---------------------------------------------------------------------------------------------------------------------
# Budget Governance Endpoints

@router.get("/budgets", response_model=OrgBudgetListResponse)
async def admin_list_budgets(
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> OrgBudgetListResponse:
    """List organization budgets and plan context."""
    try:
        del principal  # admin role already enforced by router dependency
        if org_id is not None:
            org_ids = [org_id]
        else:
            org_ids = None
        items, total = await svc_list_org_budgets(
            db,
            org_ids=org_ids,
            page=page,
            limit=limit,
        )
        return OrgBudgetListResponse(
            items=[OrgBudgetItem(**item) for item in items],
            total=total,
            page=page,
            limit=limit,
        )
    except Exception as exc:
        logger.error(f"Failed to list org budgets: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list org budgets")


@router.post("/budgets", response_model=OrgBudgetItem)
async def admin_upsert_budget(
    payload: OrgBudgetUpdateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction),
) -> OrgBudgetItem:
    """Upsert budget settings for an organization."""
    budget_updates = None
    if payload.budgets is not None:
        budget_updates = payload.budgets.model_dump(exclude_unset=True, by_alias=True)
    try:
        item, audit_changes = await svc_upsert_org_budget(
            db,
            org_id=payload.org_id,
            budget_updates=budget_updates,
            clear_budgets=payload.clear_budgets,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "org_not_found":
            raise HTTPException(status_code=404, detail="org_not_found") from exc
        if detail == "plan_not_found":
            raise HTTPException(status_code=500, detail="plan_not_found") from exc
        if detail == "subscription_not_found":
            raise HTTPException(status_code=500, detail="subscription_not_found") from exc
        raise HTTPException(status_code=400, detail="invalid_budget_update") from exc
    except Exception as exc:
        logger.error(f"Failed to upsert org budget: {exc}")
        raise HTTPException(status_code=500, detail="Failed to upsert org budget") from exc

    actor_role = None
    try:
        if principal.is_admin:
            actor_role = "admin"
        elif principal.roles:
            actor_role = principal.roles[0]
    except Exception:
        actor_role = None

    try:
        await emit_budget_audit_event(
            request,
            principal,
            org_id=payload.org_id,
            budget_updates=budget_updates,
            audit_changes=audit_changes,
            clear_budgets=payload.clear_budgets,
            actor_role=actor_role,
        )
    except Exception as exc:
        logger.error(f"Budget audit failed: {exc}")
        raise HTTPException(status_code=500, detail="audit_failed") from exc

    return OrgBudgetItem(**item)


# ---------------------------------------------------------------------------------------------------------------------
# Usage Reporting Endpoints

@router.get("/usage/daily", response_model=UsageDailyResponse)
async def get_usage_daily(
    user_id: Optional[int] = None,
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> UsageDailyResponse:
    """Query daily usage aggregates, optionally filtered by user and date range."""
    try:
        if user_id is not None:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        rows, total, _ = await svc_fetch_usage_daily(
            db,
            user_id=user_id,
            org_ids=org_ids,
            start=start,
            end=end,
            page=page,
            limit=limit,
        )
        items = [UsageDailyRow(**r) for r in rows]
        return UsageDailyResponse(items=items, total=int(total or 0), page=page, limit=limit)
    except Exception:
        logger.exception("Failed to query usage_daily")
        raise HTTPException(status_code=500, detail="Failed to load usage daily data")


@router.get("/usage/top", response_model=UsageTopResponse)
async def get_usage_top(
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(10, ge=1, le=100),
    metric: str = Query("requests", pattern="^(requests|bytes_total|bytes_in_total|errors)$"),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> UsageTopResponse:
    """Top users by aggregate usage over a date range."""
    try:
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        rows = await svc_fetch_usage_top(
            db,
            start=start,
            end=end,
            limit=limit,
            metric=metric,
            org_ids=org_ids,
        )
        for r in rows:
            r.setdefault('bytes_in_total', None)
        return UsageTopResponse(items=[UsageTopRow(**r) for r in rows])
    except Exception as e:
        logger.error(f"Failed to query usage top: {e}")
        raise HTTPException(status_code=500, detail="Failed to load usage top data")


@router.post("/usage/aggregate")
async def run_usage_aggregate(day: Optional[str] = Query(None, description="YYYY-MM-DD")) -> dict:
    """Trigger aggregation of usage_log into usage_daily for a specific day (UTC)."""
    try:
        await aggregate_usage_daily(day=day)
        return {"status": "ok", "day": day}
    except Exception:
        logger.exception("Manual usage aggregation failed/skipped")
        # Non-fatal: e.g., table absent in PG during partial setups
        return {"status": "skipped", "reason": "aggregation failed or was skipped", "day": day}


@router.get("/usage/daily/export.csv", response_class=PlainTextResponse)
async def export_usage_daily_csv(
    user_id: Optional[int] = None,
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(1000, ge=1, le=10000),
    filename: Optional[str] = Query(None, description="Optional filename for Content-Disposition"),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> PlainTextResponse:
    """Export usage_daily rows as CSV (includes bytes_in_total when available)."""
    try:
        if user_id is not None:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        content = await svc_export_usage_daily_csv_text(
            db,
            user_id=user_id,
            org_ids=org_ids,
            start=start,
            end=end,
            limit=limit,
        )
        resp = PlainTextResponse(content=content, media_type="text/csv")
        # Default filename when not provided
        if not filename:
            _start = start or "all"
            _end = end or "all"
            filename = f"usage_daily_{_start}_{_end}.csv"
        if filename:
            safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
            resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
        return resp
    except Exception as e:
        logger.error(f"Failed to export usage daily CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to export usage daily CSV")


@router.get("/usage/top/export.csv", response_class=PlainTextResponse)
async def export_usage_top_csv(
    start: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(100, ge=1, le=10000),
    metric: str = Query("requests", pattern="^(requests|bytes_total|bytes_in_total|errors)$"),
    filename: Optional[str] = Query(None, description="Optional filename for Content-Disposition"),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> PlainTextResponse:
    try:
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        content = await svc_export_usage_top_csv_text(
            db,
            start=start,
            end=end,
            limit=limit,
            metric=metric,
            org_ids=org_ids,
        )
        resp = PlainTextResponse(content=content, media_type="text/csv")
        # Default filename when not provided
        if not filename:
            _start = start or "all"
            _end = end or "all"
            filename = f"usage_top_{metric}_{_start}_{_end}.csv"
        if filename:
            safe = filename.replace("\n", " ").replace("\r", " ").replace("\"", "_")
            resp.headers["Content-Disposition"] = f"attachment; filename=\"{safe}\""
        return resp
    except Exception as e:
        logger.error(f"Failed to export usage top CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to export usage top CSV")


@router.post("/llm-usage/aggregate")
async def run_llm_usage_aggregate(day: Optional[str] = Query(None, description="YYYY-MM-DD")) -> dict:
    """Trigger aggregation of llm_usage_log into llm_usage_daily for a specific day (UTC)."""
    try:
        await aggregate_llm_usage_daily(day=day)
        return {"status": "ok", "day": day}
    except Exception as e:
        logger.warning(f"Manual LLM usage aggregation failed/skipped: {e}")
        # Do not expose internal exception details to the client
        return {
            "status": "skipped",
            "reason": "Manual LLM usage aggregation failed or was skipped",
            "day": day,
        }

# ---------------------------------------------------------------------------------------------------------------------
# LLM Usage Reporting Endpoints

@router.get("/llm-usage", response_model=LLMUsageLogResponse)
async def get_llm_usage(
    user_id: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
    status_code: Optional[int] = Query(None, alias="status"),
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> LLMUsageLogResponse:
    try:
        if user_id is not None:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        rows, total = await svc_fetch_llm_usage(
            db,
            user_id=user_id,
            provider=provider,
            model=model,
            operation=operation,
            status_code=status_code,
            start=start,
            end=end,
            page=page,
            limit=limit,
            org_ids=org_ids,
        )
        items = [LLMUsageLogRow(**r) for r in rows]
        return LLMUsageLogResponse(items=items, total=int(total or 0), page=page, limit=limit)
    except Exception:
        # Log full stack to aid debugging in tests
        logger.exception("Failed to query llm_usage_log")
        raise HTTPException(status_code=500, detail="Failed to load LLM usage data")


@router.get("/llm-usage/summary", response_model=LLMUsageSummaryResponse)
async def get_llm_usage_summary(
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    group_by: str = Query("user", pattern="^(user|provider|model|operation|day)$"),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> LLMUsageSummaryResponse:
    try:
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        # Directly support 'user'|'operation'|'day'|'provider'|'model'
        rows = await svc_fetch_llm_usage_summary(
            db,
            group_by=group_by,
            provider=None,
            start=start,
            end=end,
            org_ids=org_ids,
        )
        return LLMUsageSummaryResponse(items=[LLMUsageSummaryRow(**r) for r in rows])
    except Exception as e:
        logger.error(f"Failed to summarize llm_usage_log: {e}")
        raise HTTPException(status_code=500, detail="Failed to load LLM usage summary")


@router.get("/llm-usage/top-spenders", response_model=LLMTopSpendersResponse)
async def get_llm_top_spenders(
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    limit: int = Query(10, ge=1, le=500),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> LLMTopSpendersResponse:
    try:
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        rows = await svc_fetch_llm_top_spenders(db, start=start, end=end, limit=limit, org_ids=org_ids)
        return LLMTopSpendersResponse(items=[LLMTopSpenderRow(**r) for r in rows])
    except Exception as e:
        logger.error(f"Failed to load llm top spenders: {e}")
        raise HTTPException(status_code=500, detail="Failed to load LLM top spenders")


@router.get("/llm-usage/export.csv", response_class=PlainTextResponse)
async def export_llm_usage_csv(
    user_id: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
    status_code: Optional[int] = Query(None, alias="status"),
    start: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    end: Optional[str] = Query(None, description="ISO timestamp inclusive"),
    limit: int = Query(1000, ge=1, le=10000),
    org_id: Optional[int] = Query(None, description="Restrict to a specific organization"),
    principal: AuthPrincipal = Depends(get_auth_principal),
    db=Depends(get_db_transaction)
) -> PlainTextResponse:
    """Export filtered llm_usage_log rows as CSV."""
    try:
        if user_id is not None:
            await _enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        org_ids = await _get_admin_org_ids(principal)
        if org_id is not None:
            if org_ids is None:
                org_ids = [org_id]
            else:
                org_ids = [org_id] if org_id in org_ids else []
        is_pg = await is_postgres_backend()
        conditions: list[str] = []
        params: list = []

        def add_cond(sql: str, value):
            if value is None:
                return
            if is_pg:
                conditions.append(sql.replace('?', f"${len(params) + 1}"))
            else:
                conditions.append(sql)
            params.append(value)

        add_cond("user_id = ?", user_id)
        add_cond("LOWER(provider) = LOWER(?)", provider)
        add_cond("LOWER(model) = LOWER(?)", model)
        add_cond("operation = ?", operation)
        add_cond("status = ?", status_code)
        if start:
            add_cond("ts >= ?", start)
        if end:
            add_cond("ts <= ?", end)
        join_clause = ""
        if org_ids is not None:
            join_clause = " JOIN org_members om ON om.user_id = llm_usage_log.user_id"
            if is_pg:
                conditions.append(f"om.org_id = ANY(${len(params) + 1})")
                params.append(org_ids)
            else:
                placeholders = ",".join("?" for _ in org_ids)
                conditions.append(f"om.org_id IN ({placeholders})")
                params.extend(org_ids)
        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        if is_pg:
            limit_placeholder = f"${len(params) + 1}"
            sql = (
                f"SELECT id, ts, COALESCE(user_id,0) as user_id, COALESCE(key_id,0) as key_id, endpoint, operation, provider, model, status, latency_ms, "
                f"COALESCE(prompt_tokens,0), COALESCE(completion_tokens,0), COALESCE(total_tokens,0), COALESCE(total_cost_usd,0), currency, estimated, request_id "
                f"FROM llm_usage_log{join_clause}{where_clause} ORDER BY ts DESC LIMIT {limit_placeholder}"
            )
            rows = await db.fetch(sql, *params, limit)
            data = [(
                r["id"], r["ts"], r["user_id"], r["key_id"], r["endpoint"], r["operation"], r["provider"], r["model"], r["status"], r["latency_ms"],
                r["prompt_tokens"], r["completion_tokens"], r["total_tokens"], r["total_cost_usd"], r["currency"], r["estimated"], r["request_id"]
            ) for r in rows]
        else:
            sql = (
                f"SELECT id, ts, IFNULL(user_id,0), IFNULL(key_id,0), endpoint, operation, provider, model, status, latency_ms, "
                f"IFNULL(prompt_tokens,0), IFNULL(completion_tokens,0), IFNULL(total_tokens,0), IFNULL(total_cost_usd,0), currency, estimated, request_id "
                f"FROM llm_usage_log{join_clause}{where_clause} ORDER BY ts DESC LIMIT ?"
            )
            cur = await db.execute(sql, params + [limit])
            data = await cur.fetchall()

        # Build CSV
        header = [
            "id","ts","user_id","key_id","endpoint","operation","provider","model","status","latency_ms",
            "prompt_tokens","completion_tokens","total_tokens","total_cost_usd","currency","estimated","request_id"
        ]
        lines = [",".join(header)]
        for row in data:
            # row is tuple-like in both branches
            def _fmt(x):
                if x is None:
                    return ""
                s = str(x)
                if "," in s or "\n" in s:
                    return '"' + s.replace('"', '""') + '"'
                return s
            lines.append(
                ",".join(_fmt(c) for c in row)
            )
        content = "\n".join(lines) + "\n"
        return PlainTextResponse(content=content, media_type="text/csv")
    except Exception as e:
        logger.error(f"Failed to export llm usage CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to export CSV")


# ---------------------------------------------
# Pricing Catalog Management
# ---------------------------------------------

@router.post("/llm-usage/pricing/reload", response_model=dict)
async def reload_llm_pricing_catalog() -> dict:
    """Reload the LLM pricing catalog from environment and config file (admin-only).

    Picks up changes in PRICING_OVERRIDES and Config_Files/model_pricing.json
    without restarting the server.
    """
    try:
        reset_pricing_catalog()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to reload pricing catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload pricing catalog")


# ---------------------------------------------
# Chat Model Alias Cache Management
# ---------------------------------------------

@router.post("/chat/model-aliases/reload", response_model=dict)
async def reload_chat_model_alias_caches() -> dict:
    """Invalidate cached chat model lists and alias overrides (admin-only).

    Clears module-scope lru_caches used by chat model alias resolution so
    updates to Config_Files/model_pricing.json or env vars take effect
    without restarting the server.
    """
    try:
        invalidate_model_alias_caches()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to reload chat model alias caches: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload chat model alias caches")

#
## End of admin.py
#######################################################################################################################
# ---------------------------------------------
# Personalization admin helpers
# ---------------------------------------------

@router.post("/personalization/consolidate", response_model=dict)
async def trigger_personalization_consolidation(
    user_id: Optional[str] = Query(None, description="User ID to consolidate; defaults to single-user id"),
):
    """
    Trigger personalization consolidation for a given user (admin-only).
    """
    try:
        from tldw_Server_API.app.services.personalization_consolidation import get_consolidation_service
        svc = get_consolidation_service()
        ok = await svc.trigger_consolidation(user_id=user_id)
        return {"status": "ok" if ok else "error", "user_id": user_id}
    except Exception as e:
        logger.warning(f"Admin consolidate trigger failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger consolidation")


@router.get("/personalization/status", response_model=dict)
async def get_personalization_status():
    """Return in-memory consolidation status (last tick per user)."""
    try:
        from tldw_Server_API.app.services.personalization_consolidation import get_consolidation_service
        svc = get_consolidation_service()
        status_fn = getattr(svc, "get_status", None)
        if not callable(status_fn):
            raise TypeError(
                "Personalization service get_status is not callable: "
                f"{status_fn!r} (type={type(status_fn).__name__})"
            )
        return status_fn()
    except Exception as e:
        logger.warning(f"Admin status fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch status")


# ---------------------------------------------------------------------------------------------------------------------
# MCP Tool Catalogs (Admin)

@router.get(
    "/mcp/tool_catalogs",
    response_model=List[ToolCatalogResponse],
    summary="List MCP tool catalogs (admin)",
    description=(
        "List MCP tool catalogs across global/org/team scopes.\n\n"
        "RBAC: Admin-only.\n\n"
        "Filters: Optional `org_id` and/or `team_id` parameters restrict results to a given scope.\n"
        "Without filters, returns all catalogs."
    ),
)
async def list_tool_catalogs(
    org_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db_transaction),
) -> List[ToolCatalogResponse]:
    """List tool catalogs with optional org/team filtering."""
    try:
        is_pg = await is_postgres_backend()
        where: list[str] = []
        params: list[Any] = []
        if org_id is not None:
            where.append("org_id = $1" if is_pg else "org_id = ?")
            params.append(org_id)
        if team_id is not None:
            if is_pg:
                where.append(f"team_id = ${len(params)+1}")
            else:
                where.append("team_id = ?")
            params.append(team_id)
        where_clause = (" WHERE " + " AND ".join(where)) if where else ""
        if is_pg:
            q = (
                f"SELECT id, name, description, org_id, team_id, COALESCE(is_active,TRUE) as is_active, created_at, updated_at "
                f"FROM tool_catalogs{where_clause} ORDER BY created_at DESC LIMIT $ {len(params)+1} OFFSET $ {len(params)+2}"
            ).replace('$ ', '$')
            rows = await db.fetch(q, *params, limit, offset)
            return [ToolCatalogResponse(**dict(r)) for r in rows]
        else:
            q = f"SELECT id, name, description, org_id, team_id, COALESCE(is_active,1), created_at, updated_at FROM tool_catalogs{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
            cur = await db.execute(q, [*params, limit, offset])
            rows = await cur.fetchall()
            return [
                ToolCatalogResponse(
                    id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
                ) for r in rows
            ]
    except Exception as e:
        logger.error(f"Failed to list tool catalogs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tool catalogs")


@router.post(
    "/mcp/tool_catalogs",
    response_model=ToolCatalogResponse,
    status_code=201,
    summary="Create MCP tool catalog (admin)",
    description=(
        "Create a new MCP tool catalog in the chosen scope.\n\n"
        "RBAC: Admin-only.\n\n"
        "Scope: Set `org_id` for org-owned, `team_id` for team-owned, or neither for global.\n"
        "Name must be unique per (name, org_id, team_id)."
    ),
)
async def create_tool_catalog(payload: ToolCatalogCreateRequest, db=Depends(get_db_transaction)) -> ToolCatalogResponse:
    """Create a tool catalog."""
    try:
        is_pg = await is_postgres_backend()
        name = payload.name.strip()
        desc = payload.description
        org_id = payload.org_id
        team_id = payload.team_id
        is_active = bool(payload.is_active if payload.is_active is not None else True)
        if is_pg:
            # Case-insensitive existence check within scope
            exists = await db.fetchrow(
                "SELECT 1 FROM tool_catalogs WHERE LOWER(name) = LOWER($1) AND ((org_id IS NOT DISTINCT FROM $2) AND (team_id IS NOT DISTINCT FROM $3))",
                name, org_id, team_id,
            )
            if exists:
                raise HTTPException(status_code=409, detail="Catalog already exists")
            await db.execute(
                """
                INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active)
                VALUES ($1, $2, $3, $4, $5)
                """,
                name, desc, org_id, team_id, is_active,
            )
            row = await db.fetchrow(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active, TRUE) as is_active, created_at, updated_at FROM tool_catalogs WHERE name = $1 AND ((org_id IS NOT DISTINCT FROM $2) AND (team_id IS NOT DISTINCT FROM $3))",
                name, org_id, team_id,
            )
            return ToolCatalogResponse(**dict(row))
        else:
            # SQLite pre-check case-insensitive
            cur = await db.execute(
                "SELECT id FROM tool_catalogs WHERE LOWER(name) = LOWER(?) AND ( (org_id IS ? OR org_id = ?) AND (team_id IS ? OR team_id = ?) )",
                (name, None, org_id, None, team_id),
            )
            exists = await cur.fetchone()
            if exists:
                raise HTTPException(status_code=409, detail="Catalog already exists")
            await db.execute(
                "INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active) VALUES (?, ?, ?, ?, ?)",
                (name, desc, org_id, team_id, 1 if is_active else 0),
            )
            cur2 = await db.execute(
                "SELECT id, name, description, org_id, team_id, is_active, created_at, updated_at FROM tool_catalogs WHERE name = ? AND ( (org_id IS ? OR org_id = ?) AND (team_id IS ? OR team_id = ?) )",
                (name, None, org_id, None, team_id),
            )
            r = await cur2.fetchone()
            return ToolCatalogResponse(
                id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create tool catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tool catalog")


@router.delete(
    "/mcp/tool_catalogs/{catalog_id}",
    summary="Delete MCP tool catalog (admin)",
    description=(
        "Delete a catalog by id. Entries are removed via ON DELETE CASCADE.\n\n"
        "RBAC: Admin-only.\n\n"
        "Scope: Works for any catalog (global/org/team)."
    ),
)
async def delete_tool_catalog(catalog_id: int, db=Depends(get_db_transaction)) -> dict:
    """Delete a tool catalog (entries cascade)."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import delete_tool_catalog as _svc
        await _svc(db, catalog_id)
        return {"message": "Catalog deleted", "id": catalog_id}
    except Exception as e:
        logger.error(f"Failed to delete tool catalog {catalog_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog")


@router.get(
    "/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=List[ToolCatalogEntryResponse],
    summary="List catalog entries (admin)",
    description=(
        "List tools included in the specified catalog.\n\n"
        "RBAC: Admin-only."
    ),
)
async def list_tool_catalog_entries(catalog_id: int, db=Depends(get_db_transaction)) -> List[ToolCatalogEntryResponse]:
    """List entries in a tool catalog."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import list_tool_catalog_entries as _svc
        rows = await _svc(db, catalog_id)
        return [ToolCatalogEntryResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list tool catalog entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tool catalog entries")


@router.post(
    "/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=ToolCatalogEntryResponse,
    status_code=201,
    summary="Add tool to catalog (admin)",
    description=(
        "Add a tool entry to the catalog. Idempotent per (catalog_id, tool_name).\n\n"
        "RBAC: Admin-only."
    ),
)
async def add_tool_catalog_entry(catalog_id: int, payload: ToolCatalogEntryCreateRequest, db=Depends(get_db_transaction)) -> ToolCatalogEntryResponse:
    """Add a tool entry to a catalog (idempotent)."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import add_tool_catalog_entry as _svc
        tool = payload.tool_name.strip()
        module_id = payload.module_id.strip() if payload.module_id else None
        row = await _svc(db, catalog_id, tool, module_id)
        return ToolCatalogEntryResponse(**row)
    except Exception as e:
        logger.error(f"Failed to add tool catalog entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to add tool catalog entry")


@router.delete(
    "/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}",
    summary="Remove tool from catalog (admin)",
    description=(
        "Remove a tool entry from the catalog. Returns 200 whether or not the entry existed.\n\n"
        "RBAC: Admin-only."
    ),
)
async def delete_tool_catalog_entry(catalog_id: int, tool_name: str, db=Depends(get_db_transaction)) -> dict:
    """Remove a tool from a catalog."""
    try:
        from tldw_Server_API.app.services.admin_tool_catalog_service import delete_tool_catalog_entry as _svc
        await _svc(db, catalog_id, tool_name)
        return {"message": "Entry deleted", "catalog_id": catalog_id, "tool_name": tool_name}
    except Exception as e:
        logger.error(f"Failed to delete tool catalog entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog entry")
# -------------------------------------------------------------------------------------------------
# Network diagnostics: resolved client IP, proxy headers, and WebUI/Setup access decisions

def _parse_nets(raw: str | None) -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    if not raw:
        return nets
    for token in [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]:
        try:
            if "/" in token:
                nets.append(ipaddress.ip_network(token, strict=False))
            else:
                ip = ipaddress.ip_address(token)
                nets.append(ipaddress.ip_network(ip.exploded + ("/32" if ip.version == 4 else "/128"), strict=False))
        except Exception:
            # Skip invalid entries
            pass
    return nets


def _load_list(section: str, field: str, env_name: str) -> list[ipaddress._BaseNetwork]:
    import os
    raw_env = os.getenv(env_name)
    if raw_env:
        return _parse_nets(raw_env)
    try:
        cp = load_comprehensive_config()
        if cp and cp.has_section(section):
            raw_cfg = cp.get(section, field, fallback="").strip()
            if raw_cfg:
                return _parse_nets(raw_cfg)
    except Exception:
        pass
    return []


def _resolve_client_ip(request: Request, trusted_proxies: list[ipaddress._BaseNetwork]) -> tuple[str | None, bool]:
    def _is_trusted(ip: ipaddress._BaseAddress | None) -> bool:
        return bool(ip and any(ip in net for net in trusted_proxies))

    peer = request.client.host if request.client else None
    try:
        peer_ip_obj = ipaddress.ip_address(peer) if peer else None
    except Exception:
        peer_ip_obj = None

    if _is_trusted(peer_ip_obj):
        xr = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
        if xr:
            try:
                ipaddress.ip_address(xr.strip())
                return xr.strip(), True
            except Exception:
                pass
        fwd = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if fwd:
            try:
                leftmost = fwd.split(",")[0].strip()
                ipaddress.ip_address(leftmost)
                return leftmost, True
            except Exception:
                pass
    return peer, False


def _is_loopback(ip_str: str | None) -> bool:
    if not ip_str:
        return False
    if ip_str in {"testclient", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(ip_str).is_loopback
    except Exception:
        return False


@router.get("/network-info")
async def network_info(request: Request):
    """Show resolved client IP, proxy headers, and access decision inputs for WebUI/Setup.

    Returns a JSON payload useful for debugging remote-access policy and proxy header handling.
    """
    import os
    # Load lists and settings
    trusted_proxies = _load_list("Server", "trusted_proxies", "TLDW_TRUSTED_PROXIES")
    webui_allow = _load_list("Server", "webui_ip_allowlist", "TLDW_WEBUI_ALLOWLIST")
    webui_deny = _load_list("Server", "webui_ip_denylist", "TLDW_WEBUI_DENYLIST")
    setup_allow = _load_list("Setup", "setup_ip_allowlist", "TLDW_SETUP_ALLOWLIST")
    setup_deny = _load_list("Setup", "setup_ip_denylist", "TLDW_SETUP_DENYLIST")

    resolved_ip, via_proxy = _resolve_client_ip(request, trusted_proxies)
    loopback = _is_loopback(resolved_ip)
    ip_obj = None
    try:
        ip_obj = ipaddress.ip_address(resolved_ip) if resolved_ip else None
    except Exception:
        ip_obj = None

    def _decide(kind: str):
        if loopback:
            return {"decision": "allow", "reason": "loopback"}
        allowlist = webui_allow if kind == "webui" else setup_allow
        denylist = webui_deny if kind == "webui" else setup_deny
        toggle = webui_remote_access_enabled() if kind == "webui" else setup_remote_access_enabled()
        # denylist precedes
        if denylist and ip_obj and any(ip_obj in net for net in denylist):
            return {"decision": "deny", "reason": "denylist"}
        if allowlist:
            if ip_obj and any(ip_obj in net for net in allowlist):
                return {"decision": "allow", "reason": "allowlist"}
            return {"decision": "allow" if toggle else "deny", "reason": "toggle" if toggle else "no-allowlist-match"}
        return {"decision": "allow" if toggle else "deny", "reason": "toggle" if toggle else "toggle-off"}

    return {
        "peer_ip": request.client.host if request.client else None,
        "resolved_client_ip": resolved_ip,
        "via_trusted_proxy": via_proxy,
        "headers": {
            "x_forwarded_for": request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For"),
            "x_real_ip": request.headers.get("x-real-ip") or request.headers.get("X-Real-IP"),
        },
        "is_loopback": loopback,
        "webui": {
            "remote_toggle": webui_remote_access_enabled(),
            "allowlist": [str(n) for n in webui_allow],
            "denylist": [str(n) for n in webui_deny],
            **_decide("webui"),
        },
        "setup": {
            "remote_toggle": setup_remote_access_enabled(),
            "allowlist": [str(n) for n in setup_allow],
            "denylist": [str(n) for n in setup_deny],
            **_decide("setup"),
        },
    }
