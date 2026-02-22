import base64
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB, SemanticMemory
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Persona.session_manager import SessionManager


pytestmark = pytest.mark.unit

fastapi_app = FastAPI()
fastapi_app.include_router(persona_ep.router, prefix="/api/v1/persona")


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


def _seed_persona_session(
    tmp_path,
    monkeypatch,
    *,
    user_id: str,
    session_id: str,
    mode: str,
    scope_snapshot_json: dict | None = None,
) -> None:
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

    base = tmp_path / "user_db"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))
    db_path = DatabasePaths.get_chacha_db_path(int(user_id))
    db = CharactersRAGDB(str(db_path), client_id=f"persona-ws-seed-{user_id}-{session_id}")
    try:
        persona_id = db.create_persona_profile(
            {
                "id": "research_assistant",
                "user_id": str(user_id),
                "name": "Research Assistant",
                "mode": mode,
                "system_prompt": "Helper",
                "is_active": True,
            }
        )
        _ = db.create_persona_session(
            {
                "id": session_id,
                "persona_id": persona_id,
                "user_id": str(user_id),
                "mode": mode,
                "reuse_allowed": mode == "persistent_scoped",
                "status": "active",
                "scope_snapshot_json": dict(scope_snapshot_json or {}),
            }
        )
    finally:
        db.close_connection()


def _assert_event_meta_fields(event: dict, *, session_id: str) -> None:
    assert event.get("session_id") == session_id
    assert isinstance(event.get("timestamp_ms"), int)
    assert isinstance(event.get("event_seq"), int)


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
            assert isinstance(steps[0].get("policy"), dict)
            assert steps[0]["policy"]["allow"] is True
            assert steps[0]["policy"]["required_scope"] == "write:preview"
            assert steps[0]["policy"]["requires_confirmation"] is True

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
            # Canonical field is `output`; legacy `result` remains as a temporary alias.
            assert "output" in evt_res
            assert "result" in evt_res
            assert evt_res["output"] == evt_res["result"]


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


def test_persona_policy_denial_emits_reason_code_and_result(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    manager = SessionManager()
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)

    session_id = "sess_policy_denied"
    plan_id = "plan_policy_denied"
    manager.put_plan(
        session_id=session_id,
        user_id="1",
        persona_id="research_assistant",
        plan_id=plan_id,
        steps=[{"idx": 0, "tool": "export_report", "args": {"format": "md"}}],
    )

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())

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

            deny_notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "POLICY_EXPORT_DISABLED",
            )
            assert deny_notice.get("step_idx") == 0
            assert deny_notice.get("tool") == "export_report"

            deny_result = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            assert deny_result.get("ok") is False
            assert deny_result.get("reason_code") == "POLICY_EXPORT_DISABLED"
            assert deny_result.get("output") is None
            assert deny_result.get("result") is None
            assert isinstance(deny_result.get("policy"), dict)
            assert deny_result["policy"]["allow"] is False
            assert deny_result["policy"]["required_scope"] == "write:export"


def test_persona_policy_allows_mcp_tool_when_rules_intersect(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

    base = tmp_path / "user_db_mcp_allow"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))
    db_path = DatabasePaths.get_chacha_db_path(1)
    db = CharactersRAGDB(str(db_path), client_id="persona-ws-mcp-policy-allow-test")
    try:
        persona_id = db.create_persona_profile(
            {
                "id": "research_assistant",
                "user_id": "1",
                "name": "Research Assistant",
                "mode": "session_scoped",
                "system_prompt": "Helper",
                "is_active": True,
            }
        )
        _ = db.replace_persona_policy_rules(
            persona_id=persona_id,
            user_id="1",
            rules=[{"rule_kind": "mcp_tool", "rule_name": "knowledge.search", "allowed": True}],
        )
        _ = db.create_persona_session(
            {
                "id": "sess_policy_allow_mcp",
                "persona_id": persona_id,
                "user_id": "1",
                "mode": "session_scoped",
                "reuse_allowed": False,
                "status": "active",
                "scope_snapshot_json": {},
            }
        )
    finally:
        db.close_connection()

    manager = SessionManager()
    manager.put_plan(
        session_id="sess_policy_allow_mcp",
        user_id="1",
        persona_id="research_assistant",
        plan_id="plan_policy_allow_mcp",
        steps=[
            {
                "idx": 0,
                "step_type": "mcp_tool",
                "tool": "knowledge.search",
                "args": {"query": "hello"},
            }
        ],
    )

    class _FakeServer:
        def __init__(self):
            self.initialized = True
            self.calls = []

        async def initialize(self):
            self.initialized = True

        async def handle_http_request(self, request, user_id=None, metadata=None):
            self.calls.append({"request": request, "user_id": user_id, "metadata": metadata})
            return SimpleNamespace(error=None, result={"ok": True})

    fake_server = _FakeServer()
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)
    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: fake_server)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": "sess_policy_allow_mcp",
                        "plan_id": "plan_policy_allow_mcp",
                        "approved_steps": [0],
                    }
                )
            )

            evt_call = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            assert evt_call.get("step_type") == "mcp_tool"
            assert evt_call.get("tool") == "knowledge.search"

            evt_result = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            assert evt_result.get("ok") is True
            assert evt_result.get("step_type") == "mcp_tool"

    assert fake_server.calls
    first_call = fake_server.calls[0]
    metadata = first_call.get("metadata") or {}
    assert metadata.get("allowed_tools") == ["knowledge.search"]


def test_persona_policy_blocks_skill_without_persona_allow(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

    base = tmp_path / "user_db_skill_block"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))
    db_path = DatabasePaths.get_chacha_db_path(1)
    db = CharactersRAGDB(str(db_path), client_id="persona-ws-skill-policy-block-test")
    try:
        persona_id = db.create_persona_profile(
            {
                "id": "research_assistant",
                "user_id": "1",
                "name": "Research Assistant",
                "mode": "session_scoped",
                "system_prompt": "Helper",
                "is_active": True,
            }
        )
        _ = db.replace_persona_policy_rules(
            persona_id=persona_id,
            user_id="1",
            rules=[{"rule_kind": "mcp_tool", "rule_name": "knowledge.search", "allowed": True}],
        )
        _ = db.create_persona_session(
            {
                "id": "sess_skill_block",
                "persona_id": persona_id,
                "user_id": "1",
                "mode": "session_scoped",
                "reuse_allowed": False,
                "status": "active",
                "scope_snapshot_json": {},
            }
        )
    finally:
        db.close_connection()

    manager = SessionManager()
    manager.put_plan(
        session_id="sess_skill_block",
        user_id="1",
        persona_id="research_assistant",
        plan_id="plan_skill_block",
        steps=[{"idx": 0, "step_type": "skill", "tool": "daily-brief", "args": {"args": "headlines"}}],
    )
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": "sess_skill_block",
                        "plan_id": "plan_skill_block",
                        "approved_steps": [0],
                    }
                )
            )

            deny_notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice" and d.get("reason_code") == "POLICY_PERSONA_NO_RULES",
            )
            assert deny_notice.get("tool") == "daily-brief"
            assert deny_notice.get("step_type") == "skill"

            deny_result = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            assert deny_result.get("ok") is False
            assert deny_result.get("reason_code") == "POLICY_PERSONA_NO_RULES"
            assert deny_result.get("step_type") == "skill"


def test_persona_policy_allows_skill_when_rule_present(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

    base = tmp_path / "user_db_skill_allow"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))
    db_path = DatabasePaths.get_chacha_db_path(1)
    db = CharactersRAGDB(str(db_path), client_id="persona-ws-skill-policy-allow-test")
    try:
        persona_id = db.create_persona_profile(
            {
                "id": "research_assistant",
                "user_id": "1",
                "name": "Research Assistant",
                "mode": "session_scoped",
                "system_prompt": "Helper",
                "is_active": True,
            }
        )
        _ = db.replace_persona_policy_rules(
            persona_id=persona_id,
            user_id="1",
            rules=[{"rule_kind": "skill", "rule_name": "daily-brief", "allowed": True}],
        )
        _ = db.create_persona_session(
            {
                "id": "sess_skill_allow",
                "persona_id": persona_id,
                "user_id": "1",
                "mode": "session_scoped",
                "reuse_allowed": False,
                "status": "active",
                "scope_snapshot_json": {},
            }
        )
    finally:
        db.close_connection()

    async def _fake_handle_skill(*args, **kwargs):
        return {
            "success": True,
            "skill_name": "daily-brief",
            "rendered_prompt": "briefing",
            "allowed_tools": [],
            "execution_mode": "inline",
            "fork_output": None,
        }

    manager = SessionManager()
    manager.put_plan(
        session_id="sess_skill_allow",
        user_id="1",
        persona_id="research_assistant",
        plan_id="plan_skill_allow",
        steps=[{"idx": 0, "step_type": "skill", "tool": "daily-brief", "args": {"args": "headlines"}}],
    )
    monkeypatch.setattr(persona_ep, "get_session_manager", lambda: manager)
    monkeypatch.setattr(persona_ep, "handle_skill_tool_call", _fake_handle_skill)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": "sess_skill_allow",
                        "plan_id": "plan_skill_allow",
                        "approved_steps": [0],
                    }
                )
            )

            evt_call = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            assert evt_call.get("tool") == "daily-brief"
            assert evt_call.get("step_type") == "skill"

            evt_result = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            assert evt_result.get("ok") is True
            assert evt_result.get("step_type") == "skill"
            assert evt_result.get("output", {}).get("success") is True


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


def test_persona_tool_call_attaches_scope_metadata_from_persisted_session(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

    base = tmp_path / "user_db_scope"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))
    db_path = DatabasePaths.get_chacha_db_path(1)
    db = CharactersRAGDB(str(db_path), client_id="persona-ws-scope-metadata-test")
    try:
        persona_id = db.create_persona_profile(
            {
                "id": "research_assistant",
                "user_id": "1",
                "name": "Research Assistant",
                "mode": "session_scoped",
                "system_prompt": "Helper",
                "is_active": True,
            }
        )
        _ = db.create_persona_session(
            {
                "id": "sess_scope_forward",
                "persona_id": persona_id,
                "user_id": "1",
                "mode": "session_scoped",
                "reuse_allowed": False,
                "status": "active",
                "scope_snapshot_json": {
                    "scope_snapshot_id": "scope_forward_1",
                    "materialized_scope": {
                        "explicit_ids": {
                            "conversation_id": ["conv-a"],
                            "media_id": ["2"],
                        }
                    },
                    "audit": {"scope_snapshot_id": "scope_forward_1"},
                },
            }
        )
    finally:
        db.close_connection()

    class _FakeServer:
        def __init__(self):
            self.initialized = True
            self.calls = []

        async def initialize(self):
            self.initialized = True

        async def handle_http_request(self, request, user_id=None, metadata=None):
            self.calls.append({"request": request, "user_id": user_id, "metadata": metadata})
            return SimpleNamespace(error=None, result={"ok": True})

    fake_server = _FakeServer()
    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: fake_server)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {"type": "user_message", "session_id": "sess_scope_forward", "text": "hello"}
                )
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            step = plan["steps"][0]
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": "sess_scope_forward",
                        "plan_id": plan["plan_id"],
                        "approved_steps": [step["idx"]],
                    }
                )
            )
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_result")

    assert fake_server.calls
    metadata = fake_server.calls[0].get("metadata") or {}
    scope_payload = metadata.get("persona_scope") or {}
    assert scope_payload.get("scope_snapshot_id") == "scope_forward_1"
    assert scope_payload.get("explicit_ids", {}).get("conversation_id") == ["conv-a"]
    assert scope_payload.get("explicit_ids", {}).get("media_id") == ["2"]


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
            assert partial.get("audio_format") == "pcm16"
            assert isinstance(partial.get("seq"), int)
            assert isinstance(partial.get("timestamp_ms"), int)

            tts_event = _recv_until(ws, lambda d: d.get("event") == "tts_audio")
            assert tts_event.get("session_id") == "sess_audio"
            assert tts_event.get("audio_format") == "pcm16"
            assert tts_event.get("chunk_id")
            assert isinstance(tts_event.get("chunk_index"), int)
            assert isinstance(tts_event.get("chunk_count"), int)
            assert isinstance(tts_event.get("seq"), int)
            assert isinstance(tts_event.get("timestamp_ms"), int)

            audio_bytes = ws.receive_bytes()
            assert audio_bytes


def test_persona_audio_chunk_rejects_unsupported_format(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    monkeypatch.setattr(persona_ep, "_get_persona_allowed_audio_formats", lambda: {"pcm16"})

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            audio_payload = base64.b64encode(b"hello").decode("ascii")
            ws.send_text(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "session_id": "sess_bad_format",
                        "audio_format": "flac",
                        "bytes_base64": audio_payload,
                    }
                )
            )

            notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "AUDIO_FORMAT_UNSUPPORTED",
            )
            assert "Unsupported audio_format" in str(notice.get("message"))


def test_persona_audio_chunk_rejects_oversized_payload(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    monkeypatch.setattr(persona_ep, "_get_persona_audio_chunk_max_bytes", lambda: 4)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            audio_payload = base64.b64encode(b"hello-world").decode("ascii")
            ws.send_text(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "session_id": "sess_big_audio",
                        "audio_format": "pcm16",
                        "bytes_base64": audio_payload,
                    }
                )
            )

            notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "AUDIO_CHUNK_TOO_LARGE",
            )
            assert "exceeds max bytes" in str(notice.get("message"))


def test_persona_audio_chunk_rate_limited(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    monkeypatch.setattr(persona_ep, "_get_persona_audio_chunks_per_minute", lambda: 1)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())

            first_payload = base64.b64encode(b"first chunk").decode("ascii")
            ws.send_text(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "session_id": "sess_rate_limit",
                        "audio_format": "pcm16",
                        "bytes_base64": first_payload,
                    }
                )
            )
            _ = _recv_until(ws, lambda d: d.get("event") == "partial_transcript")
            _ = _recv_until(ws, lambda d: d.get("event") == "tts_audio")
            _ = ws.receive_bytes()

            second_payload = base64.b64encode(b"second chunk").decode("ascii")
            ws.send_text(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "session_id": "sess_rate_limit",
                        "audio_format": "pcm16",
                        "bytes_base64": second_payload,
                    }
                )
            )

            notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "AUDIO_RATE_LIMITED",
            )
            assert "rate limit exceeded" in str(notice.get("message"))


def test_persona_tts_output_truncated_notice(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    monkeypatch.setattr(persona_ep, "_get_persona_tts_max_total_bytes", lambda: 4)
    monkeypatch.setattr(persona_ep, "_get_persona_tts_chunk_size_bytes", lambda: 2)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            audio_payload = base64.b64encode(b"audio").decode("ascii")
            ws.send_text(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "session_id": "sess_tts_trunc",
                        "audio_format": "pcm16",
                        "bytes_base64": audio_payload,
                        "tts_text": "0123456789",
                    }
                )
            )

            _ = _recv_until(ws, lambda d: d.get("event") == "partial_transcript")
            trunc_notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "TTS_OUTPUT_TRUNCATED",
            )
            assert "TTS output truncated" in str(trunc_notice.get("message"))

            first_tts = _recv_until(ws, lambda d: d.get("event") == "tts_audio")
            _ = ws.receive_bytes()
            second_tts = _recv_until(
                ws,
                lambda d: d.get("event") == "tts_audio" and d.get("chunk_index") == 1,
            )
            assert first_tts.get("chunk_count") == 2
            assert second_tts.get("chunk_count") == 2
            _ = ws.receive_bytes()


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


def test_persona_memory_context_can_be_disabled_per_message(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    user_id = "901"
    db = _seed_personalization_db(tmp_path, monkeypatch, user_id=user_id, enabled=True)
    _ = db.add_semantic_memory(
        SemanticMemory(user_id=user_id, content="Do not include me when disabled.", tags=["prefs"])
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
                        "session_id": "sess_mem_disable_msg",
                        "text": "find notes for pytest",
                        "use_memory_context": False,
                    }
                )
            )
            disabled_notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "MEMORY_CONTEXT_DISABLED",
            )
            assert "disabled" in str(disabled_notice.get("message")).lower()
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")

    memory_payload = plan.get("memory") or {}
    assert memory_payload.get("enabled") is False
    assert memory_payload.get("applied_count") == 0
    query_value = str(plan["steps"][0]["args"]["query"])
    assert "Do not include me when disabled." not in query_value


def test_persona_memory_top_k_override_used(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    captured: dict[str, int] = {}

    async def _fake_resolve(*args, **kwargs):
        return "1", True, True

    class _Memory:
        def __init__(self, content: str):
            self.content = content

    def _fake_retrieve(
        *,
        user_id: str,
        query_text: str,
        top_k: int,
        persona_id: str | None = None,
        runtime_mode: str | None = None,
        scope_snapshot_id: str | None = None,
        session_id: str | None = None,
    ):
        captured["top_k"] = top_k
        captured["persona_id"] = str(persona_id or "")
        captured["runtime_mode"] = str(runtime_mode or "")
        captured["scope_snapshot_id"] = scope_snapshot_id
        captured["session_id"] = str(session_id or "")
        return [_Memory("memory-a"), _Memory("memory-b")]

    monkeypatch.setattr(persona_ep, "_resolve_authenticated_user_id", _fake_resolve)
    monkeypatch.setattr(persona_ep, "retrieve_top_memories", _fake_retrieve)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": "sess_mem_topk",
                        "text": "find testing notes",
                        "memory_top_k": 1,
                    }
                )
            )
            _ = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "MEMORY_CONTEXT_APPLIED",
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")

    assert captured.get("top_k") == 1
    assert captured.get("persona_id")
    assert captured.get("runtime_mode") == "session_scoped"
    assert captured.get("session_id") == "sess_mem_topk"
    memory_payload = plan.get("memory") or {}
    assert memory_payload.get("requested_top_k") == 1
    assert memory_payload.get("applied_count") == 2


def test_persona_ws_required_fields_and_event_ordering(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    class _FakeServer:
        def __init__(self):
            self.initialized = True

        async def initialize(self):
            self.initialized = True

        async def handle_http_request(self, request, user_id=None, metadata=None):
            return SimpleNamespace(error=None, result={"ok": True, "tool": request.params.get("name")})

    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: _FakeServer())

    session_id = "sess_contract_order"
    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": session_id,
                        "text": "https://example.com",
                        "use_memory_context": False,
                    }
                )
            )

            notice_evt = _recv_until(
                ws,
                lambda d: d.get("event") == "notice" and d.get("reason_code") == "MEMORY_CONTEXT_DISABLED",
            )
            _assert_event_meta_fields(notice_evt, session_id=session_id)
            assert notice_evt.get("level") in {"info", "warning", "error"}
            assert isinstance(notice_evt.get("message"), str)
            assert "reason_code" in notice_evt

            plan_evt = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            _assert_event_meta_fields(plan_evt, session_id=session_id)
            assert isinstance(plan_evt.get("plan_id"), str) and plan_evt.get("plan_id")
            assert isinstance(plan_evt.get("steps"), list)
            assert isinstance(plan_evt.get("memory"), dict)
            assert isinstance(plan_evt.get("persona_id"), str) and plan_evt.get("persona_id")
            assert int(plan_evt["event_seq"]) > int(notice_evt["event_seq"])

            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan_evt["plan_id"],
                        "approved_steps": [0, 1],
                    }
                )
            )

            call_evt = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            _assert_event_meta_fields(call_evt, session_id=session_id)
            assert call_evt.get("plan_id") == plan_evt["plan_id"]
            assert isinstance(call_evt.get("step_idx"), int)
            assert call_evt.get("step_type") in {"mcp_tool", "skill", "rag_query", "final_answer"}
            assert isinstance(call_evt.get("tool"), str) and call_evt.get("tool")
            assert isinstance(call_evt.get("args"), dict)
            assert isinstance(call_evt.get("policy"), dict)
            assert isinstance(call_evt.get("why"), str)

            result_evt = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            _assert_event_meta_fields(result_evt, session_id=session_id)
            assert result_evt.get("plan_id") == plan_evt["plan_id"]
            assert isinstance(result_evt.get("step_idx"), int)
            assert result_evt.get("step_type") in {"mcp_tool", "skill", "rag_query", "final_answer"}
            assert isinstance(result_evt.get("tool"), str) and result_evt.get("tool")
            assert "ok" in result_evt
            assert "output" in result_evt
            assert "result" in result_evt
            assert "reason_code" in result_evt

            assistant_evt = _recv_until(ws, lambda d: d.get("event") == "assistant_delta")
            _assert_event_meta_fields(assistant_evt, session_id=session_id)
            assert isinstance(assistant_evt.get("text_delta"), str)

            assert int(call_evt["event_seq"]) > int(plan_evt["event_seq"])
            assert int(result_evt["event_seq"]) > int(call_evt["event_seq"])
            assert int(assistant_evt["event_seq"]) > int(result_evt["event_seq"])


def test_persona_ws_ignores_forged_security_fields(monkeypatch):
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

    fake_server = _FakeServer()
    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: fake_server)

    session_id = "sess_forged_fields"
    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": session_id,
                        "text": "https://example.com",
                        "persona_scope": {"scope_snapshot_id": "forged_scope"},
                        "allowed_tools": ["evil.tool"],
                        "persona_audit": {"source": "forged_client"},
                        "metadata": {"unsafe": "value"},
                    }
                )
            )
            notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice" and d.get("reason_code") == "SECURITY_FIELDS_IGNORED",
            )
            ignored_fields = set(notice.get("ignored_fields") or [])
            assert ignored_fields == {"persona_scope", "allowed_tools", "persona_audit", "metadata"}

            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan["plan_id"],
                        "approved_steps": [0],
                    }
                )
            )
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_result")

    assert fake_server.calls
    metadata = fake_server.calls[0].get("metadata") or {}
    assert metadata.get("session_id") == session_id
    assert metadata.get("persona_audit", {}).get("source") == "persona_ws"
    assert "evil.tool" not in list(metadata.get("allowed_tools") or [])
    assert metadata.get("persona_scope") is None
    assert metadata.get("metadata") is None


def test_persona_ws_rejects_cross_user_scope_injection(tmp_path, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    injected_session_id = "sess_cross_user_scope"
    _seed_persona_session(
        tmp_path,
        monkeypatch,
        user_id="2",
        session_id=injected_session_id,
        mode="session_scoped",
        scope_snapshot_json={
            "scope_snapshot_id": "scope_user_2_only",
            "materialized_scope": {"explicit_ids": {"conversation_id": ["conv-secret"]}},
            "audit": {"scope_snapshot_id": "scope_user_2_only"},
        },
    )

    class _FakeServer:
        def __init__(self):
            self.initialized = True
            self.calls = []

        async def initialize(self):
            self.initialized = True

        async def handle_http_request(self, request, user_id=None, metadata=None):
            self.calls.append({"request": request, "user_id": user_id, "metadata": metadata})
            return SimpleNamespace(error=None, result={"ok": True})

    fake_server = _FakeServer()
    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: fake_server)

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": injected_session_id,
                        "text": "https://example.com",
                    }
                )
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": injected_session_id,
                        "plan_id": plan["plan_id"],
                        "approved_steps": [0],
                    }
                )
            )
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_result")

    assert fake_server.calls
    metadata = fake_server.calls[0].get("metadata") or {}
    assert metadata.get("session_id") == injected_session_id
    assert metadata.get("persona_scope") is None


def test_persona_session_scoped_persisted_session_disables_memory_context(tmp_path, monkeypatch):
    memory_text = "Never inject this in session_scoped mode."
    db = _seed_personalization_db(tmp_path, monkeypatch, user_id="1", enabled=True)
    _ = db.add_semantic_memory(SemanticMemory(user_id="1", content=memory_text, tags=["prefs"]))
    _seed_persona_session(
        tmp_path,
        monkeypatch,
        user_id="1",
        session_id="sess_mode_session_scoped",
        mode="session_scoped",
    )

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": "sess_mode_session_scoped",
                        "text": "find notes about pytest",
                    }
                )
            )
            mode_notice = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "MEMORY_CONTEXT_MODE_DISABLED",
            )
            assert "disabled" in str(mode_notice.get("message")).lower()
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")

    memory_payload = plan.get("memory") or {}
    assert memory_payload.get("enabled") is False
    assert memory_payload.get("requested_enabled") is True
    query_value = str(plan["steps"][0]["args"]["query"])
    assert memory_text not in query_value


def test_persona_persistent_scoped_persisted_session_applies_memory_context(tmp_path, monkeypatch):
    memory_text = "Apply this memory in persistent mode."
    db = _seed_personalization_db(tmp_path, monkeypatch, user_id="1", enabled=True)
    _ = db.add_semantic_memory(SemanticMemory(user_id="1", content=memory_text, tags=["prefs"]))
    _seed_persona_session(
        tmp_path,
        monkeypatch,
        user_id="1",
        session_id="sess_mode_persistent_scoped",
        mode="persistent_scoped",
    )

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": "sess_mode_persistent_scoped",
                        "text": "find notes about pytest",
                    }
                )
            )
            _ = _recv_until(
                ws,
                lambda d: d.get("event") == "notice"
                and d.get("reason_code") == "MEMORY_CONTEXT_APPLIED",
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")

    memory_payload = plan.get("memory") or {}
    assert memory_payload.get("enabled") is True
    assert memory_payload.get("applied_count") >= 1
    query_value = str(plan["steps"][0]["args"]["query"])
    assert memory_text in query_value


@pytest.mark.parametrize(
    ("mode", "session_id", "expected_summary_memory"),
    [
        ("session_scoped", "sess_summary_mode_session", False),
        ("persistent_scoped", "sess_summary_mode_persistent", True),
    ],
)
def test_persona_summary_memory_write_only_for_persistent_mode(
    tmp_path,
    monkeypatch,
    mode: str,
    session_id: str,
    expected_summary_memory: bool,
):
    from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep

    class _FakeServer:
        def __init__(self):
            self.initialized = True

        async def initialize(self):
            self.initialized = True

        async def handle_http_request(self, request, user_id=None, metadata=None):
            return SimpleNamespace(error=None, result={"ok": True, "tool": request.params.get("name")})

    monkeypatch.setattr(persona_ep, "get_mcp_server", lambda: _FakeServer())

    db = _seed_personalization_db(tmp_path, monkeypatch, user_id="1", enabled=True)
    _seed_persona_session(
        tmp_path,
        monkeypatch,
        user_id="1",
        session_id=session_id,
        mode=mode,
    )

    with TestClient(fastapi_app) as c:
        with c.websocket_connect("/api/v1/persona/stream") as ws:
            _ = json.loads(ws.receive_text())
            ws.send_text(
                json.dumps(
                    {
                        "type": "user_message",
                        "session_id": session_id,
                        "text": "https://example.com",
                        "use_memory_context": False,
                    }
                )
            )
            plan = _recv_until(ws, lambda d: d.get("event") == "tool_plan")
            approved_steps = [int(step["idx"]) for step in plan.get("steps", [])]
            ws.send_text(
                json.dumps(
                    {
                        "type": "confirm_plan",
                        "session_id": session_id,
                        "plan_id": plan["plan_id"],
                        "approved_steps": approved_steps,
                    }
                )
            )
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_call")
            _ = _recv_until(ws, lambda d: d.get("event") == "tool_result")
            _ = _recv_until(ws, lambda d: d.get("event") == "assistant_delta")

    memories, _ = db.list_semantic_memories(user_id="1", limit=50, offset=0)
    memory_contents = [str(item.get("content") or "") for item in memories]
    has_summary_memory = any("Summarize the ingested content" in content for content in memory_contents)
    has_tool_outcome_memory = any("Tool=" in content for content in memory_contents)

    assert has_summary_memory is expected_summary_memory
    assert has_tool_outcome_memory is False
