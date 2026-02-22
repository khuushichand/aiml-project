import importlib.machinery
import sys
import types

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPResponseError

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


class StubRunnerClient:
    def __init__(self) -> None:
        self.agent_capabilities = {"promptCapabilities": {"image": False}}
        self.cancelled = []
        self.closed = []
        self.prompt_calls = []
        self.create_session_calls = []
        self.denied_sessions = set()
        self._updates = {
            "session-123": [
                {"sessionId": "session-123", "event": "message", "content": "hello"}
            ]
        }

    async def create_session(
        self,
        cwd: str,
        mcp_servers=None,
        agent_type: str | None = None,
        user_id: int | None = None,
        persona_id: str | None = None,
        workspace_id: str | None = None,
        workspace_group_id: str | None = None,
        scope_snapshot_id: str | None = None,
    ) -> str:
        self.create_session_calls.append(
            {
                "cwd": cwd,
                "mcp_servers": mcp_servers,
                "agent_type": agent_type,
                "user_id": user_id,
                "persona_id": persona_id,
                "workspace_id": workspace_id,
                "workspace_group_id": workspace_group_id,
                "scope_snapshot_id": scope_snapshot_id,
            }
        )
        return "session-123"

    async def verify_session_access(self, session_id: str, user_id: int) -> bool:
        return session_id not in self.denied_sessions

    async def prompt(self, session_id: str, prompt):
        self.prompt_calls.append((session_id, prompt))
        return {"stopReason": "end", "detail": "ok"}

    async def cancel(self, session_id: str) -> None:
        self.cancelled.append(session_id)

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)

    def pop_updates(self, session_id: str, limit: int = 100):
        updates = list(self._updates.get(session_id, []))
        return updates[:limit]


@pytest.fixture()
def stub_runner_client(monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.agent_client_protocol as acp_endpoints

    stub = StubRunnerClient()

    async def _get_runner_client():
        return stub

    monkeypatch.setattr(acp_endpoints, "get_runner_client", _get_runner_client)
    return stub


def test_acp_session_new_success(client_user_only, stub_runner_client, tmp_path):
    resp = client_user_only.post(
        "/api/v1/acp/sessions/new",
        json={"cwd": str(tmp_path)},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["session_id"] == "session-123"
    assert payload["agent_capabilities"] == {"promptCapabilities": {"image": False}}
    assert stub_runner_client.create_session_calls
    assert isinstance(stub_runner_client.create_session_calls[0]["user_id"], int)


def test_acp_session_new_forwards_tenancy_fields(client_user_only, stub_runner_client, tmp_path):
    resp = client_user_only.post(
        "/api/v1/acp/sessions/new",
        json={
            "cwd": str(tmp_path),
            "agent_type": "codex",
            "persona_id": "persona-abc",
            "workspace_id": "ws-1",
            "workspace_group_id": "wsg-2",
            "scope_snapshot_id": "scope-3",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["persona_id"] == "persona-abc"
    assert payload["workspace_id"] == "ws-1"
    assert payload["workspace_group_id"] == "wsg-2"
    assert payload["scope_snapshot_id"] == "scope-3"
    call = stub_runner_client.create_session_calls[-1]
    assert call["agent_type"] == "codex"
    assert call["persona_id"] == "persona-abc"
    assert call["workspace_id"] == "ws-1"
    assert call["workspace_group_id"] == "wsg-2"
    assert call["scope_snapshot_id"] == "scope-3"
    assert isinstance(call["user_id"], int) and call["user_id"] > 0


def test_acp_session_prompt_success(client_user_only, stub_runner_client):
    resp = client_user_only.post(
        "/api/v1/acp/sessions/prompt",
        json={"session_id": "session-123", "prompt": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stop_reason"] == "end"
    assert payload["raw_result"]["detail"] == "ok"
    assert stub_runner_client.prompt_calls


def test_acp_session_cancel_and_close(client_user_only, stub_runner_client):
    cancel = client_user_only.post(
        "/api/v1/acp/sessions/cancel",
        json={"session_id": "session-123"},
    )
    assert cancel.status_code == 200
    assert stub_runner_client.cancelled == ["session-123"]

    close = client_user_only.post(
        "/api/v1/acp/sessions/close",
        json={"session_id": "session-123"},
    )
    assert close.status_code == 200
    assert stub_runner_client.closed == ["session-123"]


def test_acp_session_updates(client_user_only, stub_runner_client):
    resp = client_user_only.get("/api/v1/acp/sessions/session-123/updates")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["updates"] == [
        {"sessionId": "session-123", "event": "message", "content": "hello"}
    ]


def test_acp_session_new_error(client_user_only, monkeypatch, tmp_path):
    import tldw_Server_API.app.api.v1.endpoints.agent_client_protocol as acp_endpoints

    class ErrorRunnerClient(StubRunnerClient):
        async def create_session(
            self,
            cwd: str,
            mcp_servers=None,
            agent_type: str | None = None,
            user_id: int | None = None,
            persona_id: str | None = None,
            workspace_id: str | None = None,
            workspace_group_id: str | None = None,
            scope_snapshot_id: str | None = None,
        ) -> str:
            raise ACPResponseError("boom")

    async def _get_runner_client():
        return ErrorRunnerClient()

    monkeypatch.setattr(acp_endpoints, "get_runner_client", _get_runner_client)

    resp = client_user_only.post(
        "/api/v1/acp/sessions/new",
        json={"cwd": str(tmp_path)},
    )
    assert resp.status_code == 502
    assert resp.json()["detail"] == "boom"


def test_acp_session_prompt_denied_for_unowned_session(client_user_only, stub_runner_client):
    stub_runner_client.denied_sessions.add("session-999")
    resp = client_user_only.post(
        "/api/v1/acp/sessions/prompt",
        json={"session_id": "session-999", "prompt": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"


def test_acp_session_updates_denied_for_unowned_session(client_user_only, stub_runner_client):
    stub_runner_client.denied_sessions.add("session-999")
    resp = client_user_only.get("/api/v1/acp/sessions/session-999/updates")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"
