from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import clear_config_cache, settings as app_settings
from tldw_Server_API.app.core.Sandbox.orchestrator import SandboxOrchestrator
from tldw_Server_API.app.core.Sandbox.models import RunStatus, RunPhase


def _configure_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "sandbox_store.db")
    shared_artifacts_dir = str(tmp_path / "sandbox_artifacts")
    monkeypatch.setenv("SANDBOX_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SANDBOX_STORE_DB_PATH", db_path)
    monkeypatch.setenv("SANDBOX_SHARED_ARTIFACTS_DIR", shared_artifacts_dir)
    if hasattr(app_settings, "SANDBOX_STORE_BACKEND"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_BACKEND", "sqlite")
    if hasattr(app_settings, "SANDBOX_STORE_DB_PATH"):
        monkeypatch.setattr(app_settings, "SANDBOX_STORE_DB_PATH", db_path)
    if hasattr(app_settings, "SANDBOX_SHARED_ARTIFACTS_DIR"):
        monkeypatch.setattr(app_settings, "SANDBOX_SHARED_ARTIFACTS_DIR", shared_artifacts_dir)
    clear_config_cache()


def test_artifact_usage_bytes_incremented(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    orch = SandboxOrchestrator()
    # Seed a run with an owner in the store
    run_id = "run-art-1"
    status = RunStatus(id=run_id, phase=RunPhase.completed)
    orch._store.put_run("user-1", status)

    orch.store_artifacts(run_id, {"out.txt": b"hello"})
    used = orch._store.get_user_artifact_bytes("user-1")
    assert used == 5
