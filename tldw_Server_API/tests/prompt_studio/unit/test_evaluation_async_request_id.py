import os
import time
import tempfile

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.api.v1.API_Deps import prompt_studio_deps as deps


@pytest.fixture
def test_db():
    # Create DB under repository workspace to satisfy sandbox
    db_path = os.path.join("tmp", "pstest_eval_bg.db")
    # Ensure clean slate
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except Exception:
        pass
    db = PromptStudioDatabase(db_path, "test-client")
    try:
        yield db
    finally:
        try:
            db.close()
        except Exception:
            try:
                db.conn.close()
            except Exception:
                pass
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except Exception:
            pass


@pytest.fixture
def override_db_dependency(test_db):
    async def _override_db():
        return test_db

    app.dependency_overrides[deps.get_prompt_studio_db] = _override_db
    yield
    app.dependency_overrides.pop(deps.get_prompt_studio_db, None)


def test_create_evaluation_async_schedules_with_request_id(monkeypatch, override_db_dependency):
    called = {"request_id": None}

    # Ensure code path schedules background task (unset pytest env marker)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("TEST_MODE", "false")

    # Patch the async runner to capture propagated request_id
    import tldw_Server_API.app.api.v1.endpoints.prompt_studio_evaluations as eval_ep

    async def fake_run_evaluation_async(evaluation_id, db, *, request_id=None, traceparent=""):
        called["request_id"] = request_id

    monkeypatch.setattr(eval_ep, "run_evaluation_async", fake_run_evaluation_async, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/prompt-studio/evaluations",
        json={
            "project_id": 1,
            "prompt_id": 1,
            "name": "Async Eval",
            "test_case_ids": [],
            "config": {"model_name": "gpt-4o-mini"},
            "run_async": True,
        },
        headers={
            "X-Request-ID": "req-ps-eval-001",
            "X-API-KEY": "test-key",
        },
    )
    assert resp.status_code == 200, resp.text

    # BackgroundTasks executes after response generation in TestClient; give a tiny nudge if needed
    if called["request_id"] is None:
        time.sleep(0.01)
    assert called["request_id"] == "req-ps-eval-001"
