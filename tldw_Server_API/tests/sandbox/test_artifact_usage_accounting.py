from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.orchestrator import SandboxOrchestrator
from tldw_Server_API.app.core.Sandbox.models import RunStatus, RunPhase


def test_artifact_usage_bytes_incremented() -> None:
    orch = SandboxOrchestrator()
    # Seed a run with an owner in the store
    run_id = "run-art-1"
    status = RunStatus(id=run_id, phase=RunPhase.completed)
    orch._store.put_run("user-1", status)

    orch.store_artifacts(run_id, {"out.txt": b"hello"})
    used = orch._store.get_user_artifact_bytes("user-1")
    assert used == 5
