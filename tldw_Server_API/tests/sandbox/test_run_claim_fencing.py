from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import clear_config_cache, settings as app_settings
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunSpec, RuntimeType
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


def _enqueue(orch: SandboxOrchestrator, *, user_id: str, command: str) -> str:
    status = orch.enqueue_run(
        user_id=user_id,
        spec=RunSpec(
            session_id=None,
            runtime=RuntimeType.docker,
            base_image="python:3.11-slim",
            command=["echo", command],
        ),
        spec_version="1.0",
        idem_key=None,
        body={"command": ["echo", command]},
    )
    return status.id


def test_claim_fencing_allows_single_worker_across_orchestrators(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "120")

    orch_a = SandboxOrchestrator()
    orch_b = SandboxOrchestrator()
    run_id = _enqueue(orch_a, user_id="claim-user", command="claim-1")

    claimed_a = orch_a.try_claim_run(run_id, worker_id="worker-a", lease_seconds=30)
    claimed_b = orch_b.try_claim_run(run_id, worker_id="worker-b", lease_seconds=30)

    assert claimed_a is not None
    assert claimed_a.claim_owner == "worker-a"
    assert claimed_b is None

    stored = orch_b.get_run(run_id)
    assert stored is not None
    assert stored.claim_owner == "worker-a"
    assert stored.claim_expires_at is not None


def test_claim_fencing_allows_takeover_after_lease_expiry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "120")

    orch_a = SandboxOrchestrator()
    orch_b = SandboxOrchestrator()
    run_id = _enqueue(orch_a, user_id="claim-user", command="claim-2")

    claimed_a = orch_a.try_claim_run(run_id, worker_id="worker-a", lease_seconds=1)
    assert claimed_a is not None

    immediate_b = orch_b.try_claim_run(run_id, worker_id="worker-b", lease_seconds=30)
    assert immediate_b is None

    time.sleep(1.15)
    claimed_b = orch_b.try_claim_run(run_id, worker_id="worker-b", lease_seconds=30)
    assert claimed_b is not None
    assert claimed_b.claim_owner == "worker-b"


def test_claim_release_and_renew_require_current_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "120")

    orch = SandboxOrchestrator()
    run_id = _enqueue(orch, user_id="claim-user", command="claim-3")

    claimed = orch.try_claim_run(run_id, worker_id="worker-a", lease_seconds=10)
    assert claimed is not None
    assert claimed.claim_owner == "worker-a"

    assert orch.renew_run_claim(run_id, worker_id="worker-b", lease_seconds=20) is False
    assert orch.renew_run_claim(run_id, worker_id="worker-a", lease_seconds=20) is True

    assert orch.release_run_claim(run_id, worker_id="worker-b") is False
    assert orch.release_run_claim(run_id, worker_id="worker-a") is True

    claimed_again = orch.try_claim_run(run_id, worker_id="worker-b", lease_seconds=10)
    assert claimed_again is not None
    assert claimed_again.claim_owner == "worker-b"


def test_claim_fencing_concurrent_race_allows_single_winner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "120")

    orch_a = SandboxOrchestrator()
    orch_b = SandboxOrchestrator()
    run_id = _enqueue(orch_a, user_id="claim-user", command="claim-4")

    gate = threading.Barrier(3)
    outcomes: dict[str, bool] = {}

    def _contend(name: str, orch: SandboxOrchestrator, worker_id: str) -> None:
        gate.wait(timeout=5)
        claimed = orch.try_claim_run(run_id, worker_id=worker_id, lease_seconds=30)
        outcomes[name] = claimed is not None

    t1 = threading.Thread(target=_contend, args=("a", orch_a, "worker-a"), daemon=True)
    t2 = threading.Thread(target=_contend, args=("b", orch_b, "worker-b"), daemon=True)
    t1.start()
    t2.start()
    gate.wait(timeout=5)
    t1.join(timeout=5)
    t2.join(timeout=5)

    winners = [name for name, won in outcomes.items() if won]
    assert len(winners) == 1

    stored = orch_a.get_run(run_id)
    assert stored is not None
    assert stored.claim_owner in {"worker-a", "worker-b"}


def test_start_admission_respects_active_run_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_sqlite_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SANDBOX_QUEUE_MAX_LENGTH", "10")
    monkeypatch.setenv("SANDBOX_QUEUE_TTL_SEC", "120")

    orch_a = SandboxOrchestrator()
    orch_b = SandboxOrchestrator()
    run_a = _enqueue(orch_a, user_id="claim-user", command="start-admit-a")
    run_b = _enqueue(orch_b, user_id="claim-user", command="start-admit-b")

    assert orch_a.try_claim_run(run_a, worker_id="worker-a", lease_seconds=30) is not None
    assert orch_b.try_claim_run(run_b, worker_id="worker-b", lease_seconds=30) is not None

    admitted_a = orch_a.try_admit_run_start(
        run_a,
        worker_id="worker-a",
        max_active_runs=1,
        lease_seconds=30,
    )
    admitted_b = orch_b.try_admit_run_start(
        run_b,
        worker_id="worker-b",
        max_active_runs=1,
        lease_seconds=30,
    )

    assert admitted_a is not None
    assert admitted_a.phase == RunPhase.starting
    assert admitted_a.started_at is not None
    assert admitted_b is None

    first = orch_a.get_run(run_a)
    assert first is not None
    first.phase = RunPhase.completed
    first.exit_code = 0
    first.finished_at = datetime.now(timezone.utc)
    orch_a.update_run(run_a, first)

    admitted_b_after = orch_b.try_admit_run_start(
        run_b,
        worker_id="worker-b",
        max_active_runs=1,
        lease_seconds=30,
    )
    assert admitted_b_after is not None
    assert admitted_b_after.phase == RunPhase.starting
