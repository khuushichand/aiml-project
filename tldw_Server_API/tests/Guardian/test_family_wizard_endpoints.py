from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_registration_service_dep
from tldw_Server_API.app.api.v1.API_Deps.guardian_deps import get_guardian_db_for_user
from tldw_Server_API.app.api.v1.endpoints import family_wizard as family_wizard_module
from tldw_Server_API.app.api.v1.endpoints.family_wizard import router as family_wizard_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(family_wizard_router, prefix="/api/v1/guardian")
    db = GuardianDB(str(tmp_path / "family_wizard_endpoints.db"))
    app.state.guardian_db = db
    monkeypatch.setattr(family_wizard_module, "_guardian_db_for_invite_token", lambda _token: db)

    async def override_user() -> User:
        return User(
            id="guardian-1",
            username="guardian",
            email="guardian@example.com",
            is_active=True,
            is_admin=False,
        )

    def override_guardian_db() -> GuardianDB:
        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_guardian_db_for_user] = override_guardian_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_create_household_draft_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Home", "mode": "family"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["name"] == "Home"
    assert payload["mode"] == "family"
    assert payload["status"] == "draft"


def test_list_household_drafts_endpoint_returns_owned_drafts(client: TestClient) -> None:
    first = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Home", "mode": "family"},
    )
    second = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "School", "mode": "family"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    response = client.get("/api/v1/guardian/wizard/drafts")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert [row["name"] for row in payload] == ["School", "Home"]


def test_member_relationship_and_plan_endpoints(client: TestClient) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Home", "mode": "family"},
    )
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Parent", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "dependent", "display_name": "Child", "user_id": "child-1"},
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_payload = relationship_res.json()
    assert relationship_payload["status"] == "pending"
    assert relationship_payload["relationship_id"] is not None

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_user_id": "child-1",
            "relationship_draft_id": relationship_payload["id"],
            "template_id": "default-child-safe",
            "overrides": {"notify_context": "snippet"},
        },
    )
    assert plan_res.status_code == 201, plan_res.text
    plan_payload = plan_res.json()
    assert plan_payload["template_id"] == "default-child-safe"
    assert plan_payload["status"] == "queued"


def test_resend_pending_invites_endpoint(client: TestClient) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Home", "mode": "family"},
    )
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Parent", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "dependent", "display_name": "Child", "user_id": "child-1"},
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text

    resend_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/invites/resend",
        json={"dependent_user_ids": ["child-1"]},
    )
    assert resend_res.status_code == 200, resend_res.text
    payload = resend_res.json()
    assert payload["household_draft_id"] == draft_id
    assert payload["resent_count"] == 1
    assert payload["skipped_count"] == 0
    assert payload["resent_user_ids"] == ["child-1"]


def test_resend_household_member_invite_endpoint_marks_invite_sent(client: TestClient) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Invite Resend Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert dependent_member.status_code == 201, dependent_member.text
    member_id = dependent_member.json()["id"]

    provision_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members/{member_id}/invite/provision",
    )
    assert provision_res.status_code == 201, provision_res.text
    invite_id = provision_res.json()["id"]

    resend_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/invites/{invite_id}/resend",
    )
    assert resend_res.status_code == 200, resend_res.text
    payload = resend_res.json()

    assert payload["status"] == "sent"
    assert payload["resend_count"] == 1
    assert payload["last_sent_at"] is not None


def test_relationship_mapping_allows_invite_first_dependent_without_runtime_relationship(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Invite Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Parent", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    payload = relationship_res.json()
    assert payload["relationship_id"] is None
    assert payload["status"] == "pending_provisioning"


def test_save_guardrail_plan_allows_invite_first_dependent_without_resolved_user_id(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Invite Plan Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Parent", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_id = relationship_res.json()["id"]

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_draft_id": relationship_id,
            "template_id": "default-child-safe",
            "overrides": {"notify_context": "snippet"},
        },
    )
    assert plan_res.status_code == 201, plan_res.text
    payload = plan_res.json()
    assert payload["dependent_member_draft_id"] == dependent_member.json()["id"]
    assert payload["dependent_user_id"] is None
    assert payload["status"] == "queued"


def test_tracker_endpoint_returns_row_level_blockers_and_actions_for_expired_invite(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Tracker Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Parent", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text
    member_id = dependent_member.json()["id"]

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": member_id,
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_id = relationship_res.json()["id"]

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_member_draft_id": member_id,
            "relationship_draft_id": relationship_id,
            "template_id": "default-child-safe",
            "overrides": {"notify_context": "snippet"},
        },
    )
    assert plan_res.status_code == 201, plan_res.text

    provision_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members/{member_id}/invite/provision",
    )
    assert provision_res.status_code == 201, provision_res.text
    invite_id = provision_res.json()["id"]

    db = client.app.state.guardian_db
    assert db.update_household_member_invite_status(
        invite_id,
        status="expired",
        expires_at="2026-03-18T00:00:00+00:00",
    )

    tracker_res = client.get(f"/api/v1/guardian/wizard/drafts/{draft_id}/tracker")
    assert tracker_res.status_code == 200, tracker_res.text
    payload = tracker_res.json()
    item = payload["items"][0]

    assert item["invite_status"] == "expired"
    assert "invite_expired" in item["blocker_codes"]
    assert "reissue_invite" in item["available_actions"]


def test_reissue_invite_endpoint_rotates_token_and_revokes_old_invite(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Reissue Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert dependent_member.status_code == 201, dependent_member.text
    member_id = dependent_member.json()["id"]

    provision_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members/{member_id}/invite/provision",
    )
    assert provision_res.status_code == 201, provision_res.text
    original_invite = provision_res.json()
    invite_id = original_invite["id"]

    db = client.app.state.guardian_db
    assert db.update_household_member_invite_status(
        invite_id,
        status="expired",
        expires_at="2026-03-18T00:00:00+00:00",
    )

    reissue_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/invites/{invite_id}/reissue",
    )
    assert reissue_res.status_code == 200, reissue_res.text
    payload = reissue_res.json()

    revoked_invite = db.get_household_member_invite(invite_id)

    assert revoked_invite is not None
    assert revoked_invite["status"] == "revoked"
    assert payload["status"] == "ready"
    assert payload["invite_token"] != original_invite["invite_token"]


def test_preview_household_invite_endpoint_returns_invite_context(client: TestClient) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Preview Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert dependent_member.status_code == 201, dependent_member.text
    member_id = dependent_member.json()["id"]

    provision_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members/{member_id}/invite/provision",
    )
    assert provision_res.status_code == 201, provision_res.text
    invite_token = provision_res.json()["invite_token"]

    preview_res = client.get(f"/api/v1/guardian/wizard/invites/preview?token={invite_token}")
    assert preview_res.status_code == 200, preview_res.text
    payload = preview_res.json()

    assert payload["dependent_display_name"] == "Alex"
    assert payload["household_name"] == "Preview Home"
    assert payload["invite_status"] == "ready"
    assert payload["requires_registration"] is True


def test_accept_household_invite_registers_new_user_and_materializes_plan(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Register Accept Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Parent", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text
    member_id = dependent_member.json()["id"]

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": member_id,
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_draft_id = relationship_res.json()["id"]

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_member_draft_id": member_id,
            "relationship_draft_id": relationship_draft_id,
            "template_id": "default-child-safe",
            "overrides": {"category": "explicit_content", "action": "block"},
        },
    )
    assert plan_res.status_code == 201, plan_res.text
    plan_id = plan_res.json()["id"]

    provision_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members/{member_id}/invite/provision",
    )
    assert provision_res.status_code == 201, provision_res.text
    invite_token = provision_res.json()["invite_token"]
    invite_id = provision_res.json()["id"]

    class StubRegistrationService:
        async def register_user(self, *, username: str, email: str, password: str, registration_code=None, **_kwargs):
            return {
                "user_id": "child-registered",
                "username": username,
                "email": email,
                "is_verified": True,
                "registration_code_id": None,
                "registration_code_org_id": None,
                "registration_code_org_role": None,
                "registration_code_team_id": None,
            }

    async def override_registration_service():
        return StubRegistrationService()

    client.app.dependency_overrides[get_registration_service_dep] = override_registration_service
    try:
        accept_res = client.post(
            "/api/v1/guardian/wizard/invites/accept/register",
            json={
                "token": invite_token,
                "username": "alexchild",
                "email": "alex@example.com",
                "password": "StrongPass123!",
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_registration_service_dep, None)

    assert accept_res.status_code == 200, accept_res.text
    payload = accept_res.json()
    db = client.app.state.guardian_db
    updated_member = db.get_household_member_draft(member_id)
    updated_plan = db.get_guardrail_plan_draft(plan_id)
    accepted_invite = db.get_household_member_invite(invite_id)
    relationship_draft = db.get_relationship_draft(relationship_draft_id)

    assert payload["user_id"] == "child-registered"
    assert payload["materialized_plan_count"] == 1
    assert updated_member is not None and updated_member["user_id"] == "child-registered"
    assert updated_plan is not None and updated_plan["status"] == "active"
    assert updated_plan["dependent_user_id"] == "child-registered"
    assert accepted_invite is not None and accepted_invite["status"] == "accepted"
    assert relationship_draft is not None and relationship_draft["status"] == "active"


def test_accept_household_invite_claims_existing_user_and_materializes_plan(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Claim Accept Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Parent", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={
            "role": "dependent",
            "display_name": "Alex",
            "email": "alex@example.com",
            "invite_required": True,
            "account_mode": "invite_new",
            "provisioning_status": "not_started",
        },
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text
    member_id = dependent_member.json()["id"]

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": member_id,
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_draft_id = relationship_res.json()["id"]

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_member_draft_id": member_id,
            "relationship_draft_id": relationship_draft_id,
            "template_id": "default-child-safe",
            "overrides": {"category": "explicit_content", "action": "block"},
        },
    )
    assert plan_res.status_code == 201, plan_res.text

    provision_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members/{member_id}/invite/provision",
    )
    assert provision_res.status_code == 201, provision_res.text
    invite_token = provision_res.json()["invite_token"]

    async def override_child_user() -> User:
        return User(
            id="child-existing",
            username="childexisting",
            email="alex@example.com",
            is_active=True,
            is_admin=False,
        )

    original_user_override = client.app.dependency_overrides[get_request_user]
    client.app.dependency_overrides[get_request_user] = override_child_user
    try:
        accept_res = client.post(
            "/api/v1/guardian/wizard/invites/accept/claim",
            json={"token": invite_token},
        )
    finally:
        client.app.dependency_overrides[get_request_user] = original_user_override

    assert accept_res.status_code == 200, accept_res.text
    payload = accept_res.json()
    assert payload["user_id"] == "child-existing"
    assert payload["was_existing_user"] is True


def test_get_latest_household_draft_endpoint_returns_most_recent(client: TestClient) -> None:
    first = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Older Draft", "mode": "family"},
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    second = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Newer Draft", "mode": "family"},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]

    # Bump the first draft timestamp so it is now "latest".
    rename_first = client.patch(
        f"/api/v1/guardian/wizard/drafts/{first_id}",
        json={"name": "Renamed Latest Draft"},
    )
    assert rename_first.status_code == 200, rename_first.text

    latest = client.get("/api/v1/guardian/wizard/drafts/latest")
    assert latest.status_code == 200, latest.text
    payload = latest.json()
    assert payload["id"] == first_id
    assert payload["id"] != second_id
    assert payload["name"] == "Renamed Latest Draft"


def test_get_household_snapshot_endpoint_returns_members_relationships_and_plans(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Snapshot Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Primary Guardian", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "dependent", "display_name": "Alex", "user_id": "alex-kid"},
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_id = relationship_res.json()["id"]

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_user_id": "alex-kid",
            "relationship_draft_id": relationship_id,
            "template_id": "default-child-safe",
            "overrides": {"action": "warn", "notify_context": "snippet"},
        },
    )
    assert plan_res.status_code == 201, plan_res.text

    snapshot_res = client.get(f"/api/v1/guardian/wizard/drafts/{draft_id}/snapshot")
    assert snapshot_res.status_code == 200, snapshot_res.text
    snapshot = snapshot_res.json()

    assert snapshot["household"]["id"] == draft_id
    assert len(snapshot["members"]) == 2
    assert len(snapshot["relationships"]) == 1
    assert len(snapshot["plans"]) == 1
    assert snapshot["plans"][0]["dependent_user_id"] == "alex-kid"


def test_relationship_mapping_requires_authenticated_guardian_member(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "AuthZ Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    non_auth_guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Other Guardian", "user_id": "guardian-2"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "dependent", "display_name": "Child", "user_id": "child-1"},
    )
    assert non_auth_guardian_member.status_code == 201, non_auth_guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": non_auth_guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 403, relationship_res.text
    assert "authenticated guardian" in relationship_res.json()["detail"].lower()


def test_save_guardrail_plan_rejects_dependent_user_id_mismatch(
    client: TestClient,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Plan Mismatch Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Guardian", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "dependent", "display_name": "Child", "user_id": "child-1"},
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_id = relationship_res.json()["id"]

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_user_id": "child-2",
            "relationship_draft_id": relationship_id,
            "template_id": "default-child-safe",
            "overrides": {"action": "warn"},
        },
    )
    assert plan_res.status_code == 400, plan_res.text
    assert "must match" in plan_res.json()["detail"].lower()


def test_activation_summary_uses_bulk_relationship_lookup(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_res = client.post(
        "/api/v1/guardian/wizard/drafts",
        json={"name": "Summary Home", "mode": "family"},
    )
    assert draft_res.status_code == 201, draft_res.text
    draft_id = draft_res.json()["id"]

    guardian_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "guardian", "display_name": "Guardian", "user_id": "guardian-1"},
    )
    dependent_member = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/members",
        json={"role": "dependent", "display_name": "Child", "user_id": "child-1"},
    )
    assert guardian_member.status_code == 201, guardian_member.text
    assert dependent_member.status_code == 201, dependent_member.text

    relationship_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_member.json()["id"],
            "dependent_member_draft_id": dependent_member.json()["id"],
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert relationship_res.status_code == 201, relationship_res.text
    relationship_id = relationship_res.json()["id"]

    plan_res = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_user_id": "child-1",
            "relationship_draft_id": relationship_id,
            "template_id": "default-child-safe",
            "overrides": {"action": "warn"},
        },
    )
    assert plan_res.status_code == 201, plan_res.text

    db = client.app.state.guardian_db

    def fail_if_called(_relationship_draft_id: str):
        raise AssertionError("get_relationship_draft should not be called in activation summary loop")

    monkeypatch.setattr(db, "get_relationship_draft", fail_if_called)

    summary_res = client.get(f"/api/v1/guardian/wizard/drafts/{draft_id}/activation-summary")
    assert summary_res.status_code == 200, summary_res.text
    payload = summary_res.json()
    assert payload["pending_count"] == 1
    assert payload["items"][0]["relationship_status"] == "pending"
