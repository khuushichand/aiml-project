import base64
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB, SemanticMemory
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Persona.session_manager import SessionManager
from tldw_Server_API.app.main import app as fastapi_app


pytestmark = pytest.mark.unit


def _recv_until(client, predicate, timeout=2.0):

    import time

    start = time.time()
    while time.time() - start < timeout:
        msg = client.receive_text()
        try:
            data = json.loads(msg)
        except Exception:
            continue
        if predicate(data):
            return data
    raise AssertionError("Expected event not received in time")


@pytest.fixture(autouse=True)
def _mock_persona_auth(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    async def _fake_resolve(*args, **kwargs):
        return "1", True, True

    monkeypatch.setattr(persona_ep, "_resolve_authenticated_user_id", _fake_resolve)


def _seed_personalization_db(tmp_path, monkeypatch, *, user_id: str, enabled: bool) -> PersonalizationDB:
    base = tmp_path / "user_db"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))
    path = DatabasePaths.get_personalization_db_path(int(user_id))
    db = PersonalizationDB(str(path))
    db.update_profile(user_id, enabled=1 if enabled else 0)
    return db


def test_persona_websocket_plan_and_confirm(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    class _FakeServer:
        def __init__(self):
            self.initialized = True

        async def initialize(self):
            self.initialized = True

        async def handle_http_request(self, request, user_id=None, metadata=None):
            return SimpleNamespace(error=None, result={"ok": True, "tool": request.params.get("name")})

    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: _FakeServer())

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            # Initial notice
            init = json.loads(ws.receive_text())
            assert init.get("event") in {"notice", "assistant_delta"}

            session_id = "sess_basic"
            # Send a user message that triggers plan with ingest_url
            ws.send_text(
                json.dumps(
                    {"type": "user_message", "session_id": session_id, "text": "https://example.com"}
                )
            )

            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            assert "steps" in plan and isinstance(plan["steps"], list)
            steps = plan["steps"]
            plan_id = plan.get("plan_id")
            assert plan_id
            assert plan.get("session_id") == session_id

            # Approve first step to trigger tool_call/result
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan_id,
                        "approved_steps": [steps[0]["idx"]],
                    }
                )
            )

            # Expect at least a tool_call and tool_result (result may be error in scaffold)
            evt_call = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            assert "step_idx" in evt_call
            assert evt_call.get("tool") == steps[0]["tool"]
            evt_res = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            assert "step_idx" in evt_res


def test_persona_confirm_plan_ignores_client_supplied_steps():

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())

            session_id = "sess_tamper"
            ws.send_text(json.dumps({"type": "user_message", "session_id": session_id, "text": "hello"}))
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            plan_id = plan["plan_id"]
            expected_tool = plan["steps"][0]["tool"]

            # Malicious client payload should be ignored; server executes stored plan only.
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan_id,
                        "approved_steps": [0],
                        "steps": [
                            {"idx": 0, "tool": "delete_everything", "args": {"confirm": True}},
                        ],
                    }
                )
            )

            evt_call = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            assert evt_call.get("tool") == expected_tool
            assert evt_call.get("tool") != "delete_everything"


def test_persona_confirm_plan_rejects_session_mismatch():

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())

            ws.send_text(
                json.dumps(
                    {"type": "user_message", "session_id": "sess_a", "text": "https://example.com"}
                )
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            plan_id = plan["plan_id"]

            # Confirm against a different session id should fail lookup.
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": "sess_b",
                        "plan_id": plan_id,
                        "approved_steps": [0],
                    }
                )
            )

            notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice" and "Invalid plan_id/session_id" in str(d.get("message")),
            )
            assert notice.get("level") == "error"


def test_persona_stream_rejects_missing_credentials(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    async def _unauthenticated(*args, **kwargs):
        return None, False, False

    monkeypatch.setattr(persona_ep, "_resolve_authenticated_user_id", _unauthenticated)

    with TestClient(fastapi_app) as c:
        try:
            with c.websocket_connect("/api/v1/persona/stream") as ws:
                with pytest.raises(WebSocketDisconnect):
                    ws.receive_text()
        except WebSocketDisconnect:
            # Depending on server/client handshake timing, disconnect can happen
            # during connect instead of first receive.
            pass


def test_persona_cancel_clears_pending_plan():

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            session_id = "sess_cancel"

            ws.send_text(
                json.dumps(
                    {"type": "user_message", "session_id": session_id, "text": "https://example.com"}
                )
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            plan_id = plan["plan_id"]

            ws.send_text(
                json.dumps(
                    {"type": "cancel", "session_id": session_id, "reason": "user changed mind"}
                )
            )
            cancelled_notice = _recv_until(
                ws, lambda d: d.get("event") == "notice" and "Cancelled pending work" in str(d.get("message"))
            )
            assert cancelled_notice.get("session_id") == session_id

            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan_id,
                        "approved_steps": [0],
                    }
                )
            )
            invalid_notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice" and "Invalid plan_id/session_id" in str(d.get("message")),
            )
            assert invalid_notice.get("level") == "error"


def test_persona_respects_max_tool_steps(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    monkeypatch.setattr(persona_ep, "_get_persona_max_tool_steps", lambda: 1)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            session_id = "sess_max_steps"

            ws.send_text(
                json.dumps(
                    {"type": "user_message", "session_id": session_id, "text": "https://example.com"}
                )
            )
            _ = _recv_until(
                ws,
                lambda d: d.get("event") == "notice" and "Plan truncated" in str(d.get("message")),
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            assert len(plan.get("steps", [])) == 1


def test_persona_tool_call_attaches_audit_metadata(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    class _FakeServer:
        def __init__(self):
            self.initialized = True
            self.calls = []

        async def initialize(self):
            self.initialized = True

        async def handle_http_request(self, request, user_id=None, metadata=None):
            self.calls.append({"request": request, "user_id": user_id, "metadata": metadata})
            return SimpleNamespace(error=None, result={"ok": True})

    async def _fake_resolve(*args, **kwargs):
        return "user_1", True, True

    fake_server = _FakeServer()
    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: fake_server)
    monkeypatch.setattr(persona_ep, "_resolve_authenticated_user_id", _fake_resolve)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            session_id = "sess_audit"
            ws.send_text(
                json.dumps(
                    {"type": "user_message", "session_id": session_id, "text": "https://example.com"}
                )
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            step = plan["steps"][0]

            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan["plan_id"],
                        "approved_steps": [step["idx"]],
                    }
                )
            )

            _ = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_result")

    assert fake_server.calls
    call = fake_server.calls[0]
    meta = call["metadata"] or {}
    persona_audit = meta.get("persona_audit") or {}
    assert call["user_id"] == "user_1"
    assert meta.get("session_id") == session_id
    assert persona_audit.get("source") == "persona_ws"
    assert persona_audit.get("plan_id")
    assert persona_audit.get("tool") == step["tool"]
    assert persona_audit.get("why")


def test_persona_audio_chunk_emits_partial_transcript_and_tts_audio():

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            audio_payload = base64.b64encode(b"hello from audio").decode("ascii")
            ws.send_text(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "session_id": "sess_audio",
                        "audio_format": "pcm16",
                        "bytes_base64": audio_payload,
                    }
                )
            )

            partial = _recv_until(ws, lambda d: d.get("event") == "partial_transcript")
            assert partial.get("session_id") == "sess_audio"
            assert "hello from audio" in str(partial.get("text_delta"))

            tts_event = _recv_until(ws, lambda d: d.get("event") == "tts_audio")
            assert tts_event.get("session_id") == "sess_audio"
            assert tts_event.get("audio_format") == "pcm16"
            assert tts_event.get("chunk_id")

            audio_bytes = ws.receive_bytes()
            assert audio_bytes


def test_persona_persists_session_turns_and_tool_outcomes(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    manager = SessionManager()

    async def _fake_resolve(*args, **kwargs):
        return "777", True, True

    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)
    monkeypatch.setattr(persona_ep, "_resolve_authenticated_user_id", _fake_resolve)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            session_id = "sess_turn_persist"
            ws.send_text(json.dumps({"type": "user_message", "session_id": session_id, "text": "hello"}))
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            first_idx = int(plan["steps"][0]["idx"])
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan["plan_id"],
                        "approved_steps": [first_idx],
                    }
                )
            )
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_result")

    turns = manager.list_turns(session_id=session_id, user_id="777")
    assert any(t["role"] == "user" and t["content"] == "hello" for t in turns)
    assert any(t["role"] == "tool" and t["type"] == "tool_result" for t in turns)


def test_persona_memory_context_applied_when_opted_in(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    user_id = "888"
    db = _seed_personalization_db(tmp_path, monkeypatch, user_id=user_id, enabled=True)
    _ = db.add_semantic_memory(
        SemanticMemory(user_id=user_id, content="Prefers concise explanations.", tags=["prefs"])
    )

    async def _fake_resolve(*args, **kwargs):
        return user_id, True, True

    monkeypatch.setattr(persona_ep, "_resolve_authenticated_user_id", _fake_resolve)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": "sess_mem_on",
                        "text": "find notes about FastAPI testing",
                    }
                )
            )
            _ = _recv_until(
                ws,
                lambda d: d.get("event") == "notice" and "Applied" in str(d.get("message")),
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")

    query_value = str(plan["steps"][0]["args"]["query"])
    assert "Prefers concise explanations." in query_value


def test_persona_memory_context_skipped_when_opted_out(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    user_id = "889"
    db = _seed_personalization_db(tmp_path, monkeypatch, user_id=user_id, enabled=False)
    _ = db.add_semantic_memory(
        SemanticMemory(user_id=user_id, content="Should not be injected.", tags=["prefs"])
    )

    async def _fake_resolve(*args, **kwargs):
        return user_id, True, True

    monkeypatch.setattr(persona_ep, "_resolve_authenticated_user_id", _fake_resolve)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": "sess_mem_off",
                        "text": "find notes about FastAPI testing",
                    }
                )
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")

    query_value = str(plan["steps"][0]["args"]["query"])
    assert "Should not be injected." not in query_value
