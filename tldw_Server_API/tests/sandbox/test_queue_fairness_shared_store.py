from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import clear_config_cache, settings as app_settings
from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType
from tldw_Server_API.app.core.Sandbox.orchestrator import QueueFull, SandboxOrchestrator

pytestmark = pytest.mark.unit


def _configure_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "sandbox_store.db")
    root_dir = str(tmp_path / "sandbox_root")
    snapshot_dir = str(tmp_path / "snapshots")
    monkeypatch.setenv("SANDBOX_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SANDBOX_STORE_DB_PATH", db_path)
    monkeypatch.setenv("SANDBOX_ROOT_DIR", root_dir)
    monkeypatch.setenv("SANDBOX_SNAPSHOT_PATH", snapshot_dir)
    if hasattr(app_settings, "SANDBOX_STORE_BACKEND"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_BACKEND", "sqlite")
    if hasattr(app_settings, "SANDBOX_STORE_DB_PATH"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_DB_PATH", db_path)
    if hasattr(app_settings, "SANDBOX_ROOT_DIR"):
        monkeypatch.setattr(app_settings, "SANDBOX_ROOT_DIR", root_dir)
    if hasattr(app_settings, "SANDBOX_SNAPSHOT_PATH"):
        monkeypatch.setattr(app_settings, "SANDBOX_SNAPSHOT_PATH", snapshot_dir)
    clear_config_cache()


def _spec(*, command: str, persona_id: str | None = None) -> RunSpec:
    return RunSpec(
        session_id=None,
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        command=["echo", command],
        persona_id=persona_id,
    )


def test_queue_per_user_quota_enforced_across_orchestrators(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "120")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_USER", "1")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_PERSONA", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE_GROUP", "0")

    orch_a = SandboxOrchestrator()
    orch_b = SandboxOrchestrator()

    orch_a.enqueue_run(
        user_id="shared-user",
        spec=_spec(command="a-1"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "a-1"]},
    )

    with pytest.raises(QueueFull) as exc:
        orch_b.enqueue_run(
            user_id="shared-user",
            spec=_spec(command="b-1"),
            spec_version="1.0",
            idem_key=None,
            body={"command": ["echo", "b-1"]},
        )

    assert exc.value.reason == "user_queue_quota_exceeded"
    assert exc.value.quota_scope == "user_id"

    orch_b.enqueue_run(
        user_id="different-user",
        spec=_spec(command="b-2"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "b-2"]},
    )


def test_queue_per_persona_quota_enforced_across_orchestrators(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "120")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_USER", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_PERSONA", "1")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE", "0")
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_PER_WORKSPACE_GROUP", "0")

    orch_a = SandboxOrchestrator()
    orch_b = SandboxOrchestrator()

    orch_a.enqueue_run(
        user_id="user-1",
        spec=_spec(command="a-1", persona_id="persona-shared"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "a-1"]},
    )

    with pytest.raises(QueueFull) as exc:
        orch_b.enqueue_run(
            user_id="user-2",
            spec=_spec(command="b-1", persona_id="persona-shared"),
            spec_version="1.0",
            idem_key=None,
            body={"command": ["echo", "b-1"]},
        )

    assert exc.value.reason == "persona_queue_quota_exceeded"
    assert exc.value.quota_scope == "persona_id"

    orch_b.enqueue_run(
        user_id="user-2",
        spec=_spec(command="b-2", persona_id="persona-other"),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", "b-2"]},
    )
