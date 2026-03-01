from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB


@pytest.fixture
def guardian_db(tmp_path):
    return GuardianDB(str(tmp_path / "family_wizard.db"))


def test_create_and_load_household_draft(guardian_db: GuardianDB) -> None:
    draft_id = guardian_db.create_household_draft(
        owner_user_id="u1",
        mode="family",
        name="Home",
    )
    draft = guardian_db.get_household_draft(draft_id)
    assert draft is not None
    assert draft["mode"] == "family"
    assert draft["name"] == "Home"


def test_member_relationship_plan_and_activation_run_crud(guardian_db: GuardianDB) -> None:
    draft_id = guardian_db.create_household_draft(
        owner_user_id="g1",
        mode="family",
        name="Household",
    )
    guardian_member_id = guardian_db.add_household_member_draft(
        household_draft_id=draft_id,
        role="guardian",
        display_name="Guardian",
        user_id="g1",
    )
    dependent_member_id = guardian_db.add_household_member_draft(
        household_draft_id=draft_id,
        role="dependent",
        display_name="Child",
        user_id="d1",
        invite_required=True,
    )
    relationship_draft_id = guardian_db.create_relationship_draft(
        household_draft_id=draft_id,
        guardian_member_draft_id=guardian_member_id,
        dependent_member_draft_id=dependent_member_id,
        relationship_type="parent",
    )
    plan_id = guardian_db.create_guardrail_plan_draft(
        household_draft_id=draft_id,
        dependent_user_id="d1",
        relationship_draft_id=relationship_draft_id,
        template_id="default-child-safe",
        overrides={"notify_context": "snippet"},
    )
    run_id = guardian_db.record_activation_run(
        household_draft_id=draft_id,
        relationship_id=None,
        dependent_user_id="d1",
        plan_draft_id=plan_id,
        status="queued",
        detail="Queued until acceptance",
    )

    members = guardian_db.list_household_member_drafts(draft_id)
    plans = guardian_db.list_guardrail_plan_drafts(draft_id)
    runs = guardian_db.list_activation_runs(draft_id)

    assert len(members) == 2
    assert plans[0]["template_id"] == "default-child-safe"
    assert runs[0]["id"] == run_id
