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
