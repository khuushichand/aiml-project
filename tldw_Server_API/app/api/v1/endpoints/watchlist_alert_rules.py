"""
Watchlist Alert Rules API

CRUD endpoints for user-defined alert rules that trigger notifications
based on watchlist run statistics.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_user_id
from tldw_Server_API.app.core.Watchlists.alert_rules import (
    create_alert_rule,
    delete_alert_rule,
    ensure_alert_rules_table,
    list_alert_rules,
    update_alert_rule,
)

router = APIRouter(prefix="/watchlists/alert-rules", tags=["watchlists"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AlertRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    condition_type: str  # no_items, error_rate_above, items_below, items_above, run_failed
    condition_value: dict[str, Any] | None = None
    job_id: int | None = None
    severity: str = "warning"


class AlertRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    enabled: bool | None = None
    condition_type: str | None = None
    condition_value: dict[str, Any] | None = None
    job_id: int | None = None
    severity: str | None = None


class AlertRuleResponse(BaseModel):
    id: int
    user_id: str
    job_id: int | None
    name: str
    enabled: bool
    condition_type: str
    condition_value: str
    severity: str
    created_at: str
    updated_at: str


class AlertRuleListResponse(BaseModel):
    items: list[AlertRuleResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_path(user_id: str) -> str:
    """Resolve the per-user ChaChaNotes DB path for alert rules storage."""
    import os
    base = os.environ.get("TLDW_USER_DB_DIR", "Databases/user_databases")
    user_dir = os.path.join(base, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    db_path = os.path.join(user_dir, "ChaChaNotes.db")
    ensure_alert_rules_table(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=AlertRuleListResponse)
async def list_rules(
    job_id: int | None = None,
    user_id: str = Depends(get_current_user_id),
):
    """List all alert rules for the current user, optionally filtered by job."""
    db_path = _get_db_path(user_id)
    rules = list_alert_rules(db_path, user_id, job_id=job_id)
    return AlertRuleListResponse(
        items=[AlertRuleResponse(**vars(r)) for r in rules]
    )


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_rule(
    body: AlertRuleCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new alert rule."""
    valid_types = {"no_items", "error_rate_above", "items_below", "items_above", "run_failed"}
    if body.condition_type not in valid_types:
        raise HTTPException(400, f"Invalid condition_type. Must be one of: {', '.join(sorted(valid_types))}")
    db_path = _get_db_path(user_id)
    rule = create_alert_rule(
        db_path,
        user_id=user_id,
        name=body.name,
        condition_type=body.condition_type,
        condition_value=body.condition_value,
        job_id=body.job_id,
        severity=body.severity,
    )
    return AlertRuleResponse(**vars(rule))


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: int,
    body: AlertRuleUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Update an existing alert rule."""
    db_path = _get_db_path(user_id)
    updated = update_alert_rule(db_path, rule_id, user_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, "Rule not found or no changes applied")
    rules = list_alert_rules(db_path, user_id)
    rule = next((r for r in rules if r.id == rule_id), None)
    if not rule:
        raise HTTPException(404, "Rule not found")
    return AlertRuleResponse(**vars(rule))


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    user_id: str = Depends(get_current_user_id),
):
    """Delete an alert rule."""
    db_path = _get_db_path(user_id)
    deleted = delete_alert_rule(db_path, rule_id, user_id)
    if not deleted:
        raise HTTPException(404, "Rule not found")
    return {"deleted": True}
