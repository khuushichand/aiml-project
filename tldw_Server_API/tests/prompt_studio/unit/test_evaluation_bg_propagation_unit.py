import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.API_Deps import prompt_studio_deps as deps


class _StubCursor:
    def __init__(self):
        self.lastrowid = 1

    def execute(self, *args, **kwargs):
        # Do nothing; simulate successful INSERT
        self.lastrowid = 1


class _StubConn:
    def cursor(self):
        return _StubCursor()

    def commit(self):
        pass


class _StubDB:
    def get_connection(self):
        return _StubConn()


@pytest.fixture
def override_ps_deps(monkeypatch):
    async def _override_db():
        return _StubDB()

    async def _override_user():
        return {
            "user_id": "u",
            "client_id": "test-client",
            "is_authenticated": True,
            "is_admin": True,
            "permissions": ["all"],
        }

    app.dependency_overrides[deps.get_prompt_studio_db] = _override_db
    app.dependency_overrides[deps.get_prompt_studio_user] = _override_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(deps.get_prompt_studio_db, None)
        app.dependency_overrides.pop(deps.get_prompt_studio_user, None)


def test_evaluation_async_add_task_receives_request_id(monkeypatch, override_ps_deps):
    # Force scheduling branch (not inline) by removing PyTest env hint and disabling TEST_MODE
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("TEST_MODE", "false")

    # Capture add_task call arguments
    captured = {"func": None, "args": None, "kwargs": None}

    from fastapi.background import BackgroundTasks as _BT

    def fake_add_task(self, func, *args, **kwargs):  # noqa: D401
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        # Do not schedule to avoid executing background work in tests
        return None

    monkeypatch.setattr(_BT, "add_task", fake_add_task, raising=True)

    # Also patch the runner to a noop (defensive)
    import tldw_Server_API.app.api.v1.endpoints.prompt_studio_evaluations as eval_ep

    async def noop_run(*a, **kw):
        return None

    monkeypatch.setattr(eval_ep, "run_evaluation_async", noop_run, raising=True)

    client = TestClient(app)
    r = client.post(
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
            "X-Request-ID": "req-eval-xyz",
            "X-API-KEY": "test-key",
        },
    )
    assert r.status_code == 200, r.text
    # Ensure add_task was called and received propagated identifiers
    assert captured["func"] is not None
    # First positional args: (evaluation_id, db)
    assert isinstance(captured["args"], tuple) and len(captured["args"]) >= 2
    assert captured["kwargs"].get("request_id") == "req-eval-xyz"
    # traceparent may be empty if not provided; verify kwarg exists
    assert "traceparent" in captured["kwargs"]
