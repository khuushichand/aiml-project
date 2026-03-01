from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import clear_config_cache, settings as app_settings
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunStatus
from tldw_Server_API.app.core.Sandbox.orchestrator import SandboxOrchestrator

pytestmark = pytest.mark.unit


def _configure_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "sandbox_store.db")
    root_dir = str(tmp_path / "sandbox_root")
    shared_artifacts_dir = str(tmp_path / "sandbox_artifacts")
    snapshot_dir = str(tmp_path / "snapshots")
    monkeypatch.setenv("SANDBOX_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SANDBOX_STORE_DB_PATH", db_path)
    monkeypatch.setenv("SANDBOX_ROOT_DIR", root_dir)
    monkeypatch.setenv("SANDBOX_SHARED_ARTIFACTS_DIR", shared_artifacts_dir)
    monkeypatch.setenv("SANDBOX_SNAPSHOT_PATH", snapshot_dir)
    if hasattr(app_settings, "SANDBOX_STORE_BACKEND"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_BACKEND", "sqlite")
    if hasattr(app_settings, "SANDBOX_STORE_DB_PATH"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_DB_PATH", db_path)
    if hasattr(app_settings, "SANDBOX_ROOT_DIR"):
        monkeypatch.setattr(app_settings, "SANDBOX_ROOT_DIR", root_dir)
    if hasattr(app_settings, "SANDBOX_SHARED_ARTIFACTS_DIR"):
        monkeypatch.setattr(app_settings, "SANDBOX_SHARED_ARTIFACTS_DIR", shared_artifacts_dir)
    if hasattr(app_settings, "SANDBOX_SNAPSHOT_PATH"):
        monkeypatch.setattr(app_settings, "SANDBOX_SNAPSHOT_PATH", snapshot_dir)
    clear_config_cache()


def test_reconcile_artifact_usage_corrects_store_vs_disk_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_ARTIFACT_JANITOR_INTERVAL_SEC", "0")

    orch = SandboxOrchestrator()
    now = datetime.now(timezone.utc)

    run_id = "run-reconcile-1"
    orch._store.put_run(  # type: ignore[attr-defined]
        "user-1",
        RunStatus(
            id=run_id,
            phase=RunPhase.completed,
            started_at=now,
            finished_at=now,
        ),
    )
    orch.store_artifacts(run_id, {"out.txt": b"hello"})
    user_artifact_dir = (
        Path(str(tmp_path / "sandbox_artifacts"))
        / "user-1"
        / "runs"
        / run_id
        / "artifacts"
    )
    disk_user1_bytes = sum(
        int(path.stat().st_size)
        for path in user_artifact_dir.rglob("*")
        if path.is_file()
    )
    assert orch._store.get_user_artifact_bytes("user-1") == disk_user1_bytes  # type: ignore[attr-defined]

    orch._store.increment_user_artifact_bytes("user-1", 9)  # type: ignore[attr-defined]
    orch._store.increment_user_artifact_bytes("user-ghost", 7)  # type: ignore[attr-defined]
    assert orch._store.get_user_artifact_bytes("user-1") == 14  # type: ignore[attr-defined]
    assert orch._store.get_user_artifact_bytes("user-ghost") == 7  # type: ignore[attr-defined]

    summary = orch.reconcile_artifact_usage()
    assert summary["corrected_users"] >= 2
    assert summary["corrected_bytes"] >= 16

    assert orch._store.get_user_artifact_bytes("user-1") == disk_user1_bytes  # type: ignore[attr-defined]
    assert orch._store.get_user_artifact_bytes("user-ghost") == 0  # type: ignore[attr-defined]
