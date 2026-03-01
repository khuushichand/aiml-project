"""
Family Guardrails Wizard API endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from tldw_Server_API.app.api.v1.API_Deps.guardian_deps import get_guardian_db_for_user
from tldw_Server_API.app.api.v1.schemas.family_wizard_schemas import (
    ActivationSummaryItem,
    ActivationSummaryResponse,
    GuardrailPlanDraftCreate,
    GuardrailPlanDraftResponse,
    HouseholdDraftCreate,
    HouseholdDraftResponse,
    HouseholdDraftUpdate,
    HouseholdMemberDraftCreate,
    HouseholdMemberDraftResponse,
    RelationshipDraftCreate,
    RelationshipDraftResponse,
)
from tldw_Server_API.app.api.v1.schemas.guardian_schemas import DetailResponse
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB

router = APIRouter()


def _user_id(user: User) -> str:
    return str(user.id)


def _household_from_row(row: dict) -> HouseholdDraftResponse:
    return HouseholdDraftResponse(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        name=row["name"],
        mode=row["mode"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _member_from_row(row: dict) -> HouseholdMemberDraftResponse:
    return HouseholdMemberDraftResponse(
        id=row["id"],
        household_draft_id=row["household_draft_id"],
        role=row["role"],
        display_name=row["display_name"],
        user_id=row["user_id"],
        email=row["email"],
        invite_required=bool(row["invite_required"]),
        metadata=row.get("metadata") or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _relationship_from_row(row: dict) -> RelationshipDraftResponse:
    return RelationshipDraftResponse(
        id=row["id"],
        household_draft_id=row["household_draft_id"],
        guardian_member_draft_id=row["guardian_member_draft_id"],
        dependent_member_draft_id=row["dependent_member_draft_id"],
        relationship_type=row["relationship_type"],
        dependent_visible=bool(row["dependent_visible"]),
        status=row["status"],
        relationship_id=row.get("relationship_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _plan_from_row(row: dict) -> GuardrailPlanDraftResponse:
    return GuardrailPlanDraftResponse(
        id=row["id"],
        household_draft_id=row["household_draft_id"],
        dependent_user_id=row["dependent_user_id"],
        relationship_draft_id=row["relationship_draft_id"],
        template_id=row["template_id"],
        overrides=row.get("overrides") or {},
        status=row["status"],
        materialized_policy_id=row.get("materialized_policy_id"),
        failure_reason=row.get("failure_reason"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _require_owned_draft(db: GuardianDB, draft_id: str, user_id: str) -> dict:
    draft = db.get_household_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Household draft not found")
    if draft["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this household draft")
    return draft


@router.post(
    "/wizard/drafts",
    response_model=HouseholdDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_household_draft(
    body: HouseholdDraftCreate,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    draft_id = db.create_household_draft(
        owner_user_id=_user_id(user),
        mode=body.mode,
        name=body.name,
    )
    draft = db.get_household_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=500, detail="Failed to create household draft")
    return _household_from_row(draft)


@router.get("/wizard/drafts/{draft_id}", response_model=HouseholdDraftResponse)
def get_household_draft(
    draft_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    draft = _require_owned_draft(db, draft_id, _user_id(user))
    return _household_from_row(draft)


@router.patch("/wizard/drafts/{draft_id}", response_model=HouseholdDraftResponse)
def update_household_draft(
    draft_id: str,
    body: HouseholdDraftUpdate,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    _require_owned_draft(db, draft_id, _user_id(user))
    updates = body.model_dump(exclude_unset=True)
    if updates:
        db.update_household_draft(draft_id, **updates)
    draft = db.get_household_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Household draft not found")
    return _household_from_row(draft)


@router.post(
    "/wizard/drafts/{draft_id}/members",
    response_model=HouseholdMemberDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_household_member_draft(
    draft_id: str,
    body: HouseholdMemberDraftCreate,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    _require_owned_draft(db, draft_id, _user_id(user))
    member_id = db.add_household_member_draft(
        household_draft_id=draft_id,
        role=body.role,
        display_name=body.display_name,
        user_id=body.user_id,
        email=body.email,
        invite_required=body.invite_required,
        metadata=body.metadata,
    )
    member = db.get_household_member_draft(member_id)
    if not member:
        raise HTTPException(status_code=500, detail="Failed to create member draft")
    return _member_from_row(member)


@router.delete(
    "/wizard/drafts/{draft_id}/members/{member_id}",
    response_model=DetailResponse,
)
def remove_household_member_draft(
    draft_id: str,
    member_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    _require_owned_draft(db, draft_id, _user_id(user))
    member = db.get_household_member_draft(member_id)
    if not member or member["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Member draft not found")
    db.remove_household_member_draft(member_id)
    return DetailResponse(detail="Member draft removed")


@router.post(
    "/wizard/drafts/{draft_id}/relationships",
    response_model=RelationshipDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_relationship_mapping(
    draft_id: str,
    body: RelationshipDraftCreate,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    _require_owned_draft(db, draft_id, _user_id(user))
    guardian_member = db.get_household_member_draft(body.guardian_member_draft_id)
    dependent_member = db.get_household_member_draft(body.dependent_member_draft_id)

    if not guardian_member or guardian_member["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Guardian member draft not found")
    if not dependent_member or dependent_member["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Dependent member draft not found")
    if guardian_member["role"] != "guardian":
        raise HTTPException(status_code=400, detail="Guardian member draft must have guardian role")
    if dependent_member["role"] != "dependent":
        raise HTTPException(status_code=400, detail="Dependent member draft must have dependent role")
    if not guardian_member["user_id"] or not dependent_member["user_id"]:
        raise HTTPException(
            status_code=400,
            detail="Both guardian and dependent must have user_id before mapping",
        )

    try:
        relationship = db.create_relationship(
            guardian_user_id=guardian_member["user_id"],
            dependent_user_id=dependent_member["user_id"],
            relationship_type=body.relationship_type,
            dependent_visible=body.dependent_visible,
        )
        relationship_draft_id = db.create_relationship_draft(
            household_draft_id=draft_id,
            guardian_member_draft_id=body.guardian_member_draft_id,
            dependent_member_draft_id=body.dependent_member_draft_id,
            relationship_type=body.relationship_type,
            dependent_visible=body.dependent_visible,
        )
        db.link_relationship_draft(
            relationship_draft_id=relationship_draft_id,
            relationship_id=relationship.id,
            status=relationship.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    relationship_draft = db.get_relationship_draft(relationship_draft_id)
    if not relationship_draft:
        raise HTTPException(status_code=500, detail="Failed to save relationship mapping")
    return _relationship_from_row(relationship_draft)


@router.post(
    "/wizard/drafts/{draft_id}/plans",
    response_model=GuardrailPlanDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_guardrail_plan(
    draft_id: str,
    body: GuardrailPlanDraftCreate,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    _require_owned_draft(db, draft_id, _user_id(user))
    relationship_draft = db.get_relationship_draft(body.relationship_draft_id)
    if not relationship_draft or relationship_draft["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Relationship draft not found")

    plan_id = db.create_guardrail_plan_draft(
        household_draft_id=draft_id,
        dependent_user_id=body.dependent_user_id,
        relationship_draft_id=body.relationship_draft_id,
        template_id=body.template_id,
        overrides=body.overrides,
    )
    plan = db.get_guardrail_plan_draft(plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="Failed to save guardrail plan")
    return _plan_from_row(plan)


@router.get(
    "/wizard/drafts/{draft_id}/activation-summary",
    response_model=ActivationSummaryResponse,
)
def get_activation_summary(
    draft_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    draft = _require_owned_draft(db, draft_id, _user_id(user))
    plans = db.list_guardrail_plan_drafts(draft_id)
    active_count = sum(1 for plan in plans if plan["status"] == "active")
    pending_count = sum(1 for plan in plans if plan["status"] == "queued")
    failed_count = sum(1 for plan in plans if plan["status"] == "failed")

    items: list[ActivationSummaryItem] = []
    for plan in plans:
        relationship = db.get_relationship_draft(plan["relationship_draft_id"])
        relationship_status = (
            relationship["status"] if relationship else "pending"
        )
        message = "Queued until acceptance" if plan["status"] == "queued" else None
        items.append(
            ActivationSummaryItem(
                dependent_user_id=plan["dependent_user_id"],
                relationship_status=relationship_status,
                plan_status=plan["status"],
                message=message,
            )
        )

    return ActivationSummaryResponse(
        household_draft_id=draft_id,
        status=draft["status"],
        active_count=active_count,
        pending_count=pending_count,
        failed_count=failed_count,
        items=items,
    )
