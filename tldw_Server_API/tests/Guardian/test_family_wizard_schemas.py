from __future__ import annotations

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.family_wizard_schemas import (
    ActivationSummaryResponse,
    GuardrailPlanDraftCreate,
    HouseholdDraftCreate,
    HouseholdMemberDraftCreate,
)


def test_guardrail_plan_template_required() -> None:
    with pytest.raises(ValidationError):
        GuardrailPlanDraftCreate(
            dependent_user_id="dep-1",
            relationship_draft_id="rel-1",
            template_id="",
        )


def test_household_draft_create_requires_valid_mode() -> None:
    with pytest.raises(ValidationError):
        HouseholdDraftCreate(name="Home", mode="unknown")


def test_activation_summary_response_tracks_counts() -> None:
    summary = ActivationSummaryResponse(
        household_draft_id="draft-1",
        status="invites_pending",
        active_count=1,
        pending_count=2,
        failed_count=0,
    )

    assert summary.status == "invites_pending"
    assert summary.pending_count == 2


def test_household_member_draft_supports_invite_first_dependents() -> None:
    payload = HouseholdMemberDraftCreate(
        role="dependent",
        display_name="Alex",
        email="alex@example.com",
        invite_required=True,
        account_mode="invite_new",
        provisioning_status="not_started",
    )

    assert payload.user_id is None
    assert payload.account_mode == "invite_new"
    assert payload.provisioning_status == "not_started"
