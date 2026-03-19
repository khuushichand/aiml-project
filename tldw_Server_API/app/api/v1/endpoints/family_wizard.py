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
    HouseholdDraftSnapshotResponse,
    HouseholdDraftResponse,
    HouseholdDraftUpdate,
    HouseholdInviteTrackerItemResponse,
    HouseholdInviteTrackerResponse,
    HouseholdMemberDraftCreate,
    HouseholdMemberInviteResponse,
    HouseholdMemberDraftResponse,
    ResendPendingInvitesRequest,
    ResendPendingInvitesResponse,
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
        account_mode=row.get("account_mode", "existing_account"),
        provisioning_status=row.get("provisioning_status", "not_started"),
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
        dependent_member_draft_id=row["dependent_member_draft_id"],
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


def _invite_from_row(row: dict) -> HouseholdMemberInviteResponse:
    return HouseholdMemberInviteResponse(
        id=row["id"],
        household_draft_id=row["household_draft_id"],
        member_draft_id=row["member_draft_id"],
        status=row["status"],
        delivery_channel=row["delivery_channel"],
        delivery_target=row.get("delivery_target"),
        invite_token=row["invite_token"],
        resend_count=row["resend_count"],
        last_sent_at=row.get("last_sent_at"),
        accepted_at=row.get("accepted_at"),
        expires_at=row.get("expires_at"),
        revoked_at=row.get("revoked_at"),
        failure_reason=row.get("failure_reason"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _tracker_item_from_rows(
    member: dict,
    relationship: dict | None,
    plan: dict | None,
    invite: dict | None,
) -> HouseholdInviteTrackerItemResponse:
    invite_status = invite["status"] if invite else "not_started"
    blocker_codes: list[str] = []
    available_actions: list[str] = []

    if member.get("invite_required", True):
        if not invite:
            blocker_codes.append("invite_not_provisioned")
            available_actions.append("provision_invite")
        elif invite_status == "expired":
            blocker_codes.append("invite_expired")
            available_actions.append("reissue_invite")
        elif invite_status in ("ready", "sent"):
            blocker_codes.append("invite_pending_acceptance")
            available_actions.append("resend_invite")
        elif invite_status == "failed":
            blocker_codes.append("invite_failed")
            available_actions.append("reissue_invite")

    if relationship and relationship["status"] == "pending_provisioning":
        blocker_codes.append("account_not_accepted")
    if plan and plan["status"] == "queued":
        blocker_codes.append("plan_waiting_for_acceptance")

    return HouseholdInviteTrackerItemResponse(
        member_draft_id=member["id"],
        display_name=member["display_name"],
        account_mode=member.get("account_mode", "existing_account"),
        dependent_user_id=member.get("user_id"),
        relationship_draft_id=relationship["id"] if relationship else None,
        relationship_status=relationship["status"] if relationship else None,
        plan_draft_id=plan["id"] if plan else None,
        plan_status=plan["status"] if plan else None,
        invite_id=invite["id"] if invite else None,
        invite_status=invite_status,
        invite_delivery_channel=invite.get("delivery_channel") if invite else None,
        invite_delivery_target=invite.get("delivery_target") if invite else None,
        invite_last_sent_at=invite.get("last_sent_at") if invite else None,
        invite_accepted_at=invite.get("accepted_at") if invite else None,
        invite_expires_at=invite.get("expires_at") if invite else None,
        blocker_codes=blocker_codes,
        available_actions=available_actions,
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
    """Create a new household wizard draft owned by the authenticated guardian."""
    draft_id = db.create_household_draft(
        owner_user_id=_user_id(user),
        mode=body.mode,
        name=body.name,
    )
    draft = db.get_household_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=500, detail="Failed to create household draft")
    return _household_from_row(draft)


@router.get("/wizard/drafts", response_model=list[HouseholdDraftResponse])
def list_household_drafts(
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """List owned household wizard drafts ordered by most recently updated."""
    drafts = db.list_household_drafts(_user_id(user))
    return [_household_from_row(row) for row in drafts]


@router.get("/wizard/drafts/latest", response_model=HouseholdDraftResponse)
def get_latest_household_draft(
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Return the authenticated guardian's most recently updated wizard draft."""
    draft = db.get_latest_household_draft(_user_id(user))
    if not draft:
        raise HTTPException(status_code=404, detail="No household draft found")
    return _household_from_row(draft)


@router.get("/wizard/drafts/{draft_id}", response_model=HouseholdDraftResponse)
def get_household_draft(
    draft_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Return one owned household wizard draft."""
    draft = _require_owned_draft(db, draft_id, _user_id(user))
    return _household_from_row(draft)


@router.patch("/wizard/drafts/{draft_id}", response_model=HouseholdDraftResponse)
def update_household_draft(
    draft_id: str,
    body: HouseholdDraftUpdate,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Update mutable fields on an owned household wizard draft."""
    _require_owned_draft(db, draft_id, _user_id(user))
    updates = body.model_dump(exclude_unset=True)
    if updates:
        db.update_household_draft(draft_id, **updates)
    draft = db.get_household_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Household draft not found")
    return _household_from_row(draft)


@router.get(
    "/wizard/drafts/{draft_id}/snapshot",
    response_model=HouseholdDraftSnapshotResponse,
)
def get_household_draft_snapshot(
    draft_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Return full wizard snapshot (household, members, relationships, plans)."""
    draft = _require_owned_draft(db, draft_id, _user_id(user))
    members = db.list_household_member_drafts(draft_id)
    relationships = db.list_relationship_drafts(draft_id)
    plans = db.list_guardrail_plan_drafts(draft_id)
    return HouseholdDraftSnapshotResponse(
        household=_household_from_row(draft),
        members=[_member_from_row(row) for row in members],
        relationships=[_relationship_from_row(row) for row in relationships],
        plans=[_plan_from_row(row) for row in plans],
    )


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
    """Create a guardian/dependent member draft under an owned household draft."""
    _require_owned_draft(db, draft_id, _user_id(user))
    member_id = db.add_household_member_draft(
        household_draft_id=draft_id,
        role=body.role,
        display_name=body.display_name,
        user_id=body.user_id,
        email=body.email,
        invite_required=body.invite_required,
        account_mode=body.account_mode,
        provisioning_status=body.provisioning_status,
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
    """Delete one member draft from an owned household draft."""
    _require_owned_draft(db, draft_id, _user_id(user))
    member = db.get_household_member_draft(member_id)
    if not member or member["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Member draft not found")
    db.remove_household_member_draft(member_id)
    return DetailResponse(detail="Member draft removed")


@router.post(
    "/wizard/drafts/{draft_id}/members/{member_id}/invite/provision",
    response_model=HouseholdMemberInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def provision_household_member_invite(
    draft_id: str,
    member_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Provision or return the current invite for one dependent member draft."""
    _require_owned_draft(db, draft_id, _user_id(user))
    member = db.get_household_member_draft(member_id)
    if not member or member["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Member draft not found")
    if member["role"] != "dependent":
        raise HTTPException(status_code=400, detail="Invite provisioning requires a dependent member draft")
    if not member.get("invite_required", True):
        raise HTTPException(status_code=400, detail="Member draft does not require an invite")

    latest_invite = db.get_latest_household_member_invite_for_member(member_id)
    if latest_invite and latest_invite["status"] in ("ready", "sent"):
        return _invite_from_row(latest_invite)

    invite_id = db.create_household_member_invite(
        household_draft_id=draft_id,
        member_draft_id=member_id,
        delivery_channel="email" if member.get("email") else "guardian_copy",
        delivery_target=member.get("email"),
        status="ready",
    )
    invite = db.get_household_member_invite(invite_id)
    if not invite:
        raise HTTPException(status_code=500, detail="Failed to provision invite")
    return _invite_from_row(invite)


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
    """Persist one dependent mapping and create its runtime relationship."""
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
    authenticated_user_id = _user_id(user)
    if guardian_member["user_id"] != authenticated_user_id:
        raise HTTPException(
            status_code=403,
            detail="Relationship mapping guardian member must match the authenticated guardian account",
        )

    try:
        dependent_user_id = (dependent_member.get("user_id") or "").strip()
        if dependent_user_id:
            relationship = db.create_relationship(
                guardian_user_id=authenticated_user_id,
                dependent_user_id=dependent_user_id,
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
        else:
            relationship_draft_id = db.create_relationship_draft(
                household_draft_id=draft_id,
                guardian_member_draft_id=body.guardian_member_draft_id,
                dependent_member_draft_id=body.dependent_member_draft_id,
                relationship_type=body.relationship_type,
                dependent_visible=body.dependent_visible,
                status="pending_provisioning",
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
    """Queue one guardrail plan draft bound to an owned relationship draft."""
    _require_owned_draft(db, draft_id, _user_id(user))
    relationship_draft = db.get_relationship_draft(body.relationship_draft_id)
    if not relationship_draft or relationship_draft["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Relationship draft not found")
    dependent_member = db.get_household_member_draft(relationship_draft["dependent_member_draft_id"])
    if not dependent_member or dependent_member["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Dependent member draft not found")
    dependent_member_draft_id = relationship_draft["dependent_member_draft_id"]
    requested_member_draft_id = (body.dependent_member_draft_id or "").strip()
    if requested_member_draft_id and requested_member_draft_id != dependent_member_draft_id:
        raise HTTPException(
            status_code=400,
            detail="Plan dependent_member_draft_id must match the dependent member on the relationship draft",
        )
    dependent_user_id = (dependent_member.get("user_id") or "").strip() or None
    requested_dependent_user_id = (body.dependent_user_id or "").strip()
    if requested_dependent_user_id and dependent_user_id and requested_dependent_user_id != dependent_user_id:
        raise HTTPException(
            status_code=400,
            detail="Plan dependent_user_id must match the dependent user_id on the relationship draft",
        )

    plan_id = db.create_guardrail_plan_draft(
        household_draft_id=draft_id,
        relationship_draft_id=body.relationship_draft_id,
        dependent_member_draft_id=dependent_member_draft_id,
        dependent_user_id=dependent_user_id,
        template_id=body.template_id,
        overrides=body.overrides,
    )
    plan = db.get_guardrail_plan_draft(plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="Failed to save guardrail plan")
    return _plan_from_row(plan)


@router.get(
    "/wizard/drafts/{draft_id}/tracker",
    response_model=HouseholdInviteTrackerResponse,
)
def get_household_invite_tracker(
    draft_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Return row-level invite, relationship, and plan state for one household draft."""
    _require_owned_draft(db, draft_id, _user_id(user))
    dependent_members = [
        member
        for member in db.list_household_member_drafts(draft_id)
        if member["role"] == "dependent"
    ]
    relationships_by_member = {
        relationship["dependent_member_draft_id"]: relationship
        for relationship in db.list_relationship_drafts(draft_id)
    }
    plans_by_member = {
        plan["dependent_member_draft_id"]: plan
        for plan in db.list_guardrail_plan_drafts(draft_id)
    }
    invites_by_member = {}
    for invite in db.list_household_member_invites(draft_id):
        invites_by_member.setdefault(invite["member_draft_id"], invite)

    items = [
        _tracker_item_from_rows(
            member,
            relationships_by_member.get(member["id"]),
            plans_by_member.get(member["id"]),
            invites_by_member.get(member["id"]),
        )
        for member in dependent_members
    ]
    active_count = sum(1 for item in items if item.plan_status == "active")
    failed_count = sum(
        1
        for item in items
        if item.plan_status == "failed" or item.invite_status == "failed"
    )
    pending_count = sum(1 for item in items if item.blocker_codes or item.plan_status == "queued")

    return HouseholdInviteTrackerResponse(
        household_draft_id=draft_id,
        active_count=active_count,
        pending_count=pending_count,
        failed_count=failed_count,
        items=items,
    )


@router.get(
    "/wizard/drafts/{draft_id}/activation-summary",
    response_model=ActivationSummaryResponse,
)
def get_activation_summary(
    draft_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Summarize activation readiness/status for each planned dependent setup."""
    draft = _require_owned_draft(db, draft_id, _user_id(user))
    plans = db.list_guardrail_plan_drafts(draft_id)
    relationship_status_by_id = {
        relationship["id"]: relationship["status"]
        for relationship in db.list_relationship_drafts(draft_id)
    }
    active_count = sum(1 for plan in plans if plan["status"] == "active")
    pending_count = sum(1 for plan in plans if plan["status"] == "queued")
    failed_count = sum(1 for plan in plans if plan["status"] == "failed")

    items: list[ActivationSummaryItem] = []
    for plan in plans:
        relationship_status = relationship_status_by_id.get(plan["relationship_draft_id"], "pending")
        message = "Queued until acceptance" if plan["status"] == "queued" else None
        items.append(
            ActivationSummaryItem(
                dependent_member_draft_id=plan["dependent_member_draft_id"],
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


@router.post(
    "/wizard/drafts/{draft_id}/invites/{invite_id}/resend",
    response_model=HouseholdMemberInviteResponse,
)
def resend_household_member_invite(
    draft_id: str,
    invite_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Resend one existing household member invite."""
    _require_owned_draft(db, draft_id, _user_id(user))
    invite = db.get_household_member_invite(invite_id)
    if not invite or invite["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite["status"] in ("accepted", "revoked"):
        raise HTTPException(status_code=409, detail="Invite cannot be resent in its current state")
    touched = db.update_household_member_invite_status(
        invite_id,
        status="sent",
        increment_resend_count=True,
    )
    if not touched:
        raise HTTPException(status_code=500, detail="Failed to resend invite")
    invite = db.get_household_member_invite(invite_id)
    if not invite:
        raise HTTPException(status_code=500, detail="Invite not found after resend")
    return _invite_from_row(invite)


@router.post(
    "/wizard/drafts/{draft_id}/invites/{invite_id}/reissue",
    response_model=HouseholdMemberInviteResponse,
)
def reissue_household_member_invite(
    draft_id: str,
    invite_id: str,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Rotate an expired or invalid invite and return the replacement invite."""
    _require_owned_draft(db, draft_id, _user_id(user))
    invite = db.get_household_member_invite(invite_id)
    if not invite or invite["household_draft_id"] != draft_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    try:
        replacement_id = db.reissue_household_member_invite(invite_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    replacement = db.get_household_member_invite(replacement_id)
    if not replacement:
        raise HTTPException(status_code=500, detail="Failed to reissue invite")
    return _invite_from_row(replacement)


@router.post(
    "/wizard/drafts/{draft_id}/invites/resend",
    response_model=ResendPendingInvitesResponse,
)
def resend_pending_invites(
    draft_id: str,
    body: ResendPendingInvitesRequest,
    user: User = Depends(get_request_user),
    db: GuardianDB = Depends(get_guardian_db_for_user),
):
    """Resend invite reminders for pending dependent setups in a household draft."""
    _require_owned_draft(db, draft_id, _user_id(user))

    requested_member_ids: list[str] = []
    seen_member_ids: set[str] = set()
    for raw_member_id in body.member_draft_ids:
        member_id = raw_member_id.strip()
        if not member_id or member_id in seen_member_ids:
            continue
        seen_member_ids.add(member_id)
        requested_member_ids.append(member_id)

    requested_user_ids: list[str] = []
    seen_user_ids: set[str] = set()
    for raw_user_id in body.dependent_user_ids:
        user_id = raw_user_id.strip()
        if not user_id or user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        requested_user_ids.append(user_id)

    if not requested_member_ids and not requested_user_ids:
        return ResendPendingInvitesResponse(
            household_draft_id=draft_id,
            resent_count=0,
            skipped_count=0,
            resent_user_ids=[],
            skipped_user_ids=[],
            resent_member_draft_ids=[],
            skipped_member_draft_ids=[],
        )

    members = db.list_household_member_drafts(draft_id)
    member_by_id = {member["id"]: member for member in members if member["role"] == "dependent"}
    member_by_dependent_user_id = {
        member["user_id"]: member
        for member in members
        if member["role"] == "dependent" and member.get("user_id")
    }

    resent_user_ids: list[str] = []
    skipped_user_ids: list[str] = []
    resent_member_draft_ids: list[str] = []
    skipped_member_draft_ids: list[str] = []

    for dependent_user_id in requested_user_ids:
        member = member_by_dependent_user_id.get(dependent_user_id)
        if not member:
            skipped_user_ids.append(dependent_user_id)
            continue
        if not member.get("invite_required", True):
            skipped_user_ids.append(dependent_user_id)
            continue
        latest_invite = db.get_latest_household_member_invite_for_member(member["id"])
        if not latest_invite:
            invite_id = db.create_household_member_invite(
                household_draft_id=draft_id,
                member_draft_id=member["id"],
                delivery_channel="email" if member.get("email") else "guardian_copy",
                delivery_target=member.get("email"),
                status="ready",
            )
            latest_invite = db.get_household_member_invite(invite_id)
        if not latest_invite or latest_invite["status"] in ("accepted", "revoked", "expired"):
            skipped_user_ids.append(dependent_user_id)
            continue
        touched = db.update_household_member_invite_status(
            latest_invite["id"],
            status="sent",
            increment_resend_count=True,
        )
        if not touched:
            skipped_user_ids.append(dependent_user_id)
            continue
        resent_user_ids.append(dependent_user_id)
        resent_member_draft_ids.append(member["id"])

    for member_id in requested_member_ids:
        member = member_by_id.get(member_id)
        if not member:
            skipped_member_draft_ids.append(member_id)
            continue
        if not member.get("invite_required", True):
            skipped_member_draft_ids.append(member_id)
            continue
        latest_invite = db.get_latest_household_member_invite_for_member(member_id)
        if not latest_invite:
            invite_id = db.create_household_member_invite(
                household_draft_id=draft_id,
                member_draft_id=member_id,
                delivery_channel="email" if member.get("email") else "guardian_copy",
                delivery_target=member.get("email"),
                status="ready",
            )
            latest_invite = db.get_household_member_invite(invite_id)
        if not latest_invite or latest_invite["status"] in ("accepted", "revoked", "expired"):
            skipped_member_draft_ids.append(member_id)
            continue
        touched = db.update_household_member_invite_status(
            latest_invite["id"],
            status="sent",
            increment_resend_count=True,
        )
        if not touched:
            skipped_member_draft_ids.append(member_id)
            continue
        resent_member_draft_ids.append(member_id)
        if member.get("user_id"):
            resent_user_ids.append(member["user_id"])

    if resent_user_ids or resent_member_draft_ids:
        db.update_household_draft(draft_id, status="invites_pending")

    resent_user_ids = list(dict.fromkeys(resent_user_ids))
    resent_member_draft_ids = list(dict.fromkeys(resent_member_draft_ids))
    return ResendPendingInvitesResponse(
        household_draft_id=draft_id,
        resent_count=len(resent_member_draft_ids) or len(resent_user_ids),
        skipped_count=len(skipped_user_ids) + len(skipped_member_draft_ids),
        resent_user_ids=resent_user_ids,
        skipped_user_ids=skipped_user_ids,
        resent_member_draft_ids=resent_member_draft_ids,
        skipped_member_draft_ids=skipped_member_draft_ids,
    )
