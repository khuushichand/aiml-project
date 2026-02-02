import json
import hmac
import hashlib

import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.engine import WorkflowEngine, RunMode
from tldw_Server_API.app.core.Security import egress as egress_mod


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_webhook_step_signing_redirect_and_size_limit(monkeypatch, tmp_path):
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setattr(egress_mod, "is_webhook_url_allowed_for_tenant", lambda url, tenant_id: True)

    calls = []
    body = json.dumps({"ok": True}).encode("utf-8")

    class DummyResponse:
        def __init__(self, status_code, headers=None, content=b""):
            self.status_code = status_code
            self.headers = headers or {}
            self._content = content
            self.encoding = "utf-8"

        def read(self):
            return self._content

        def iter_bytes(self):
            yield self._content

        def json(self):
            return json.loads(self._content.decode("utf-8"))

        @property
        def text(self):
            return self._content.decode("utf-8")

        def close(self):
            return None

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, headers=None, content=None, params=None, **kwargs):
            calls.append({"method": method, "url": url, "headers": headers or {}, "content": content})
            if url.endswith("/redirect"):
                return DummyResponse(302, headers={"location": "/final"})
            return DummyResponse(
                200,
                headers={"content-type": "application/json", "content-length": str(len(body))},
                content=body,
            )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Workflows.adapters.integration.webhook._wf_create_client",
        lambda *args, **kwargs: DummyClient(),
    )

    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    definition = {
        "name": "webhook-controls",
        "version": 1,
        "steps": [
            {
                "id": "w1",
                "type": "webhook",
                "config": {
                    "url": "https://example.test/redirect",
                    "method": "POST",
                    "body": {"ok": True},
                    "follow_redirects": True,
                    "max_bytes": 4,
                    "signing": {"type": "hmac-sha256", "secret_ref": "WEBHOOK_SECRET"},
                },
            }
        ],
    }
    run_id = "run-webhook-controls"
    db.create_run(
        run_id=run_id,
        tenant_id="default",
        user_id="user",
        inputs={},
        workflow_id=None,
        definition_version=1,
        definition_snapshot=definition,
    )

    WorkflowEngine.set_run_secrets(run_id, {"WEBHOOK_SECRET": "shhh"})
    engine = WorkflowEngine(db)
    await engine.start_run(run_id, RunMode.SYNC)

    assert len(calls) == 2
    assert calls[0]["url"].endswith("/redirect")
    assert calls[1]["url"].endswith("/final")

    expected_sig = hmac.new(b"shhh", calls[0]["content"].encode("utf-8"), hashlib.sha256).hexdigest()
    assert calls[0]["headers"].get("X-Workflows-Signature") == expected_sig

    run = db.get_run(run_id)
    outputs = json.loads(run.outputs_json or "{}")
    assert outputs.get("error") == "response_too_large"
