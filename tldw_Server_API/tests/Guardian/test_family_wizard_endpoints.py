from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.guardian_deps import get_guardian_db_for_user
from tldw_Server_API.app.api.v1.endpoints.family_wizard import router as family_wizard_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB


@pytest.fixture
def client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(family_wizard_router, prefix="/api/v1/guardian")
    db = GuardianDB(str(tmp_path / "family_wizard_endpoints.db"))

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
