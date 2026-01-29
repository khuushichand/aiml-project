from __future__ import annotations

import os

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


def _user(uid: int) -> User:
    return User(id=uid, username=f"user-{uid}", is_active=True, is_admin=False)


def test_session_upload_creates_workspace(monkeypatch) -> None:
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("SANDBOX_ENABLE_EXECUTION", "false")
    os.environ.setdefault("SANDBOX_BACKGROUND_EXECUTION", "true")

    client = TestClient(app)
    app.dependency_overrides[get_request_user] = lambda: _user(1)
    try:
        body = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "timeout_sec": 60,
        }
        r = client.post("/api/v1/sandbox/sessions", json=body)
        assert r.status_code == 200
        session_id = r.json()["id"]

        files = [("files", ("hello.txt", b"hello"))]
        r2 = client.post(f"/api/v1/sandbox/sessions/{session_id}/files", files=files)
        assert r2.status_code == 200
        payload = r2.json()
        assert payload.get("bytes_received") == 5
        assert payload.get("file_count") == 1
    finally:
        app.dependency_overrides.pop(get_request_user, None)
