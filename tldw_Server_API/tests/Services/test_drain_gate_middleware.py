from __future__ import annotations

from types import SimpleNamespace
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


@pytest.fixture()
def test_app():
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.services.app_lifecycle import reset_lifecycle_state

    reset_lifecycle_state(app)
    return app


@pytest.fixture()
def draining_client(test_app):
    from tldw_Server_API.app.services.app_lifecycle import get_or_create_lifecycle_state

    headers = {"X-API-KEY": os.environ.get("SINGLE_USER_API_KEY", "test-api-key-12345")}

    with TestClient(test_app, headers=headers) as client:
        state = get_or_create_lifecycle_state(test_app)
        state.phase = "draining"
        state.ready = False
        state.draining = True
        yield client


def test_drain_gate_allows_health_but_rejects_mutation(test_app, draining_client):
    ok = draining_client.get("/health")
    head_ok = draining_client.head("/health")
    blocked = draining_client.post("/api/v1/chat/completions", json={"messages": []})
    if ok.status_code != 200:
        raise AssertionError(f"expected /health to stay open, got {ok.status_code}")
    if head_ok.status_code != 200:
        raise AssertionError(f"expected HEAD /health to stay open, got {head_ok.status_code}")
    if blocked.status_code != 503:
        raise AssertionError(f"expected drain gate to return 503, got {blocked.status_code}")
    if blocked.json()["reason"] != "shutdown_in_progress":
        raise AssertionError(f"unexpected drain reason: {blocked.json()['reason']!r}")


def test_drain_gate_rejects_non_control_plane_head_request(test_app, draining_client):
    blocked = draining_client.head("/api/v1/chat/completions")
    if blocked.status_code != 503:
        raise AssertionError(f"expected drain gate to reject HEAD /api/v1/chat/completions, got {blocked.status_code}")


def test_assert_may_start_work_raises_when_draining(test_app):
    from tldw_Server_API.app.services.app_lifecycle import (
        assert_may_start_work,
        get_or_create_lifecycle_state,
    )

    state = get_or_create_lifecycle_state(test_app)
    state.draining = True
    with pytest.raises(HTTPException) as excinfo:
        assert_may_start_work(test_app, kind="job_enqueue")
    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == {"message": "Shutdown in progress", "kind": "job_enqueue"}


def test_assert_may_start_work_noops_when_not_draining(test_app):
    from tldw_Server_API.app.services.app_lifecycle import assert_may_start_work

    assert_may_start_work(test_app, kind="job_enqueue")


def test_drain_gate_rejects_guarded_request_before_llm_budget_runs(test_app, draining_client, monkeypatch):
    from tldw_Server_API.app.core.AuthNZ.llm_budget_middleware import LLMBudgetMiddleware

    budget_called = {"value": False}

    async def _unexpected_budget_dispatch(self, request, call_next):
        budget_called["value"] = True
        raise AssertionError("LLMBudgetMiddleware should not run while draining")

    monkeypatch.setattr(LLMBudgetMiddleware, "dispatch", _unexpected_budget_dispatch)

    blocked = draining_client.post("/api/v1/chat/completions", json={"messages": []})
    if blocked.status_code != 503:
        raise AssertionError(f"expected drain gate to return 503, got {blocked.status_code}")
    if blocked.json()["reason"] != "shutdown_in_progress":
        raise AssertionError(f"unexpected drain reason: {blocked.json()['reason']!r}")
    if budget_called["value"]:
        raise AssertionError("LLMBudgetMiddleware was invoked for a drained request")


@pytest.mark.parametrize(
    "method,path",
    [
        ("HEAD", "/health"),
        ("HEAD", "/ready"),
        ("HEAD", "/health/ready"),
    ],
)
def test_control_plane_head_paths_are_allowlisted(method, path):
    from tldw_Server_API.app.core.Security.drain_gate_middleware import _is_allowlisted_control_plane_path

    request = SimpleNamespace(method=method, url=SimpleNamespace(path=path))
    if not _is_allowlisted_control_plane_path(request):
        raise AssertionError(f"Expected {method} {path} to be allowlisted during drain")
