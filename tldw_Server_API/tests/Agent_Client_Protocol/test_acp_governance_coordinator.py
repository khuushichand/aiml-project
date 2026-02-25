from __future__ import annotations

import importlib.machinery
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.runner_client import (
    ACPGovernanceCoordinator,
    ACPRunnerClient,
    SessionWebSocketRegistry,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

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


class _PromptGovernanceDeniedRunner:
    def __init__(self) -> None:
        self.agent_capabilities = {"promptCapabilities": {"image": False}}

    async def verify_session_access(self, session_id: str, user_id: int) -> bool:
        return True

    async def check_prompt_governance(
        self,
        session_id: str,
        prompt: list[dict[str, Any]],
        *,
        user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return {
            "action": "deny",
            "status": "deny",
            "category": "acp",
        }

    async def prompt(self, session_id: str, prompt: list[dict[str, Any]]) -> dict[str, Any]:
        return {"stopReason": "end", "detail": "unexpected-success"}


def _new_runner_client_for_permissions() -> ACPRunnerClient:
    cfg = SimpleNamespace(
        command="echo",
        args=[],
        env={},
        cwd=None,
        startup_timeout_sec=0,
    )
    return ACPRunnerClient(cfg)


@pytest.fixture()
def prompt_governance_denied_runner(monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.agent_client_protocol as acp_endpoints

    runner = _PromptGovernanceDeniedRunner()

    async def _get_runner_client():
        return runner

    monkeypatch.setattr(acp_endpoints, "get_runner_client", _get_runner_client)
    return runner


def test_prompt_denied_by_governance_returns_blocked_error(
    client_user_only,
    prompt_governance_denied_runner,
):
    response = client_user_only.post(
        "/api/v1/acp/sessions/prompt",
        json={
            "session_id": "session-gov-prompt",
            "prompt": [{"role": "user", "content": "ship this change"}],
        },
    )

    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["code"] == "governance_blocked"
    assert body["detail"]["governance"]["action"] == "deny"


@pytest.mark.asyncio
async def test_permission_request_uses_single_unified_approval_path(monkeypatch):
    client = _new_runner_client_for_permissions()
    session_id = "session-gov-auto"

    async def _send(_payload: dict[str, Any]) -> None:
        return None

    registry = SessionWebSocketRegistry(session_id=session_id)
    registry.websockets.add(_send)
    client._ws_registry[session_id] = registry

    async def _fake_check_permission_governance(
        sid: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
        *,
        tier: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return {
            "action": "require_approval",
            "status": "require_approval",
            "category": "acp",
        }

    monkeypatch.setattr(client, "check_permission_governance", _fake_check_permission_governance, raising=False)

    prompts: list[dict[str, Any]] = []

    async def _fake_broadcast(sid: str, message: dict[str, Any]) -> None:
        if message.get("type") == "permission_request":
            prompts.append(message)
            await client.respond_to_permission(sid, str(message["request_id"]), True)

    monkeypatch.setattr(client, "_broadcast_to_session", _fake_broadcast)

    response = await client._handle_request(
        ACPMessage(
            jsonrpc="2.0",
            id="perm-1",
            method="session/request_permission",
            params={
                "sessionId": session_id,
                "tool": {"name": "fs.read", "input": {"path": "README.md"}},
            },
        )
    )

    assert response.result == {"outcome": {"outcome": "approved"}}
    assert len(prompts) == 1


@pytest.mark.asyncio
async def test_governance_require_approval_plus_batch_tier_creates_one_prompt(monkeypatch):
    client = _new_runner_client_for_permissions()
    session_id = "session-gov-batch"

    async def _send(_payload: dict[str, Any]) -> None:
        return None

    registry = SessionWebSocketRegistry(session_id=session_id)
    registry.websockets.add(_send)
    registry.batch_approved_tiers.add("batch")
    client._ws_registry[session_id] = registry

    async def _fake_check_permission_governance(
        sid: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
        *,
        tier: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return {
            "action": "require_approval",
            "status": "require_approval",
            "category": "acp",
        }

    monkeypatch.setattr(client, "check_permission_governance", _fake_check_permission_governance, raising=False)

    prompts: list[dict[str, Any]] = []

    async def _fake_broadcast(sid: str, message: dict[str, Any]) -> None:
        if message.get("type") == "permission_request":
            prompts.append(message)
            await client.respond_to_permission(sid, str(message["request_id"]), True)

    monkeypatch.setattr(client, "_broadcast_to_session", _fake_broadcast)

    response = await client._handle_request(
        ACPMessage(
            jsonrpc="2.0",
            id="perm-2",
            method="session/request_permission",
            params={
                "sessionId": session_id,
                "tool": {"name": "fs.write", "input": {"path": "README.md", "content": "ok"}},
            },
        )
    )

    assert response.result == {"outcome": {"outcome": "approved"}}
    assert len(prompts) == 1


def test_permission_outcome_shadow_deny_falls_back_to_tier_logic():
    outcome = ACPGovernanceCoordinator.resolve_permission_outcome(
        tier="auto",
        batch_tier_approved=False,
        governance={"action": "deny", "status": "deny", "rollout_mode": "shadow"},
    )

    assert outcome == "approve"


def test_permission_outcome_off_mode_ignores_require_approval():
    outcome = ACPGovernanceCoordinator.resolve_permission_outcome(
        tier="auto",
        batch_tier_approved=False,
        governance={"action": "require_approval", "status": "require_approval", "rollout_mode": "off"},
    )

    assert outcome == "approve"


@pytest.mark.asyncio
async def test_prompt_shadow_rollout_deny_is_not_blocked(monkeypatch):
    client = _new_runner_client_for_permissions()

    async def _fake_check_prompt_governance(
        session_id: str,
        prompt: list[dict[str, Any]],
        *,
        user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return {
            "action": "deny",
            "status": "deny",
            "category": "acp",
            "rollout_mode": "shadow",
        }

    monkeypatch.setattr(client, "check_prompt_governance", _fake_check_prompt_governance, raising=False)

    async def _fake_call(method: str, payload: dict[str, Any]) -> ACPMessage:
        assert method == "session/prompt"
        assert payload["sessionId"] == "session-shadow"
        return ACPMessage(jsonrpc="2.0", id="acp-shadow", result={"stopReason": "end"})

    client._client = SimpleNamespace(call=_fake_call)

    response = await client.prompt(
        "session-shadow",
        [{"role": "user", "content": "continue"}],
    )

    assert response == {"stopReason": "end"}


@pytest.mark.asyncio
async def test_check_permission_governance_records_metrics(monkeypatch):
    client = _new_runner_client_for_permissions()

    class _GovernanceStub:
        async def validate_change(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["surface"] == "acp_permission"
            return {
                "action": "allow",
                "status": "allow",
                "category": "acp",
            }

    client._governance = _GovernanceStub()  # type: ignore[assignment]
    monkeypatch.setattr(client, "_resolve_governance_rollout_mode", lambda _metadata=None: "enforce", raising=False)

    metric_calls: list[dict[str, str]] = []
    monkeypatch.setattr(
        client,
        "_record_governance_check",
        lambda **kwargs: metric_calls.append({k: str(v) for k, v in kwargs.items()}),
        raising=False,
    )

    governance = await client.check_permission_governance(
        "session-metric",
        "fs.read",
        {"path": "README.md"},
        tier="auto",
    )

    assert isinstance(governance, dict)
    assert metric_calls
    assert metric_calls[-1]["surface"] == "acp_permission"
    assert metric_calls[-1]["status"] == "allow"
    assert metric_calls[-1]["rollout_mode"] == "enforce"
