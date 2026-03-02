from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.guardian_deps import get_guardian_db_for_user
from tldw_Server_API.app.api.v1.endpoints import guardian_controls
from tldw_Server_API.app.api.v1.endpoints.guardian_controls import router as guardian_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB


@pytest.fixture
def guardian_controls_client(tmp_path) -> tuple[TestClient, GuardianDB, GuardianDB]:
    app = FastAPI()
    app.include_router(guardian_router, prefix="/api/v1/guardian")

    dependent_db = GuardianDB(str(tmp_path / "dependent_guardian.db"))
    guardian_db = GuardianDB(str(tmp_path / "primary_guardian.db"))

    async def override_user() -> User:
        return User(
            id="dependent-1",
            username="dependent",
            email="dependent@example.com",
            is_active=True,
            is_admin=False,
        )

    def override_guardian_db() -> GuardianDB:
        return dependent_db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_guardian_db_for_user] = override_guardian_db

    with TestClient(app) as test_client:
        yield test_client, dependent_db, guardian_db

    app.dependency_overrides.clear()


def test_accept_relationship_materializes_using_guardian_database(
    guardian_controls_client: tuple[TestClient, GuardianDB, GuardianDB],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, dependent_db, guardian_db = guardian_controls_client

    relationship = dependent_db.create_relationship(
        guardian_user_id="guardian-1",
        dependent_user_id="dependent-1",
        relationship_type="parent",
    )

    captured: dict[str, str] = {}

    def fake_materialize(db: GuardianDB, relationship_id: str, actor_user_id: str):
        captured["db_path"] = db.db_path
        captured["relationship_id"] = relationship_id
        captured["actor_user_id"] = actor_user_id
        return {"materialized_count": 0, "failed_count": 0, "policy_ids": []}

    monkeypatch.setattr(
        guardian_controls,
        "materialize_pending_plans_for_relationship",
        fake_materialize,
    )
    monkeypatch.setattr(
        guardian_controls,
        "get_guardian_db_for_user_id",
        lambda _user_id: guardian_db,
    )

    response = client.post(f"/api/v1/guardian/relationships/{relationship.id}/accept")
    assert response.status_code == 200, response.text
    assert captured["relationship_id"] == relationship.id
    assert captured["actor_user_id"] == "dependent-1"
    assert captured["db_path"] == guardian_db.db_path
