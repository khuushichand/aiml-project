from __future__ import annotations

import tldw_Server_API.app.core.Sandbox.policy as policy_module

from tldw_Server_API.app.core.Sandbox.models import RuntimeType
from tldw_Server_API.app.core.Sandbox.policy import SandboxPolicyConfig


def test_policy_config_reads_lima_default_runtime(monkeypatch) -> None:
    monkeypatch.setattr(policy_module.app_settings, "SANDBOX_DEFAULT_RUNTIME", "lima", raising=False)
    cfg = SandboxPolicyConfig.from_settings()
    assert cfg.default_runtime == RuntimeType.lima
