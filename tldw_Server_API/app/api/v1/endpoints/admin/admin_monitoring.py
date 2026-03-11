from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminAlertAssignRequest,
    AdminAlertEscalateRequest,
    AdminAlertEventResponse,
    AdminAlertHistoryListResponse,
    AdminAlertRuleCreateRequest,
    AdminAlertRuleCreateResponse,
    AdminAlertRuleDeleteResponse,
    AdminAlertRuleListResponse,
    AdminAlertRuleResponse,
    AdminAlertSnoozeRequest,
    AdminAlertStateMutationResponse,
    AdminAlertStateResponse,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.admin_monitoring_repo import (
    AuthnzAdminMonitoringRepo,
)
from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo

router = APIRouter()


_MONITORING_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    asyncio.TimeoutError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    HTTPException,
)


async def _emit_admin_audit_event(
    request: Request,
    principal: AuthPrincipal,
    *,
    event_type: str,
    category: str,
    resource_type: str,
    resource_id: str | None,
    action: str,
    metadata: dict[str, Any],
) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    await admin_mod._emit_admin_audit_event(
        request,
        principal,
        event_type=event_type,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        metadata=metadata,
    )


async def _get_monitoring_repo() -> AuthnzAdminMonitoringRepo:
    pool = await get_db_pool()
    repo = AuthnzAdminMonitoringRepo(pool)
    await repo.ensure_schema()
    return repo


async def _get_users_repo() -> AuthnzUsersRepo:
    pool = await get_db_pool()
    return AuthnzUsersRepo(db_pool=pool)


def _principal_actor_id(principal: AuthPrincipal) -> int | None:
    try:
        return int(principal.user_id) if principal.user_id is not None else None
    except (TypeError, ValueError):
        return None


def _parse_event_details(details_json: str | None) -> dict[str, Any] | None:
    if not details_json:
        return None
    try:
        parsed = json.loads(details_json)
    except json.JSONDecodeError:
        return {"raw": details_json}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _event_response_from_row(row: dict[str, Any]) -> AdminAlertEventResponse:
    return AdminAlertEventResponse(
        id=int(row["id"]),
        alert_identity=str(row["alert_identity"]),
        action=str(row["action"]),
        actor_user_id=row.get("actor_user_id"),
        details=_parse_event_details(row.get("details_json")),
        created_at=row.get("created_at"),
    )


@router.get("/monitoring/alert-rules", response_model=AdminAlertRuleListResponse)
async def list_alert_rules(
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminAlertRuleListResponse:
    try:
        del principal
        repo = await _get_monitoring_repo()
        items = [AdminAlertRuleResponse(**row) for row in await repo.list_rules()]
        return AdminAlertRuleListResponse(items=items)
    except _MONITORING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list admin alert rules: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list alert rules") from exc


@router.post("/monitoring/alert-rules", response_model=AdminAlertRuleCreateResponse)
async def create_alert_rule(
    payload: AdminAlertRuleCreateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminAlertRuleCreateResponse:
    try:
        repo = await _get_monitoring_repo()
        actor_id = _principal_actor_id(principal)
        created = await repo.create_rule(
            metric=payload.metric,
            operator=payload.operator,
            threshold=payload.threshold,
            duration_minutes=payload.duration_minutes,
            severity=payload.severity,
            enabled=payload.enabled,
            created_by_user_id=actor_id,
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="config.changed",
            category="system",
            resource_type="admin_alert_rule",
            resource_id=str(created["id"]),
            action="monitoring.rule.create",
            metadata={
                "metric": payload.metric,
                "operator": payload.operator,
                "severity": payload.severity,
            },
        )
        return AdminAlertRuleCreateResponse(item=AdminAlertRuleResponse(**created))
    except _MONITORING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to create admin alert rule: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create alert rule") from exc


@router.delete("/monitoring/alert-rules/{rule_id}", response_model=AdminAlertRuleDeleteResponse)
async def delete_alert_rule(
    rule_id: int,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminAlertRuleDeleteResponse:
    try:
        repo = await _get_monitoring_repo()
        existing = await repo.get_rule(rule_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="unknown_rule")
        deleted = await repo.delete_rule(rule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="unknown_rule")
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="config.changed",
            category="system",
            resource_type="admin_alert_rule",
            resource_id=str(rule_id),
            action="monitoring.rule.delete",
            metadata={"metric": existing.get("metric")},
        )
        return AdminAlertRuleDeleteResponse(status="deleted", id=rule_id)
    except HTTPException:
        raise
    except _MONITORING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to delete admin alert rule: {exc}")
        raise HTTPException(status_code=500, detail="Failed to delete alert rule") from exc


@router.post("/monitoring/alerts/{alert_identity}/assign", response_model=AdminAlertStateMutationResponse)
async def assign_alert(
    alert_identity: str,
    payload: AdminAlertAssignRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminAlertStateMutationResponse:
    try:
        users_repo = await _get_users_repo()
        assignee = await users_repo.get_user_by_id(payload.assigned_to_user_id)
        if assignee is None:
            raise HTTPException(status_code=404, detail="unknown_user")
        repo = await _get_monitoring_repo()
        actor_id = _principal_actor_id(principal)
        state = await repo.upsert_alert_state(
            alert_identity=alert_identity,
            assigned_to_user_id=payload.assigned_to_user_id,
            updated_by_user_id=actor_id,
        )
        await repo.append_alert_event(
            alert_identity=alert_identity,
            action="assigned",
            actor_user_id=actor_id,
            details_json=json.dumps({"assigned_to_user_id": payload.assigned_to_user_id}),
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.update",
            category="system",
            resource_type="monitoring_alert",
            resource_id=alert_identity,
            action="monitoring.alert.assign",
            metadata={"assigned_to_user_id": payload.assigned_to_user_id},
        )
        return AdminAlertStateMutationResponse(item=AdminAlertStateResponse(**state))
    except HTTPException:
        raise
    except _MONITORING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to assign monitoring alert: {exc}")
        raise HTTPException(status_code=500, detail="Failed to assign alert") from exc


@router.post("/monitoring/alerts/{alert_identity}/snooze", response_model=AdminAlertStateMutationResponse)
async def snooze_alert(
    alert_identity: str,
    payload: AdminAlertSnoozeRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminAlertStateMutationResponse:
    try:
        repo = await _get_monitoring_repo()
        actor_id = _principal_actor_id(principal)
        state = await repo.upsert_alert_state(
            alert_identity=alert_identity,
            snoozed_until=payload.snoozed_until.isoformat(),
            updated_by_user_id=actor_id,
        )
        await repo.append_alert_event(
            alert_identity=alert_identity,
            action="snoozed",
            actor_user_id=actor_id,
            details_json=json.dumps({"snoozed_until": payload.snoozed_until.isoformat()}),
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.update",
            category="system",
            resource_type="monitoring_alert",
            resource_id=alert_identity,
            action="monitoring.alert.snooze",
            metadata={"snoozed_until": payload.snoozed_until.isoformat()},
        )
        return AdminAlertStateMutationResponse(item=AdminAlertStateResponse(**state))
    except _MONITORING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to snooze monitoring alert: {exc}")
        raise HTTPException(status_code=500, detail="Failed to snooze alert") from exc


@router.post("/monitoring/alerts/{alert_identity}/escalate", response_model=AdminAlertStateMutationResponse)
async def escalate_alert(
    alert_identity: str,
    payload: AdminAlertEscalateRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminAlertStateMutationResponse:
    try:
        repo = await _get_monitoring_repo()
        actor_id = _principal_actor_id(principal)
        state = await repo.upsert_alert_state(
            alert_identity=alert_identity,
            escalated_severity=payload.severity,
            updated_by_user_id=actor_id,
        )
        await repo.append_alert_event(
            alert_identity=alert_identity,
            action="escalated",
            actor_user_id=actor_id,
            details_json=json.dumps({"severity": payload.severity}),
        )
        await _emit_admin_audit_event(
            request,
            principal,
            event_type="data.update",
            category="system",
            resource_type="monitoring_alert",
            resource_id=alert_identity,
            action="monitoring.alert.escalate",
            metadata={"severity": payload.severity},
        )
        return AdminAlertStateMutationResponse(item=AdminAlertStateResponse(**state))
    except _MONITORING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to escalate monitoring alert: {exc}")
        raise HTTPException(status_code=500, detail="Failed to escalate alert") from exc


@router.get("/monitoring/alerts/history", response_model=AdminAlertHistoryListResponse)
async def list_alert_history(
    alert_identity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> AdminAlertHistoryListResponse:
    try:
        del principal
        repo = await _get_monitoring_repo()
        items = [
            _event_response_from_row(row)
            for row in await repo.list_alert_events(alert_identity=alert_identity, limit=limit)
        ]
        return AdminAlertHistoryListResponse(items=items)
    except _MONITORING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list admin alert history: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list alert history") from exc
