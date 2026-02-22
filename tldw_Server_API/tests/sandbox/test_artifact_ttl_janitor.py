from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import clear_config_cache, settings as app_settings
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunStatus
from tldw_Server_API.app.core.Sandbox.orchestrator import SandboxOrchestrator

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


def test_artifact_ttl_janitor_removes_expired_artifacts_and_decrements_usage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_ARTIFACT_TTL_HOURS", "1")
    monkeypatch.setenv("SANDBOX_ARTIFACT_JANITOR_INTERVAL_SEC", "0")

    now = datetime.now(timezone.utc)
    old_finished = now - timedelta(hours=3)

    orch = SandboxOrchestrator()

    old_run_id = "run-old-artifacts"
    new_run_id = "run-new-artifacts"
    orch._store.put_run(  # type: ignore[attr-defined]
        "user-1",
        RunStatus(
            id=old_run_id,
            phase=RunPhase.completed,
            started_at=old_finished,
            finished_at=old_finished,
        ),
    )
    orch._store.put_run(  # type: ignore[attr-defined]
        "user-1",
        RunStatus(
            id=new_run_id,
            phase=RunPhase.completed,
            started_at=now,
            finished_at=now,
        ),
    )

    orch.store_artifacts(old_run_id, {"old.txt": b"12345"})
    orch.store_artifacts(new_run_id, {"new.txt": b"12"})
    assert orch._store.get_user_artifact_bytes("user-1") == 7  # type: ignore[attr-defined]

    summary = orch.prune_expired_artifacts(force=True, now_utc=now)
    assert summary["removed_runs"] == 1
    assert summary["removed_files"] == 1
    assert summary["removed_bytes"] == 5

    assert orch._store.get_user_artifact_bytes("user-1") == 2  # type: ignore[attr-defined]
    assert orch.list_artifacts(old_run_id) == {}
    assert orch.get_artifact(old_run_id, "old.txt") is None
    assert orch.list_artifacts(new_run_id).get("new.txt") == 2
