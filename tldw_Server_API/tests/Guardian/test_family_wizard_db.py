from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management import Guardian_DB as guardian_db_module
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


def test_loads_json_or_default_logs_parse_warnings(
    guardian_db: GuardianDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_id = guardian_db.create_household_draft(
        owner_user_id="u1",
        mode="family",
        name="Bad Metadata Home",
        metadata={"created": True},
    )

    with guardian_db._lock:
        conn = guardian_db._connect()
        try:
            conn.execute(
                "UPDATE guardian_household_drafts SET metadata = ? WHERE id = ?",
                ("{invalid_json", draft_id),
            )
        finally:
            conn.close()

    warning_messages: list[str] = []

    def capture_warning(message: str, *args):
        rendered = message.format(*args) if args else message
        warning_messages.append(rendered)

    monkeypatch.setattr(guardian_db_module.logger, "warning", capture_warning)

    draft = guardian_db.get_household_draft(draft_id)
    assert draft is not None
    assert draft["metadata"] is None
    assert warning_messages


def test_create_household_member_invite_and_list_drafts(guardian_db: GuardianDB) -> None:
    draft_id = guardian_db.create_household_draft(
        owner_user_id="guardian-1",
        mode="family",
        name="Home",
    )
    member_id = guardian_db.add_household_member_draft(
        household_draft_id=draft_id,
        role="dependent",
        display_name="Alex",
        email="alex@example.com",
        invite_required=True,
        account_mode="invite_new",
        provisioning_status="not_started",
    )

    invite_id = guardian_db.create_household_member_invite(
        household_draft_id=draft_id,
        member_draft_id=member_id,
        delivery_channel="email",
        delivery_target="alex@example.com",
    )

    invite = guardian_db.get_household_member_invite(invite_id)
    drafts = guardian_db.list_household_drafts("guardian-1")

    assert invite is not None
    assert invite["status"] == "ready"
    assert invite["delivery_channel"] == "email"
    assert drafts
    assert drafts[0]["id"] == draft_id
