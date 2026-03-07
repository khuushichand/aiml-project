from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import chat_workflows as chat_workflows_mod
from tldw_Server_API.app.core.AuthNZ.permissions import (
    CHAT_WORKFLOWS_READ,
    CHAT_WORKFLOWS_RUN,
    CHAT_WORKFLOWS_WRITE,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.DB_Management.ChatWorkflows_DB import ChatWorkflowsDatabase


def _make_principal(*, permissions: list[str]) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["user"],
        permissions=permissions,
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )


def _build_app(
    db: ChatWorkflowsDatabase,
    *,
    principal_permissions: list[str],
    user_permissions: list[str],
) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_workflows_mod.router)
    principal = _make_principal(permissions=principal_permissions)

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        request.state.auth = AuthContext(
            principal=principal,
            ip=request.client.host if getattr(request, "client", None) else None,
            user_agent=request.headers.get("User-Agent"),
            request_id=request.headers.get("X-Request-ID"),
        )
        return principal

    async def _fake_get_user_context() -> dict[str, Any]:
        return {
            "user_id": "1",
            "tenant_id": "default",
            "client_id": "test-client",
            "is_admin": False,
            "permissions": list(user_permissions),
        }

    async def _fake_get_db() -> ChatWorkflowsDatabase:
        return db

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[chat_workflows_mod._get_user_context] = _fake_get_user_context
    app.dependency_overrides[chat_workflows_mod._get_db] = _fake_get_db
    return app


@pytest.mark.asyncio
async def test_chat_workflow_run_can_complete_and_continue_to_chat(tmp_path):
    db = ChatWorkflowsDatabase(
        db_path=tmp_path / "chat_workflows.db",
        client_id="test-client",
    )
    app = _build_app(
        db,
        principal_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
        user_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
    )

    with TestClient(app) as client:
        template_resp = client.post(
            "/api/v1/chat-workflows/templates",
            json={
                "title": "Discovery",
                "description": "Collect context",
                "steps": [
                    {
                        "id": "goal",
                        "step_index": 0,
                        "label": "Goal",
                        "base_question": "What is your goal?",
                        "question_mode": "stock",
                        "context_refs": [],
                    }
                ],
            },
        )
        assert template_resp.status_code == 201, template_resp.text
        template_id = template_resp.json()["id"]

        run_resp = client.post(
            "/api/v1/chat-workflows/runs",
            json={"template_id": template_id, "selected_context_refs": []},
        )
        assert run_resp.status_code == 200, run_resp.text
        run_id = run_resp.json()["run_id"]
        assert db.get_run(run_id)["source_mode"] == "saved_template"

        answer_resp = client.post(
            f"/api/v1/chat-workflows/runs/{run_id}/answer",
            json={"step_index": 0, "answer_text": "Ship a feature"},
        )
        assert answer_resp.status_code == 200, answer_resp.text
        assert answer_resp.json()["status"] == "completed"

        continue_resp = client.post(f"/api/v1/chat-workflows/runs/{run_id}/continue-chat")
        assert continue_resp.status_code == 200, continue_resp.text
        assert continue_resp.json()["conversation_id"]


@pytest.mark.asyncio
async def test_chat_workflow_transcript_returns_structured_messages(tmp_path):
    db = ChatWorkflowsDatabase(
        db_path=tmp_path / "chat_workflows.db",
        client_id="test-client",
    )
    app = _build_app(
        db,
        principal_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
        user_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
    )

    with TestClient(app) as client:
        template_id = client.post(
            "/api/v1/chat-workflows/templates",
            json={
                "title": "Discovery",
                "steps": [
                    {
                        "id": "goal",
                        "step_index": 0,
                        "base_question": "What is your goal?",
                        "question_mode": "stock",
                        "context_refs": [],
                    }
                ],
            },
        ).json()["id"]
        run_id = client.post(
            "/api/v1/chat-workflows/runs",
            json={"template_id": template_id, "selected_context_refs": []},
        ).json()["run_id"]
        client.post(
            f"/api/v1/chat-workflows/runs/{run_id}/answer",
            json={"step_index": 0, "answer_text": "Ship a feature"},
        )

        transcript_resp = client.get(f"/api/v1/chat-workflows/runs/{run_id}/transcript")
        assert transcript_resp.status_code == 200, transcript_resp.text
        transcript_body = transcript_resp.json()
        assert transcript_body["run_id"] == run_id
        messages = transcript_body["messages"]
        assert messages[0]["role"] == "assistant"
        assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_chat_workflow_cancel_marks_run_canceled(tmp_path):
    db = ChatWorkflowsDatabase(
        db_path=tmp_path / "chat_workflows.db",
        client_id="test-client",
    )
    app = _build_app(
        db,
        principal_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
        user_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
    )

    with TestClient(app) as client:
        template_id = client.post(
            "/api/v1/chat-workflows/templates",
            json={
                "title": "Discovery",
                "steps": [
                    {
                        "id": "goal",
                        "step_index": 0,
                        "base_question": "What is your goal?",
                        "question_mode": "stock",
                        "context_refs": [],
                    }
                ],
            },
        ).json()["id"]
        run_id = client.post(
            "/api/v1/chat-workflows/runs",
            json={"template_id": template_id, "selected_context_refs": []},
        ).json()["run_id"]

        cancel_resp = client.post(f"/api/v1/chat-workflows/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["status"] == "canceled"


@pytest.mark.asyncio
async def test_chat_workflow_answer_is_idempotent_with_matching_key(tmp_path):
    db = ChatWorkflowsDatabase(
        db_path=tmp_path / "chat_workflows.db",
        client_id="test-client",
    )
    app = _build_app(
        db,
        principal_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
        user_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
    )

    with TestClient(app) as client:
        template_id = client.post(
            "/api/v1/chat-workflows/templates",
            json={
                "title": "Discovery",
                "steps": [
                    {
                        "id": "goal",
                        "step_index": 0,
                        "base_question": "What is your goal?",
                        "question_mode": "stock",
                        "context_refs": [],
                    }
                ],
            },
        ).json()["id"]
        run_id = client.post(
            "/api/v1/chat-workflows/runs",
            json={"template_id": template_id, "selected_context_refs": []},
        ).json()["run_id"]

        first_resp = client.post(
            f"/api/v1/chat-workflows/runs/{run_id}/answer",
            json={
                "step_index": 0,
                "answer_text": "Ship a feature",
                "idempotency_key": "answer-1",
            },
        )
        replay_resp = client.post(
            f"/api/v1/chat-workflows/runs/{run_id}/answer",
            json={
                "step_index": 0,
                "answer_text": "Ship a feature",
                "idempotency_key": "answer-1",
            },
        )

        assert first_resp.status_code == 200, first_resp.text
        assert replay_resp.status_code == 200, replay_resp.text
        assert len(db.list_answers(run_id)) == 1


@pytest.mark.asyncio
async def test_chat_workflow_answer_rejects_conflicting_idempotent_retry(tmp_path):
    db = ChatWorkflowsDatabase(
        db_path=tmp_path / "chat_workflows.db",
        client_id="test-client",
    )
    app = _build_app(
        db,
        principal_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
        user_permissions=[
            CHAT_WORKFLOWS_READ,
            CHAT_WORKFLOWS_WRITE,
            CHAT_WORKFLOWS_RUN,
        ],
    )

    with TestClient(app) as client:
        run_resp = client.post(
            "/api/v1/chat-workflows/runs",
            json={
                "template_draft": {
                    "title": "Generated",
                    "description": "Draft",
                    "version": 1,
                    "steps": [
                        {
                            "id": "goal",
                            "step_index": 0,
                            "base_question": "What is your goal?",
                            "question_mode": "stock",
                            "context_refs": [],
                        }
                    ],
                },
                "selected_context_refs": [],
            },
        )
        assert run_resp.status_code == 200, run_resp.text
        run_id = run_resp.json()["run_id"]
        assert db.get_run(run_id)["source_mode"] == "generated_draft"

        first_resp = client.post(
            f"/api/v1/chat-workflows/runs/{run_id}/answer",
            json={
                "step_index": 0,
                "answer_text": "Ship a feature",
                "idempotency_key": "answer-1",
            },
        )
        conflict_resp = client.post(
            f"/api/v1/chat-workflows/runs/{run_id}/answer",
            json={
                "step_index": 0,
                "answer_text": "Ship something else",
                "idempotency_key": "answer-1",
            },
        )

        assert first_resp.status_code == 200, first_resp.text
        assert conflict_resp.status_code == 409, conflict_resp.text
