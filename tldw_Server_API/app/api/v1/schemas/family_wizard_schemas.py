"""
Pydantic schemas for Family Guardrails Wizard draft lifecycle APIs.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


WizardHouseholdMode = Literal["family", "institutional"]
WizardRelationshipType = Literal["parent", "legal_guardian", "institutional"]
WizardMemberRole = Literal["guardian", "dependent", "caregiver"]
WizardAccountMode = Literal["existing_account", "invite_new"]
WizardProvisioningStatus = Literal[
    "not_started",
    "invite_ready",
    "sent",
    "accepted",
    "expired",
    "failed",
]
WizardActivationStatus = Literal[
    "draft",
    "invites_pending",
    "partially_active",
    "active",
    "needs_attention",
]
WizardPlanStatus = Literal["queued", "active", "failed"]
WizardRelationshipDraftStatus = Literal[
    "pending",
    "pending_provisioning",
    "active",
    "declined",
    "revoked",
]
WizardInviteStatus = Literal[
    "not_started",
    "ready",
    "sent",
    "accepted",
    "expired",
    "revoked",
    "failed",
]


class HouseholdDraftCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    mode: WizardHouseholdMode = "family"


class HouseholdDraftUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    mode: WizardHouseholdMode | None = None
    status: WizardActivationStatus | None = None


class HouseholdDraftResponse(BaseModel):
    id: str
    owner_user_id: str
    name: str
    mode: WizardHouseholdMode
    status: WizardActivationStatus
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


class HouseholdDraftSnapshotResponse(BaseModel):
    household: HouseholdDraftResponse
    members: list["HouseholdMemberDraftResponse"] = Field(default_factory=list)
    relationships: list["RelationshipDraftResponse"] = Field(default_factory=list)
    plans: list["GuardrailPlanDraftResponse"] = Field(default_factory=list)


class HouseholdMemberDraftCreate(BaseModel):
    role: WizardMemberRole
    display_name: str = Field(..., min_length=1, max_length=120)
    user_id: str | None = None
    email: str | None = None
    invite_required: bool = True
    account_mode: WizardAccountMode = "existing_account"
    provisioning_status: WizardProvisioningStatus = "not_started"
    metadata: dict[str, Any] = Field(default_factory=dict)


class HouseholdMemberDraftResponse(BaseModel):
    id: str
    household_draft_id: str
    role: WizardMemberRole
    display_name: str
    user_id: str | None = None
    email: str | None = None
    invite_required: bool
    account_mode: WizardAccountMode = "existing_account"
    provisioning_status: WizardProvisioningStatus = "not_started"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


class RelationshipDraftCreate(BaseModel):
    guardian_member_draft_id: str = Field(..., min_length=1)
    dependent_member_draft_id: str = Field(..., min_length=1)
    relationship_type: WizardRelationshipType = "parent"
    dependent_visible: bool = True


class RelationshipDraftResponse(BaseModel):
    id: str
    household_draft_id: str
    guardian_member_draft_id: str
    dependent_member_draft_id: str
    relationship_type: WizardRelationshipType
    dependent_visible: bool
    status: WizardRelationshipDraftStatus
    relationship_id: str | None = None
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


class GuardrailPlanDraftCreate(BaseModel):
    dependent_member_draft_id: str | None = Field(None, min_length=1)
    dependent_user_id: str | None = Field(None, min_length=1)
    relationship_draft_id: str = Field(..., min_length=1)
    template_id: str = Field(..., min_length=1)
    overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dependent_reference(self) -> "GuardrailPlanDraftCreate":
        if not self.dependent_member_draft_id and not self.dependent_user_id:
            raise ValueError("Either dependent_member_draft_id or dependent_user_id is required")
        return self


class GuardrailPlanDraftResponse(BaseModel):
    id: str
    household_draft_id: str
    dependent_member_draft_id: str
    dependent_user_id: str | None = None
    relationship_draft_id: str
    template_id: str
    overrides: dict[str, Any] = Field(default_factory=dict)
    status: WizardPlanStatus
    materialized_policy_id: str | None = None
    failure_reason: str | None = None
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


class ActivationSummaryItem(BaseModel):
    dependent_member_draft_id: str
    dependent_user_id: str | None = None
    relationship_status: WizardRelationshipDraftStatus
    plan_status: WizardPlanStatus
    message: str | None = None


class ActivationSummaryResponse(BaseModel):
    household_draft_id: str
    status: WizardActivationStatus
    active_count: int = Field(..., ge=0)
    pending_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    items: list[ActivationSummaryItem] = Field(default_factory=list)


class ResendPendingInvitesRequest(BaseModel):
    dependent_user_ids: list[str] = Field(default_factory=list)
    member_draft_ids: list[str] = Field(default_factory=list)


class ResendPendingInvitesResponse(BaseModel):
    household_draft_id: str
    resent_count: int = Field(..., ge=0)
    skipped_count: int = Field(..., ge=0)
    resent_user_ids: list[str] = Field(default_factory=list)
    skipped_user_ids: list[str] = Field(default_factory=list)
    resent_member_draft_ids: list[str] = Field(default_factory=list)
    skipped_member_draft_ids: list[str] = Field(default_factory=list)


class HouseholdMemberInviteResponse(BaseModel):
    id: str
    household_draft_id: str
    member_draft_id: str
    status: WizardInviteStatus
    delivery_channel: str
    delivery_target: str | None = None
    invite_token: str
    resend_count: int = Field(..., ge=0)
    last_sent_at: str | None = None
    accepted_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    failure_reason: str | None = None
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


class HouseholdInviteTrackerItemResponse(BaseModel):
    member_draft_id: str
    display_name: str
    account_mode: WizardAccountMode
    dependent_user_id: str | None = None
    relationship_draft_id: str | None = None
    relationship_status: WizardRelationshipDraftStatus | None = None
    plan_draft_id: str | None = None
    plan_status: WizardPlanStatus | None = None
    invite_id: str | None = None
    invite_status: WizardInviteStatus = "not_started"
    invite_delivery_channel: str | None = None
    invite_delivery_target: str | None = None
    invite_last_sent_at: str | None = None
    invite_accepted_at: str | None = None
    invite_expires_at: str | None = None
    blocker_codes: list[str] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)


class HouseholdInviteTrackerResponse(BaseModel):
    household_draft_id: str
    active_count: int = Field(..., ge=0)
    pending_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    items: list[HouseholdInviteTrackerItemResponse] = Field(default_factory=list)
