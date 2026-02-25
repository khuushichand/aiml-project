from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.Meetings_DB_Deps import (
    get_meetings_db_for_user,
    get_meetings_db_for_websocket,
)
from tldw_Server_API.app.api.v1.endpoints.meetings import router as meetings_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase


@pytest.fixture()
def meetings_api_client(tmp_path):
    db = MeetingsDatabase(db_path=tmp_path / "Media_DB_v2.db", client_id="api-test", user_id="1")
    app = FastAPI()
    app.include_router(meetings_router, prefix="/api/v1")

    async def _override_meetings_db() -> MeetingsDatabase:
        return db

    async def _override_user() -> User:
        return User(
            id=1,
            username="meetings-tester",
            role="admin",
            roles=["admin"],
            is_admin=True,
        )

    app.dependency_overrides[get_meetings_db_for_user] = _override_meetings_db
    app.dependency_overrides[get_meetings_db_for_websocket] = _override_meetings_db
    app.dependency_overrides[get_request_user] = _override_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    db.close_connection()
