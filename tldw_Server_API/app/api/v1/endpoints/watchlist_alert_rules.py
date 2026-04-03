"""
Watchlist Alert Rules API

CRUD endpoints for user-defined alert rules that trigger notifications
based on watchlist run statistics.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
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
    base_override = os.environ.get("TLDW_USER_DB_DIR") or None
    user_dir = DatabasePaths.get_user_base_directory(
        user_id,
        base_dir_override=base_override,
    )
    db_path = user_dir / DatabasePaths.CHACHA_DB_NAME
    ensure_alert_rules_table(str(db_path))
    return str(db_path)


def _user_id_text(current_user: User) -> str:
    raw = getattr(current_user, "id", None)
    if raw is None:
        raw = getattr(current_user, "id_int", None)
    return str(raw)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=AlertRuleListResponse)
async def list_rules(
    job_id: int | None = None,
    current_user: User = Depends(get_request_user),
):
    """List all alert rules for the current user, optionally filtered by job."""
    user_id = _user_id_text(current_user)
    db_path = _get_db_path(user_id)
    rules = list_alert_rules(db_path, user_id, job_id=job_id)
    return AlertRuleListResponse(
        items=[AlertRuleResponse(**vars(r)) for r in rules]
    )


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_rule(
    body: AlertRuleCreate,
    current_user: User = Depends(get_request_user),
):
    """Create a new alert rule."""
    valid_types = {"no_items", "error_rate_above", "items_below", "items_above", "run_failed"}
    if body.condition_type not in valid_types:
        raise HTTPException(400, f"Invalid condition_type. Must be one of: {', '.join(sorted(valid_types))}")
    user_id = _user_id_text(current_user)
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
    current_user: User = Depends(get_request_user),
):
    """Update an existing alert rule."""
    user_id = _user_id_text(current_user)
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
    current_user: User = Depends(get_request_user),
):
    """Delete an alert rule."""
    user_id = _user_id_text(current_user)
    db_path = _get_db_path(user_id)
    deleted = delete_alert_rule(db_path, rule_id, user_id)
    if not deleted:
        raise HTTPException(404, "Rule not found")
    return {"deleted": True}
