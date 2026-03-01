"""
Pydantic schemas for Family Guardrails Wizard draft lifecycle APIs.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


WizardHouseholdMode = Literal["family", "institutional"]
WizardRelationshipType = Literal["parent", "legal_guardian", "institutional"]
WizardMemberRole = Literal["guardian", "dependent", "caregiver"]
WizardActivationStatus = Literal[
    "draft",
    "invites_pending",
    "partially_active",
    "active",
    "needs_attention",
]
WizardPlanStatus = Literal["queued", "active", "failed"]


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


class HouseholdMemberDraftCreate(BaseModel):
    role: WizardMemberRole
    display_name: str = Field(..., min_length=1, max_length=120)
    user_id: str | None = None
    email: str | None = None
    invite_required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class HouseholdMemberDraftResponse(BaseModel):
    id: str
    household_draft_id: str
    role: WizardMemberRole
    display_name: str
    user_id: str | None = None
    email: str | None = None
    invite_required: bool
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
    status: Literal["pending", "active", "declined", "revoked"]
    relationship_id: str | None = None
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


class GuardrailPlanDraftCreate(BaseModel):
    dependent_user_id: str = Field(..., min_length=1)
    relationship_draft_id: str = Field(..., min_length=1)
    template_id: str = Field(..., min_length=1)
    overrides: dict[str, Any] = Field(default_factory=dict)


class GuardrailPlanDraftResponse(BaseModel):
    id: str
    household_draft_id: str
    dependent_user_id: str
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
    dependent_user_id: str
    relationship_status: Literal["pending", "active", "declined", "revoked"]
    plan_status: WizardPlanStatus
    message: str | None = None


class ActivationSummaryResponse(BaseModel):
    household_draft_id: str
    status: WizardActivationStatus
    active_count: int = Field(..., ge=0)
    pending_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    items: list[ActivationSummaryItem] = Field(default_factory=list)
