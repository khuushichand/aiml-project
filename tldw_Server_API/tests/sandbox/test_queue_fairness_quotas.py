from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType
from tldw_Server_API.app.core.Sandbox.orchestrator import QueueFull, SandboxOrchestrator

pytestmark = pytest.mark.unit


def _run_spec(*, persona_id: str | None = None, workspace_id: str | None = None, workspace_group_id: str | None = None, cmd_suffix: str = "1") -> RunSpec:
    return RunSpec(
        session_id=None,
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        command=["echo", cmd_suffix],
        persona_id=persona_id,
        workspace_id=workspace_id,
        workspace_group_id=workspace_group_id,
    )


def test_queue_quota_per_user_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "60")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_USER", "1")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_PERSONA", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE_GROUP", "0")

    orch = SandboxOrchestrator()

    orch.enqueue_run(
        user_id=101,
        spec=_run_spec(cmd_suffix="u1-a"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "u1-a"]},
    )

    with pytest.raises(QueueFull) as exc:
        orch.enqueue_run(
            user_id=101,
            spec=_run_spec(cmd_suffix="u1-b"),
            spec_version="1.0",
            idem_key=None,
            body={"command": ["echo", "u1-b"]},
        )

    assert exc.value.reason == "user_queue_quota_exceeded"
    assert exc.value.quota_scope == "user_id"
    assert exc.value.limit == 1

    # Different user should still be admitted.
    orch.enqueue_run(
        user_id=202,
        spec=_run_spec(cmd_suffix="u2-a"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "u2-a"]},
    )


def test_queue_quota_per_persona_is_enforced_across_users(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "60")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_USER", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_PERSONA", "1")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE_GROUP", "0")

    orch = SandboxOrchestrator()

    orch.enqueue_run(
        user_id=101,
        spec=_run_spec(persona_id="persona-alpha", cmd_suffix="p-a"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "p-a"]},
    )

    with pytest.raises(QueueFull) as exc:
        orch.enqueue_run(
            user_id=202,
            spec=_run_spec(persona_id="persona-alpha", cmd_suffix="p-b"),
            spec_version="1.0",
            idem_key=None,
            body={"command": ["echo", "p-b"]},
        )

    assert exc.value.reason == "persona_queue_quota_exceeded"
    assert exc.value.quota_scope == "persona_id"
    assert exc.value.limit == 1

    orch.enqueue_run(
        user_id=202,
        spec=_run_spec(persona_id="persona-beta", cmd_suffix="p-c"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "p-c"]},
    )


def test_queue_quota_per_workspace_group_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "60")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_USER", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_PERSONA", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE_GROUP", "1")

    orch = SandboxOrchestrator()

    orch.enqueue_run(
        user_id=101,
        spec=_run_spec(workspace_group_id="wg-1", cmd_suffix="wg-a"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "wg-a"]},
    )

    with pytest.raises(QueueFull) as exc:
        orch.enqueue_run(
            user_id=202,
            spec=_run_spec(workspace_group_id="wg-1", cmd_suffix="wg-b"),
            spec_version="1.0",
            idem_key=None,
            body={"command": ["echo", "wg-b"]},
        )

    assert exc.value.reason == "workspace_group_queue_quota_exceeded"
    assert exc.value.quota_scope == "workspace_group_id"
    assert exc.value.limit == 1

    orch.enqueue_run(
        user_id=202,
        spec=_run_spec(workspace_group_id="wg-2", cmd_suffix="wg-c"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "wg-c"]},
    )
