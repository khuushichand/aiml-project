from __future__ import annotations

from pathlib import Path
import threading

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


def test_artifact_usage_cap_holds_under_concurrent_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_MAX_ARTIFACT_BYTES_PER_USER_MB", "1")

    orch = SandboxOrchestrator()
    run_a = "run-art-concurrent-a"
    run_b = "run-art-concurrent-b"
    orch._store.put_run("user-1", RunStatus(id=run_a, phase=RunPhase.completed))
    orch._store.put_run("user-1", RunStatus(id=run_b, phase=RunPhase.completed))

    original_get = orch._store.get_user_artifact_bytes
    barrier = threading.Barrier(2)

    def _synchronized_get(user_id: str) -> int:
        value = original_get(user_id)
        try:
            barrier.wait(timeout=1.0)
        except threading.BrokenBarrierError:
            pass
        return value

    monkeypatch.setattr(orch._store, "get_user_artifact_bytes", _synchronized_get)

    errors: list[BaseException] = []

    def _worker(run_id: str, payload: bytes) -> None:
        try:
            orch.store_artifacts(run_id, {"out.txt": payload})
        except BaseException as exc:  # pragma: no cover - assertion capture path
            errors.append(exc)

    payload = b"x" * (700 * 1024)
    thread_a = threading.Thread(target=_worker, args=(run_a, payload))
    thread_b = threading.Thread(target=_worker, args=(run_b, payload))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=2.0)
    thread_b.join(timeout=2.0)

    assert not thread_a.is_alive()
    assert not thread_b.is_alive()
    assert errors == []

    cap_bytes = 1 * 1024 * 1024
    used = original_get("user-1")
    total_persisted = sum(
        orch.list_artifacts(run_id).get("out.txt", 0)
        for run_id in (run_a, run_b)
    )

    assert used <= cap_bytes
    assert total_persisted <= cap_bytes
    assert any(
        orch.list_artifacts(run_id).get("out.txt", 0) == 0
        for run_id in (run_a, run_b)
    )
