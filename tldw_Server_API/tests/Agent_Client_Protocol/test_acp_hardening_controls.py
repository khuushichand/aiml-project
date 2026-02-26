import importlib.machinery
import sys
import types

import pytest

pytestmark = pytest.mark.unit


# Stub heavyweight audio deps before app import in shared fixtures.
if "torch" not in sys.modules:
    _fake_torch = types.ModuleType("torch")
    _fake_torch.__spec__ = importlib.machinery.ModuleSpec("torch", loader=None)
    _fake_torch.Tensor = object
    _fake_torch.nn = types.SimpleNamespace(Module=object)
    sys.modules["torch"] = _fake_torch

if "faster_whisper" not in sys.modules:
    _fake_fw = types.ModuleType("faster_whisper")
    _fake_fw.__spec__ = importlib.machinery.ModuleSpec("faster_whisper", loader=None)

    class _StubWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

    _fake_fw.WhisperModel = _StubWhisperModel
    _fake_fw.BatchedInferencePipeline = _StubWhisperModel
    sys.modules["faster_whisper"] = _fake_fw

if "transformers" not in sys.modules:
    _fake_tf = types.ModuleType("transformers")
    _fake_tf.__spec__ = importlib.machinery.ModuleSpec("transformers", loader=None)

    class _StubProcessor:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    class _StubModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    _fake_tf.AutoProcessor = _StubProcessor
    _fake_tf.Qwen2AudioForConditionalGeneration = _StubModel
    sys.modules["transformers"] = _fake_tf


class _StubUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class _StubSessionRecord:
    def __init__(self) -> None:
        self.session_id = "session-123"
        self.user_id = 1
        self.agent_type = "codex"
        self.name = "Hardening Session"
        self.status = "active"
        self.created_at = "2026-02-26T00:00:00+00:00"
        self.last_activity_at = "2026-02-26T00:05:00+00:00"
        self.message_count = 3
        self.tags = ["hardening"]
        self.persona_id = "persona-abc"
        self.workspace_id = "ws-1"
        self.workspace_group_id = "wsg-2"
        self.scope_snapshot_id = "scope-3"
        self.cwd = "/tmp/test-project"
        self.messages = [
            {
                "role": "assistant",
                "content": {
                    "error_type": "acp_timeout",
                    "error": "operation timed out waiting for runner",
                    "diagnostic_uri": "diag://timeout/1",
                },
                "timestamp": "2026-02-26T00:00:01+00:00",
            },
            {
                "role": "assistant",
                "content": {
                    "error_type": "acp_governance_blocked",
                    "message": "access_token should never leak",
                },
                "timestamp": "2026-02-26T00:00:02+00:00",
            },
        ]
        self.usage = _StubUsage(prompt_tokens=10, completion_tokens=20)

    def to_info_dict(self, *, has_websocket: bool = False) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "message_count": self.message_count,
            "usage": self.usage.to_dict(),
            "tags": list(self.tags),
            "has_websocket": has_websocket,
            "persona_id": self.persona_id,
            "workspace_id": self.workspace_id,
            "workspace_group_id": self.workspace_group_id,
            "scope_snapshot_id": self.scope_snapshot_id,
        }


class _StubSessionStore:
    def __init__(self) -> None:
        self.record = _StubSessionRecord()

    async def get_session(self, session_id: str):
        if session_id != self.record.session_id:
            return None
        return self.record

    async def close_session(self, session_id: str) -> None:
        if session_id == self.record.session_id:
            self.record.status = "closed"

    async def list_sessions(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        if user_id is not None and int(user_id) != 1:
            return [], 0
        return [self.record], 1


class _StubRunnerClient:
    def __init__(self) -> None:
        self.cancel_calls: list[str] = []
        self.close_calls: list[str] = []

    async def verify_session_access(self, session_id: str, user_id: int) -> bool:
        return session_id == "session-123" and int(user_id) == 1

    async def cancel(self, session_id: str) -> None:
        self.cancel_calls.append(session_id)

    async def close_session(self, session_id: str) -> None:
        self.close_calls.append(session_id)

    def has_websocket_connections(self, session_id: str) -> bool:
        return False

    def pop_updates(self, session_id: str, limit: int = 100):
        return []


@pytest.fixture()
def stub_acp_hardening(monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.agent_client_protocol as acp_endpoints

    store = _StubSessionStore()
    runner = _StubRunnerClient()

    async def _get_store():
        return store

    async def _get_runner():
        return runner

    monkeypatch.setattr(acp_endpoints, "get_acp_session_store", _get_store)
    monkeypatch.setattr(acp_endpoints, "get_runner_client", _get_runner)

    with acp_endpoints._ACP_AUDIT_LOCK:
        acp_endpoints._ACP_AUDIT_EVENTS.clear()
    with acp_endpoints._ACP_RECONCILIATION_LOCK:
        acp_endpoints._ACP_RECONCILIATION.clear()
    with acp_endpoints._ACP_CONTROL_RATE_LIMITER._lock:
        acp_endpoints._ACP_CONTROL_RATE_LIMITER._windows.clear()

    return store, runner, acp_endpoints


def test_acp_teardown_and_reconciliation(client_user_only, stub_acp_hardening):
    teardown = client_user_only.post("/api/v1/acp/sessions/session-123/teardown")
    assert teardown.status_code == 200
    payload = teardown.json()
    assert payload["reconciliation"]["status"] == "teardown_completed"

    recon = client_user_only.get("/api/v1/acp/sessions/session-123/reconciliation")
    assert recon.status_code == 200
    assert recon.json()["reconciliation"]["status"] == "teardown_completed"


def test_acp_diagnostics_normalization(client_user_only, stub_acp_hardening):
    response = client_user_only.get("/api/v1/acp/sessions/session-123/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    reason_codes = {item["reason_code"] for item in payload["diagnostics"]}
    assert "timed_out" in reason_codes
    assert "blocked" in reason_codes
    assert any(item["message"] == "Diagnostic message redacted (sensitive content)" for item in payload["diagnostics"])


def test_acp_audit_records_control_actions(client_user_only, stub_acp_hardening):
    cancel = client_user_only.post(
        "/api/v1/acp/sessions/cancel",
        json={"session_id": "session-123"},
    )
    assert cancel.status_code == 200

    audit = client_user_only.get("/api/v1/acp/sessions/session-123/audit")
    assert audit.status_code == 200
    actions = [entry["action"] for entry in audit.json()["events"]]
    assert "cancel" in actions


def test_acp_control_surface_rate_limit(client_user_only, stub_acp_hardening, monkeypatch):
    store, _runner, acp_endpoints = stub_acp_hardening
    assert store.record.session_id == "session-123"
    monkeypatch.setenv("ACP_CONTROL_RATE_LIMIT_PER_MINUTE", "1")

    with acp_endpoints._ACP_CONTROL_RATE_LIMITER._lock:
        acp_endpoints._ACP_CONTROL_RATE_LIMITER._windows.clear()

    first = client_user_only.get("/api/v1/acp/sessions/session-123/usage")
    second = client_user_only.get("/api/v1/acp/sessions/session-123/usage")

    assert first.status_code == 200
    assert second.status_code == 429
    detail = second.json()["detail"]
    assert detail["code"] == "rate_limited"
