from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.policy import SandboxPolicy, SandboxPolicyConfig
from tldw_Server_API.app.core.Sandbox.models import RunSpec, SessionSpec


def test_policy_clamps_run_resources() -> None:
    cfg = SandboxPolicyConfig(max_cpu=2.0, max_mem_mb=512)
    policy = SandboxPolicy(cfg)
    spec = RunSpec(
        session_id=None,
        runtime=None,
        base_image=None,
        command=["echo", "ok"],
        cpu=4.0,
        memory_mb=1024,
    )
    spec = policy.apply_to_run(spec, firecracker_available=True)
    assert spec.cpu == 2.0
    assert spec.memory_mb == 512


def test_policy_clamps_session_resources() -> None:
    cfg = SandboxPolicyConfig(max_cpu=1.0, max_mem_mb=256)
    policy = SandboxPolicy(cfg)
    spec = SessionSpec(cpu_limit=2.0, memory_mb=1024)
    spec = policy.apply_to_session(spec, firecracker_available=True)
    assert spec.cpu_limit == 1.0
    assert spec.memory_mb == 256
