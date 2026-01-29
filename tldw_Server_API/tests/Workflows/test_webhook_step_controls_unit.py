import asyncio

import pytest

from tldw_Server_API.app.core.Workflows.adapters import run_webhook_adapter
from tldw_Server_API.app.core.Security import egress as egress_mod


pytestmark = pytest.mark.unit


def test_webhook_step_egress_policy_blocks(monkeypatch):
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setattr(egress_mod, "is_webhook_url_allowed_for_tenant", lambda url, tenant_id: True)

    def _boom(*args, **kwargs):
        raise AssertionError("webhook client should not be created when blocked")

    monkeypatch.setattr("tldw_Server_API.app.core.Workflows.adapters._wf_create_client", _boom)

    cfg = {"url": "https://deny.test/hook", "egress_policy": {"denylist": ["deny.test"]}}
    ctx = {"tenant_id": "default", "user_id": "1"}
    out = asyncio.run(run_webhook_adapter(cfg, ctx))
    assert out.get("dispatched") is False
    assert out.get("error") == "blocked_egress"
