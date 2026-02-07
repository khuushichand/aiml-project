from __future__ import annotations

"""Helpers for emitting mandatory audit events for budget updates."""

from typing import Any

from fastapi import Request

from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
    get_or_create_audit_service_for_user_id_optional,
)
from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditContext,
    AuditEventCategory,
    AuditEventType,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _coerce_actor_id(actor_id_raw: Any | None) -> int | None:
    """Best-effort conversion of actor identifiers to int."""
    try:
        return int(actor_id_raw) if actor_id_raw is not None else None
    except (TypeError, ValueError):
        return None


async def emit_budget_audit_event(
    request: Request,
    principal: AuthPrincipal,
    *,
    org_id: int,
    budget_updates: dict[str, Any] | None,
    audit_changes: list[dict[str, Any]] | None,
    clear_budgets: bool,
    actor_role: str | None,
) -> None:
    """Emit a mandatory audit event for a budget update."""
    actor_id_raw = getattr(request.state, "user_id", None) or principal.user_id
    actor_id = _coerce_actor_id(actor_id_raw)
    svc = await get_or_create_audit_service_for_user_id_optional(actor_id)

    correlation_id = (
        request.headers.get("X-Correlation-ID") or getattr(request.state, "correlation_id", None)
    )
    request_id = (
        request.headers.get("X-Request-ID") or getattr(request.state, "request_id", None)
    )
    ctx_kwargs = {
        "user_id": str(actor_id) if actor_id is not None else None,
        "correlation_id": correlation_id,
        "ip_address": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent"),
        "endpoint": str(request.url.path),
        "method": request.method,
    }
    if request_id:
        ctx_kwargs["request_id"] = request_id
    ctx = AuditContext(**ctx_kwargs)

    await svc.log_event(
        event_type=AuditEventType.CONFIG_CHANGED,
        category=AuditEventCategory.SYSTEM,
        context=ctx,
        resource_type="org_budget",
        resource_id=str(org_id),
        action="budget.update",
        metadata={
            "org_id": org_id,
            "actor_id": actor_id,
            "resource_type": "org_budget",
            "resource_id": str(org_id),
            "correlation_id": correlation_id,
            "version": 1,
            "changes": audit_changes or [],
            "no_changes": len(audit_changes or []) == 0,
            "clear_budgets": clear_budgets,
            "updates": budget_updates or {},
            "actor_role": actor_role,
            "source_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "request_id": request_id,
        },
    )
    await svc.flush(raise_on_failure=True)
