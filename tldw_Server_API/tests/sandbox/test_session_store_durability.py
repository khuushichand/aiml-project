from __future__ import annotations

from pathlib import Path

from tldw_Server_API.app.core.config import clear_config_cache, settings as app_settings
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RuntimeType, RunSpec, SessionSpec, TrustLevel
from tldw_Server_API.app.core.Sandbox.orchestrator import SandboxOrchestrator
from tldw_Server_API.app.core.Sandbox.service import SandboxService
from tldw_Server_API.app.core.Sandbox.store import get_store


def _configure_sqlite_store(monkeypatch, tmp_path: Path) -> None:
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


def test_session_metadata_rehydrates_across_orchestrator_instances(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    spec = SessionSpec(runtime=RuntimeType.docker, base_image="python:3.11-slim")
    orch_a = SandboxOrchestrator()
    source = orch_a.create_session(
        user_id="user-42",
        spec=spec,
        spec_version="1.0",
        idem_key=None,
        body={"spec_version": "1.0", "runtime": "docker"},
    )

    owner_a = orch_a.get_session_owner(source.id)
    ws_a = orch_a.get_session_workspace_path(source.id)
    assert owner_a == "user-42"
    assert ws_a is not None

    marker = Path(str(ws_a)) / "marker.txt"
    marker.write_text("hello", encoding="utf-8")

    orch_b = SandboxOrchestrator()
    owner_b = orch_b.get_session_owner(source.id)
    restored = orch_b.get_session(source.id)
    ws_b = orch_b.get_session_workspace_path(source.id)

    assert owner_b == "user-42"
    assert restored is not None
    assert restored.id == source.id
    assert restored.runtime == RuntimeType.docker
    assert ws_b == ws_a
    assert (Path(str(ws_b)) / "marker.txt").read_text(encoding="utf-8") == "hello"


def test_clone_session_works_after_service_restart(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    source_service = SandboxService()
    spec = SessionSpec(runtime=RuntimeType.docker, base_image="python:3.11-slim")
    source = source_service.create_session(
        user_id="user-7",
        spec=spec,
        spec_version="1.0",
        idem_key=None,
        raw_body={"spec_version": "1.0", "runtime": "docker"},
    )
    source_ws = source_service._orch.get_session_workspace_path(source.id)
    assert source_ws is not None
    source_file = Path(str(source_ws)) / "notes.txt"
    source_file.write_text("stateful data", encoding="utf-8")

    restarted_service = SandboxService()
    cloned = restarted_service.clone_session(source.id)
    cloned_ws = restarted_service._orch.get_session_workspace_path(cloned.id)

    assert cloned.id != source.id
    assert cloned_ws is not None
    assert restarted_service._orch.get_session_owner(cloned.id) == "user-7"
    assert (Path(str(cloned_ws)) / "notes.txt").read_text(encoding="utf-8") == "stateful data"


def test_session_execution_defaults_roundtrip_and_clone(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    source_service = SandboxService()
    spec = SessionSpec(
        runtime=RuntimeType.docker,
        base_image="python:3.12-slim",
        cpu_limit=1.5,
        memory_mb=768,
        timeout_sec=77,
        network_policy="deny_all",
        env={"SESSION_TOKEN": "present"},
        labels={"team": "sandbox"},
        trust_level=TrustLevel.untrusted,
        persona_id="persona-77",
        workspace_id="workspace-77",
        workspace_group_id="wg-77",
        scope_snapshot_id="scope-77",
    )
    source = source_service.create_session(
        user_id="user-7",
        spec=spec,
        spec_version="1.0",
        idem_key=None,
        raw_body={"spec_version": "1.0", "runtime": "docker"},
    )

    restarted_service = SandboxService()
    restored = restarted_service._orch.get_session(source.id)
    assert restored is not None
    assert restored.base_image == "python:3.12-slim"
    assert restored.cpu_limit == 1.5
    assert restored.memory_mb == 768
    assert restored.timeout_sec == 77
    assert restored.network_policy == "deny_all"
    assert restored.env == {"SESSION_TOKEN": "present"}
    assert restored.labels == {"team": "sandbox"}
    assert restored.trust_level == TrustLevel.untrusted

    cloned = restarted_service.clone_session(source.id)
    assert cloned.base_image == "python:3.12-slim"
    assert cloned.cpu_limit == 1.5
    assert cloned.memory_mb == 768
    assert cloned.timeout_sec == 77
    assert cloned.network_policy == "deny_all"
    assert cloned.env == {"SESSION_TOKEN": "present"}
    assert cloned.labels == {"team": "sandbox"}
    assert cloned.trust_level == TrustLevel.untrusted


def test_cross_node_delete_invalidates_cached_session_state(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    spec = SessionSpec(runtime=RuntimeType.docker, base_image="python:3.11-slim")
    orch_a = SandboxOrchestrator()
    source = orch_a.create_session(
        user_id="user-55",
        spec=spec,
        spec_version="1.0",
        idem_key=None,
        body={"spec_version": "1.0", "runtime": "docker"},
    )

    orch_b = SandboxOrchestrator()
    assert orch_b.get_session(source.id) is not None
    assert orch_b.get_session_workspace_path(source.id) is not None

    assert orch_a.destroy_session(source.id) is True

    assert orch_b.get_session(source.id) is None
    assert orch_b.get_session_workspace_path(source.id) is None
    with orch_b._lock:
        assert source.id not in orch_b._sessions
        assert source.id not in orch_b._session_roots


def test_destroy_session_cancels_and_drains_when_active_runs_exist(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    orch = SandboxOrchestrator()
    session = orch.create_session(
        user_id="user-66",
        spec=SessionSpec(runtime=RuntimeType.docker, base_image="python:3.11-slim"),
        spec_version="1.0",
        idem_key=None,
        body={"spec_version": "1.0", "runtime": "docker"},
    )
    run = orch.enqueue_run(
        user_id="user-66",
        spec=RunSpec(
            session_id=session.id,
            runtime=RuntimeType.docker,
            base_image="python:3.11-slim",
            command=["python", "-c", "print('queued')"],
        ),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["python", "-c", "print('queued')"], "session_id": session.id},
    )

    svc = SandboxService()
    assert svc.destroy_session(session.id) is True
    killed = orch.get_run(run.id)
    assert killed is not None
    assert killed.phase == RunPhase.killed


def test_destroy_session_cleans_snapshots_artifacts_and_usage(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    svc = SandboxService()
    session = svc.create_session(
        user_id="user-77",
        spec=SessionSpec(runtime=RuntimeType.docker, base_image="python:3.11-slim"),
        spec_version="1.0",
        idem_key=None,
        raw_body={"spec_version": "1.0", "runtime": "docker"},
    )
    ws = svc._orch.get_session_workspace_path(session.id)
    assert ws is not None
    (Path(str(ws)) / "state.txt").write_text("snapshot me", encoding="utf-8")
    snap = svc.create_snapshot(session.id)
    assert snap.get("snapshot_id")

    run = svc._orch.enqueue_run(
        user_id="user-77",
        spec=RunSpec(
            session_id=session.id,
            runtime=RuntimeType.docker,
            base_image="python:3.11-slim",
            command=["python", "-c", "print('queued')"],
        ),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["python", "-c", "print('queued')"], "session_id": session.id},
    )
    svc._orch.store_artifacts(run.id, {"out.txt": b"hello"})
    snapshot_dir = Path(tmp_path) / "snapshots" / session.id
    artifact_dir = svc._orch._artifact_dir("user-77", run.id)  # type: ignore[attr-defined]
    assert snapshot_dir.exists()
    assert artifact_dir.exists()
    assert svc._orch._store.get_user_artifact_bytes("user-77") == 5  # type: ignore[attr-defined]

    assert svc.destroy_session(session.id) is True

    killed = svc._orch.get_run(run.id)
    assert killed is not None
    assert killed.phase == RunPhase.killed
    assert not snapshot_dir.exists()
    assert not artifact_dir.exists()
    assert svc._orch._store.get_user_artifact_bytes("user-77") == 0  # type: ignore[attr-defined]


def test_session_tenancy_metadata_roundtrips_across_orchestrators(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    spec = SessionSpec(
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        persona_id="persona-123",
        workspace_id="workspace-abc",
        workspace_group_id="wg-team-1",
        scope_snapshot_id="scope-v1",
    )
    orch_a = SandboxOrchestrator()
    source = orch_a.create_session(
        user_id="user-88",
        spec=spec,
        spec_version="1.0",
        idem_key=None,
        body={"spec_version": "1.0", "runtime": "docker"},
    )

    assert source.persona_id == "persona-123"
    assert source.workspace_id == "workspace-abc"
    assert source.workspace_group_id == "wg-team-1"
    assert source.scope_snapshot_id == "scope-v1"

    orch_b = SandboxOrchestrator()
    restored = orch_b.get_session(source.id)
    assert restored is not None
    assert restored.persona_id == "persona-123"
    assert restored.workspace_id == "workspace-abc"
    assert restored.workspace_group_id == "wg-team-1"
    assert restored.scope_snapshot_id == "scope-v1"


def test_run_tenancy_metadata_persists_and_lists(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    orch = SandboxOrchestrator()
    spec = RunSpec(
        session_id="session-tenancy-1",
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        command=["python", "-c", "print('ok')"],
        persona_id="persona-xyz",
        workspace_id="workspace-7",
        workspace_group_id="group-A",
        scope_snapshot_id="scope-2026-02-22",
    )
    status = orch.enqueue_run(
        user_id="user-901",
        spec=spec,
        spec_version="1.0",
        idem_key=None,
        body={"command": ["python", "-c", "print('ok')"]},
    )

    stored = orch.get_run(status.id)
    assert stored is not None
    assert stored.session_id == "session-tenancy-1"
    assert stored.persona_id == "persona-xyz"
    assert stored.workspace_id == "workspace-7"
    assert stored.workspace_group_id == "group-A"
    assert stored.scope_snapshot_id == "scope-2026-02-22"

    listed = orch.list_runs(user_id="user-901", limit=500, offset=0)
    row = next((item for item in listed if item.get("id") == status.id), None)
    if row is None:
        raise AssertionError(f"Run {status.id} missing from list_runs(user_id='user-901'): {listed!r}")
    assert row.get("session_id") == "session-tenancy-1"
    assert row.get("persona_id") == "persona-xyz"
    assert row.get("workspace_id") == "workspace-7"
    assert row.get("workspace_group_id") == "group-A"
    assert row.get("scope_snapshot_id") == "scope-2026-02-22"


def test_acp_control_metadata_roundtrips_across_store_instances(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)

    store_a = get_store()
    store_a.put_acp_session_control(
        session_id="acp-session-1",
        user_id="user-500",
        sandbox_session_id="sandbox-session-1",
        run_id="run-1",
        ssh_host="127.0.0.1",
        ssh_port=4122,
        ssh_user="acp",
        ssh_private_key="PRIVATE-KEY",
        persona_id="persona-1",
        workspace_id="workspace-1",
        workspace_group_id="wg-1",
        scope_snapshot_id="scope-1",
    )

    store_b = get_store()
    row = store_b.get_acp_session_control("acp-session-1")
    assert row is not None
    assert row.get("user_id") == "user-500"
    assert row.get("sandbox_session_id") == "sandbox-session-1"
    assert row.get("run_id") == "run-1"
    assert row.get("ssh_user") == "acp"
    assert row.get("persona_id") == "persona-1"
    assert row.get("workspace_id") == "workspace-1"
    assert row.get("workspace_group_id") == "wg-1"
    assert row.get("scope_snapshot_id") == "scope-1"

    assert store_b.delete_acp_session_control("acp-session-1") is True
    assert store_b.get_acp_session_control("acp-session-1") is None
