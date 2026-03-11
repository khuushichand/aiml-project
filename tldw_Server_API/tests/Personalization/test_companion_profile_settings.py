from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_personalization_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.main import app as fastapi_app


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_companion_profile_db(tmp_path):
    db = PersonalizationDB(str(tmp_path / "personalization.db"))

    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def override_db_dep():
        return db

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_personalization_db_for_user] = override_db_dep

    with TestClient(fastapi_app) as client:
        yield client, db

    fastapi_app.dependency_overrides.clear()


def test_personalization_profile_exposes_companion_reflection_flags(
    client_with_companion_profile_db,
) -> None:
    client, db = client_with_companion_profile_db
    db.update_profile(
        "1",
        enabled=1,
        companion_reflections_enabled=1,
        companion_daily_reflections_enabled=0,
        companion_weekly_reflections_enabled=1,
    )

    response = client.get("/api/v1/personalization/profile")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["companion_reflections_enabled"] is True
    assert payload["companion_daily_reflections_enabled"] is False
    assert payload["companion_weekly_reflections_enabled"] is True
