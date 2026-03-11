from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunSpec, RunStatus, RuntimeType, TrustLevel
from tldw_Server_API.app.core.Sandbox.policy import SandboxPolicy
from tldw_Server_API.app.core.Sandbox.service import SandboxService


def test_execute_single_runtime_scaffold_marks_policy_failures(monkeypatch) -> None:
    svc = SandboxService()
    status = RunStatus(id="run-1", phase=RunPhase.queued, runtime=RuntimeType.seatbelt)
    admitted = RunStatus(id="run-1", phase=RunPhase.starting, runtime=RuntimeType.seatbelt)
    updates: list[tuple[str, RunStatus]] = []

    def _fake_apply(target: RunStatus, source: RunStatus) -> None:
        target.phase = source.phase

    monkeypatch.setattr(svc, "_admit_run_starting", lambda run_id: admitted)
    monkeypatch.setattr(svc, "_apply_admitted_status", _fake_apply)
    monkeypatch.setattr(svc, "_run_with_claim_lease", lambda run_id, fn: fn())
    monkeypatch.setattr(svc._orch, "update_run", lambda run_id, state: updates.append((run_id, state)))

    def _raise_policy(run_id: str, spec: RunSpec, workspace_path: str | None):
        del run_id, spec, workspace_path
        raise SandboxPolicy.PolicyUnsupported(
            RuntimeType.seatbelt,
            requirement="standard",
            reasons=["seatbelt_standard_disabled"],
        )

    result = svc._execute_single_runtime_scaffold(
        status=status,
        spec=RunSpec(
            session_id=None,
            runtime=RuntimeType.seatbelt,
            base_image="host-local",
            command=["echo", "ok"],
            trust_level=TrustLevel.standard,
        ),
        workspace_path=None,
        start_run_fn=_raise_policy,
        policy_failed_reason="seatbelt_policy_failed",
        failed_reason="seatbelt_failed",
        policy_exceptions=(SandboxPolicy.RuntimeUnavailable, SandboxPolicy.PolicyUnsupported),
    )

    assert result.phase == RunPhase.failed
    assert result.message == "seatbelt_policy_failed"
    assert updates[-1][0] == "run-1"
