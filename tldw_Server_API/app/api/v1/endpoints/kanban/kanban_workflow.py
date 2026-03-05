# app/api/v1/endpoints/kanban/kanban_workflow.py
"""Kanban workflow-control API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tldw_Server_API.app.api.v1.API_Deps.kanban_deps import (
    get_kanban_db_for_user,
    kanban_rate_limit,
)
from tldw_Server_API.app.api.v1.schemas.kanban_schemas import (
    WorkflowApprovalDecisionRequest,
    WorkflowClaimRequest,
    WorkflowControlResponse,
    WorkflowEventsListResponse,
    WorkflowForceReassignRequest,
    WorkflowPolicyUpsertRequest,
    WorkflowReleaseRequest,
    WorkflowStaleClaimsListResponse,
    WorkflowStatePatchRequest,
    WorkflowStateResponse,
    WorkflowTransitionRequest,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Kanban_DB import (
    ConflictError,
    InputError,
    KanbanDB,
    KanbanDBError,
    NotFoundError,
)

router = APIRouter(tags=["Kanban Workflow"])

_KNOWN_WORKFLOW_ERROR_CODES = {
    "version_conflict",
    "lease_required",
    "lease_mismatch",
    "policy_paused",
    "transition_not_allowed",
    "approval_required",
    "projection_failed",
    "idempotency_conflict",
}


def _extract_workflow_error_code(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return "workflow_error"
    code = message.split("(", 1)[0].strip().split(" ", 1)[0].strip()
    if code in _KNOWN_WORKFLOW_ERROR_CODES:
        return code
    return "workflow_error"


def _workflow_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": str(exc)},
        )
    if isinstance(exc, InputError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_request", "message": str(exc)},
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": _extract_workflow_error_code(exc), "message": str(exc)},
        )
    if isinstance(exc, KanbanDBError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "kanban_db_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "internal_error", "message": "An unexpected error occurred"},
    )


def _require_admin(current_user: User) -> None:
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Admin privileges required"},
        )


@router.get(
    "/workflow/boards/{board_id}/policy",
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.policy.get"))],
)
async def get_workflow_policy(
    board_id: int,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> dict[str, Any]:
    try:
        policy = db.get_workflow_policy(board_id)
        if policy is None:
            raise NotFoundError("Workflow policy not found", entity="workflow_policy", entity_id=board_id)  # noqa: TRY003
        return policy
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.put(
    "/workflow/boards/{board_id}/policy",
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.policy.upsert"))],
)
async def upsert_workflow_policy(
    board_id: int,
    policy_in: WorkflowPolicyUpsertRequest,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> dict[str, Any]:
    try:
        return db.upsert_workflow_policy(
            board_id=board_id,
            statuses=[status.model_dump() for status in policy_in.statuses] if policy_in.statuses is not None else None,
            transitions=[transition.model_dump() for transition in policy_in.transitions] if policy_in.transitions is not None else None,
            is_paused=policy_in.is_paused,
            is_draining=policy_in.is_draining,
            default_lease_ttl_sec=policy_in.default_lease_ttl_sec,
            strict_projection=policy_in.strict_projection,
            metadata=policy_in.metadata,
        )
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.get(
    "/workflow/boards/{board_id}/statuses",
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.statuses.list"))],
)
async def list_workflow_statuses(
    board_id: int,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> dict[str, Any]:
    try:
        return {"statuses": db.list_workflow_statuses(board_id)}
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.get(
    "/workflow/boards/{board_id}/transitions",
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.transitions.list"))],
)
async def list_workflow_transitions(
    board_id: int,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> dict[str, Any]:
    try:
        return {"transitions": db.list_workflow_transitions(board_id)}
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.get(
    "/workflow/cards/{card_id}/state",
    response_model=WorkflowStateResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.task.state.get"))],
)
async def get_card_workflow_state(
    card_id: int,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStateResponse:
    try:
        return WorkflowStateResponse(**db.get_card_workflow_state(card_id))
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.patch(
    "/workflow/cards/{card_id}/state",
    response_model=WorkflowStateResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.task.state.patch"))],
)
async def patch_card_workflow_state(
    card_id: int,
    state_in: WorkflowStatePatchRequest,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStateResponse:
    try:
        state = db.patch_card_workflow_state(
            card_id=card_id,
            workflow_status_key=state_in.workflow_status_key,
            expected_version=state_in.expected_version,
            lease_owner=state_in.lease_owner,
            idempotency_key=state_in.idempotency_key,
            correlation_id=state_in.correlation_id,
            last_actor=state_in.actor,
        )
        return WorkflowStateResponse(**state)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/cards/{card_id}/claim",
    response_model=WorkflowStateResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.task.claim"))],
)
async def claim_card_workflow(
    card_id: int,
    claim_in: WorkflowClaimRequest,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStateResponse:
    try:
        state = db.claim_card_workflow(
            card_id=card_id,
            owner=claim_in.owner,
            lease_ttl_sec=claim_in.lease_ttl_sec,
            idempotency_key=claim_in.idempotency_key,
            correlation_id=claim_in.correlation_id,
        )
        return WorkflowStateResponse(**state)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/cards/{card_id}/release",
    response_model=WorkflowStateResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.task.release"))],
)
async def release_card_workflow(
    card_id: int,
    release_in: WorkflowReleaseRequest,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStateResponse:
    try:
        state = db.release_card_workflow(
            card_id=card_id,
            owner=release_in.owner,
            idempotency_key=release_in.idempotency_key,
            correlation_id=release_in.correlation_id,
        )
        return WorkflowStateResponse(**state)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/cards/{card_id}/transition",
    response_model=WorkflowStateResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.task.transition"))],
)
async def transition_card_workflow(
    card_id: int,
    transition_in: WorkflowTransitionRequest,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStateResponse:
    try:
        state = db.transition_card_workflow(
            card_id=card_id,
            to_status_key=transition_in.to_status_key,
            actor=transition_in.actor,
            expected_version=transition_in.expected_version,
            idempotency_key=transition_in.idempotency_key,
            correlation_id=transition_in.correlation_id,
            reason=transition_in.reason,
        )
        return WorkflowStateResponse(**state)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/cards/{card_id}/approval",
    response_model=WorkflowStateResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.task.approval.decide"))],
)
async def decide_card_workflow_approval(
    card_id: int,
    approval_in: WorkflowApprovalDecisionRequest,
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStateResponse:
    try:
        state = db.decide_card_workflow_approval(
            card_id=card_id,
            reviewer=approval_in.reviewer,
            decision=approval_in.decision,
            expected_version=approval_in.expected_version,
            idempotency_key=approval_in.idempotency_key,
            correlation_id=approval_in.correlation_id,
            reason=approval_in.reason,
        )
        return WorkflowStateResponse(**state)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.get(
    "/workflow/cards/{card_id}/events",
    response_model=WorkflowEventsListResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.task.events.list"))],
)
async def list_card_workflow_events(
    card_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowEventsListResponse:
    try:
        return WorkflowEventsListResponse(events=db.list_card_workflow_events(card_id=card_id, limit=limit, offset=offset))
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.get(
    "/workflow/recovery/stale-claims",
    response_model=WorkflowStaleClaimsListResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.recovery.list_stale_claims"))],
)
async def list_stale_workflow_claims(
    board_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStaleClaimsListResponse:
    try:
        claims = db.list_stale_workflow_claims(board_id=board_id, limit=limit)
        return WorkflowStaleClaimsListResponse(stale_claims=claims)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/recovery/cards/{card_id}/force-reassign",
    response_model=WorkflowStateResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.recovery.force_reassign"))],
)
async def force_reassign_workflow_claim(
    card_id: int,
    request_in: WorkflowForceReassignRequest,
    current_user: User = Depends(get_request_user),
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowStateResponse:
    _require_admin(current_user)
    try:
        state = db.force_reassign_workflow_claim(
            card_id=card_id,
            new_owner=request_in.new_owner,
            idempotency_key=request_in.idempotency_key,
            correlation_id=request_in.correlation_id,
            reason=request_in.reason,
        )
        return WorkflowStateResponse(**state)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/control/boards/{board_id}/pause",
    response_model=WorkflowControlResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.control.pause"))],
)
async def pause_workflow_policy(
    board_id: int,
    current_user: User = Depends(get_request_user),
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowControlResponse:
    _require_admin(current_user)
    try:
        policy = db.get_workflow_policy(board_id)
        if not policy:
            raise NotFoundError("Workflow policy not found", entity="workflow_policy", entity_id=board_id)  # noqa: TRY003
        updated = db.upsert_workflow_policy(
            board_id=board_id,
            statuses=policy.get("statuses"),
            transitions=policy.get("transitions"),
            is_paused=True,
            is_draining=bool(policy.get("is_draining", False)),
            default_lease_ttl_sec=int(policy.get("default_lease_ttl_sec", 900)),
            strict_projection=bool(policy.get("strict_projection", True)),
            metadata=policy.get("metadata"),
        )
        return WorkflowControlResponse(success=True, policy=updated)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/control/boards/{board_id}/resume",
    response_model=WorkflowControlResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.control.resume"))],
)
async def resume_workflow_policy(
    board_id: int,
    current_user: User = Depends(get_request_user),
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowControlResponse:
    _require_admin(current_user)
    try:
        policy = db.get_workflow_policy(board_id)
        if not policy:
            raise NotFoundError("Workflow policy not found", entity="workflow_policy", entity_id=board_id)  # noqa: TRY003
        updated = db.upsert_workflow_policy(
            board_id=board_id,
            statuses=policy.get("statuses"),
            transitions=policy.get("transitions"),
            is_paused=False,
            is_draining=bool(policy.get("is_draining", False)),
            default_lease_ttl_sec=int(policy.get("default_lease_ttl_sec", 900)),
            strict_projection=bool(policy.get("strict_projection", True)),
            metadata=policy.get("metadata"),
        )
        return WorkflowControlResponse(success=True, policy=updated)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc


@router.post(
    "/workflow/control/boards/{board_id}/drain",
    response_model=WorkflowControlResponse,
    dependencies=[Depends(kanban_rate_limit("kanban.workflow.control.drain"))],
)
async def drain_workflow_policy(
    board_id: int,
    current_user: User = Depends(get_request_user),
    db: KanbanDB = Depends(get_kanban_db_for_user),
) -> WorkflowControlResponse:
    _require_admin(current_user)
    try:
        policy = db.get_workflow_policy(board_id)
        if not policy:
            raise NotFoundError("Workflow policy not found", entity="workflow_policy", entity_id=board_id)  # noqa: TRY003
        updated = db.upsert_workflow_policy(
            board_id=board_id,
            statuses=policy.get("statuses"),
            transitions=policy.get("transitions"),
            is_paused=bool(policy.get("is_paused", False)),
            is_draining=True,
            default_lease_ttl_sec=int(policy.get("default_lease_ttl_sec", 900)),
            strict_projection=bool(policy.get("strict_projection", True)),
            metadata=policy.get("metadata"),
        )
        return WorkflowControlResponse(success=True, policy=updated)
    except (NotFoundError, InputError, ConflictError, KanbanDBError) as exc:
        raise _workflow_http_error(exc) from exc
