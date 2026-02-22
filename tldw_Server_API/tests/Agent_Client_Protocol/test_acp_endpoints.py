import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPResponseError

pytestmark = pytest.mark.unit


class StubRunnerClient:
    def __init__(self) -> None:
        self.agent_capabilities = {"promptCapabilities": {"image": False}}
        self.cancelled = []
        self.closed = []
        self.prompt_calls = []
        self.denied_sessions = set()
        self._updates = {
            "session-123": [
                {"sessionId": "session-123", "event": "message", "content": "hello"}
            ]
        }

    async def create_session(self, cwd: str, mcp_servers=None) -> str:
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


def test_acp_session_new_success(client_user_only, stub_runner_client):
    resp = client_user_only.post(
        "/api/v1/acp/sessions/new",
        json={"cwd": "/tmp"},  # nosec B108
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["session_id"] == "session-123"
    assert payload["agent_capabilities"] == {"promptCapabilities": {"image": False}}


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


def test_acp_session_new_error(client_user_only, monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.agent_client_protocol as acp_endpoints

    class ErrorRunnerClient(StubRunnerClient):
        async def create_session(self, cwd: str, mcp_servers=None) -> str:
            raise ACPResponseError("boom")

    async def _get_runner_client():
        return ErrorRunnerClient()

    monkeypatch.setattr(acp_endpoints, "get_runner_client", _get_runner_client)

    resp = client_user_only.post(
        "/api/v1/acp/sessions/new",
        json={"cwd": "/tmp"},  # nosec B108
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
