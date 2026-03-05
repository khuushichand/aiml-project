"""Authorization tests for privileged Kanban workflow endpoints."""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

pytestmark = pytest.mark.integration


@pytest.fixture()
def non_admin_workflow_client(tmp_path, monkeypatch):
    """Create workflow test client as a non-admin user."""
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))
    db_path = DatabasePaths.get_kanban_db_path("integration_non_admin_workflow_user")
    db = KanbanDB(str(db_path), user_id="integration_non_admin_workflow_user")

    async def override_user():
        return User(id=1, username="workflow-user", email="workflow@user.local", is_active=True, is_admin=False)

    from tldw_Server_API.app.api.v1.API_Deps.kanban_deps import get_kanban_db_for_user

    def override_db_dep():
        return db

    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    fastapi_app = app_main.app
    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_kanban_db_for_user] = override_db_dep

    with TestClient(fastapi_app) as client:
        yield client, db

    fastapi_app.dependency_overrides.clear()


def test_pause_workflow_policy_forbidden_for_non_admin(non_admin_workflow_client):
    """Non-admin callers should be blocked from privileged workflow controls."""
    client, _db = non_admin_workflow_client
    board_resp = client.post(
        "/api/v1/kanban/boards",
        json={"name": "Authz Workflow Board", "client_id": "authz-workflow-board-1"},
    )
    assert board_resp.status_code == 201, board_resp.text
    board_id = board_resp.json()["id"]

    pause_resp = client.post(f"/api/v1/kanban/workflow/control/boards/{board_id}/pause")
    assert pause_resp.status_code == 403, pause_resp.text
    payload: dict[str, Any] = pause_resp.json()
    assert isinstance(payload.get("detail"), dict)
    assert payload["detail"]["code"] == "forbidden"


def test_force_reassign_workflow_claim_forbidden_for_non_admin(non_admin_workflow_client):
    """Non-admin callers should be blocked from force-reassign recovery operation."""
    client, _db = non_admin_workflow_client
    board_resp = client.post(
        "/api/v1/kanban/boards",
        json={"name": "Authz Workflow Board 2", "client_id": "authz-workflow-board-2"},
    )
    assert board_resp.status_code == 201, board_resp.text
    board_id = board_resp.json()["id"]

    list_resp = client.post(
        f"/api/v1/kanban/boards/{board_id}/lists",
        json={"name": "Authz Workflow List 2", "client_id": "authz-workflow-list-2"},
    )
    assert list_resp.status_code == 201, list_resp.text
    list_id = list_resp.json()["id"]

    card_resp = client.post(
        f"/api/v1/kanban/lists/{list_id}/cards",
        json={"title": "Authz Workflow Card 2", "client_id": "authz-workflow-card-2"},
    )
    assert card_resp.status_code == 201, card_resp.text
    card_id = card_resp.json()["id"]

    reassign_resp = client.post(
        f"/api/v1/kanban/workflow/recovery/cards/{card_id}/force-reassign",
        json={
            "new_owner": "builder-2",
            "idempotency_key": "authz-force-reassign",
            "correlation_id": "corr-authz-force-reassign",
            "reason": "authz check",
        },
    )
    assert reassign_resp.status_code == 403, reassign_resp.text
    payload: dict[str, Any] = reassign_resp.json()
    assert isinstance(payload.get("detail"), dict)
    assert payload["detail"]["code"] == "forbidden"


def test_patch_workflow_state_forbidden_for_non_admin(non_admin_workflow_client):
    """Non-admin callers should be blocked from direct workflow state patching."""
    client, _db = non_admin_workflow_client
    board_resp = client.post(
        "/api/v1/kanban/boards",
        json={"name": "Authz Workflow Board 3", "client_id": "authz-workflow-board-3"},
    )
    assert board_resp.status_code == 201, board_resp.text
    board_id = board_resp.json()["id"]

    list_resp = client.post(
        f"/api/v1/kanban/boards/{board_id}/lists",
        json={"name": "Authz Workflow List 3", "client_id": "authz-workflow-list-3"},
    )
    assert list_resp.status_code == 201, list_resp.text
    list_id = list_resp.json()["id"]

    card_resp = client.post(
        f"/api/v1/kanban/lists/{list_id}/cards",
        json={"title": "Authz Workflow Card 3", "client_id": "authz-workflow-card-3"},
    )
    assert card_resp.status_code == 201, card_resp.text
    card_id = card_resp.json()["id"]

    state_resp = client.get(f"/api/v1/kanban/workflow/cards/{card_id}/state")
    assert state_resp.status_code == 200, state_resp.text
    state = state_resp.json()

    patch_resp = client.patch(
        f"/api/v1/kanban/workflow/cards/{card_id}/state",
        json={
            "workflow_status_key": state["workflow_status_key"],
            "expected_version": state["version"],
            "idempotency_key": "authz-state-patch",
            "actor": "non-admin-user",
        },
    )
    assert patch_resp.status_code == 403, patch_resp.text
    payload: dict[str, Any] = patch_resp.json()
    assert isinstance(payload.get("detail"), dict)
    assert payload["detail"]["code"] == "forbidden"
