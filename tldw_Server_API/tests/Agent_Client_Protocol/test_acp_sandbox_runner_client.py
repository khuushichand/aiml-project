from __future__ import annotations

import asyncio
import contextlib

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.config import ACPSandboxConfig
from tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_runner_client import (
    ACPSandboxRunnerManager,
    SandboxSessionHandle,
    _is_self_referential_agent_command,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPResponseError


@pytest.mark.unit
def test_acp_sandbox_config_default_network_policy_is_deny_all() -> None:
    cfg = ACPSandboxConfig()
    if cfg.network_policy != "deny_all":
        pytest.fail(f"Expected ACP sandbox default network policy deny_all, got {cfg.network_policy!r}")


@pytest.mark.unit
def test_load_acp_sandbox_config_defaults_network_policy_to_deny_all(monkeypatch) -> None:
    import tldw_Server_API.app.core.Agent_Client_Protocol.config as acp_config

    monkeypatch.delenv("ACP_SANDBOX_NETWORK_POLICY", raising=False)
    monkeypatch.setattr(acp_config, "get_config_section", lambda name: {})
    cfg = acp_config.load_acp_sandbox_config()
    if cfg.network_policy != "deny_all":
        pytest.fail(f"Expected loader fallback network policy deny_all, got {cfg.network_policy!r}")


@pytest.mark.unit
def test_acp_sandbox_config_default_runtime_hardening_flags() -> None:
    cfg = ACPSandboxConfig()
    if cfg.run_as_root is not False:
        pytest.fail(f"Expected ACP sandbox default run_as_root=False, got {cfg.run_as_root!r}")
    if cfg.read_only_root is not True:
        pytest.fail(f"Expected ACP sandbox default read_only_root=True, got {cfg.read_only_root!r}")
    if cfg.ssh_container_port != 2222:
        pytest.fail(f"Expected ACP sandbox default ssh_container_port=2222, got {cfg.ssh_container_port!r}")


@pytest.mark.unit
def test_load_acp_sandbox_config_defaults_runtime_hardening_flags(monkeypatch) -> None:
    import tldw_Server_API.app.core.Agent_Client_Protocol.config as acp_config

    monkeypatch.delenv("ACP_SANDBOX_RUN_AS_ROOT", raising=False)
    monkeypatch.delenv("ACP_SANDBOX_READ_ONLY_ROOT", raising=False)
    monkeypatch.delenv("ACP_SSH_CONTAINER_PORT", raising=False)
    monkeypatch.setattr(acp_config, "get_config_section", lambda name: {})
    cfg = acp_config.load_acp_sandbox_config()
    if cfg.run_as_root is not False:
        pytest.fail(f"Expected loader fallback run_as_root=False, got {cfg.run_as_root!r}")
    if cfg.read_only_root is not True:
        pytest.fail(f"Expected loader fallback read_only_root=True, got {cfg.read_only_root!r}")
    if cfg.ssh_container_port != 2222:
        pytest.fail(f"Expected loader fallback ssh_container_port=2222, got {cfg.ssh_container_port!r}")


@pytest.mark.unit
def test_is_self_referential_agent_command_detects_runner_binary() -> None:
    cases = [
        ("tldw-agent-acp", True),
        ("/usr/local/bin/tldw-agent-acp", True),
        ("claude", False),
        ("/usr/local/bin/codex", False),
    ]
    for command, expected in cases:
        actual = _is_self_referential_agent_command(command)
        if actual != expected:
            pytest.fail(
                f"_is_self_referential_agent_command({command!r}) returned {actual}, expected {expected}"
            )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_session_rejects_self_referential_agent_command() -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            agent_command="/usr/local/bin/tldw-agent-acp",
        )
    )

    with pytest.raises(ACPResponseError, match="cannot be tldw-agent-acp"):
        await manager.create_session(cwd="/workspace")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_session_requires_authenticated_user_id() -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            agent_command="/usr/local/bin/codex",
        )
    )

    with pytest.raises(ACPResponseError, match="require an authenticated user_id"):
        await manager.create_session(cwd="/workspace")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_session_propagates_non_root_read_only_and_internal_ssh_port(monkeypatch) -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            agent_command="/usr/local/bin/codex",
            network_policy="deny_all",
            run_as_root=False,
            read_only_root=True,
            ssh_enabled=True,
            ssh_container_port=2222,
        )
    )
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "1")
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "1")

    import tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_runner_client as src

    class _Obj:
        def __init__(self, obj_id: str) -> None:
            self.id = obj_id

    capture: dict[str, object] = {}

    class _FakeSandboxService:
        def __init__(self) -> None:
            self.cancelled: list[str] = []
            self.destroyed: list[str] = []

        def create_session(self, **kwargs):
            capture["session_spec"] = kwargs.get("spec")
            return _Obj("sandbox-session-hardened")

        def start_run_scaffold(self, **kwargs):
            capture["run_spec"] = kwargs.get("spec")
            return _Obj("run-hardened")

        def cancel_run(self, run_id: str) -> None:
            self.cancelled.append(run_id)

        def destroy_session(self, session_id: str) -> None:
            self.destroyed.append(session_id)

    class _FakeHub:
        def subscribe_with_buffer(self, run_id: str) -> asyncio.Queue:
            return asyncio.Queue()

        def push_stdin(self, run_id: str, data: bytes) -> None:
            return None

    class _CallResult:
        def __init__(self, result: dict[str, object]) -> None:
            self.result = result

    class _FakeStreamClient:
        def __init__(self, send_bytes) -> None:
            self._send_bytes = send_bytes

        def set_notification_handler(self, handler) -> None:
            return None

        def set_request_handler(self, handler) -> None:
            return None

        async def start(self) -> None:
            return None

        async def call(self, method: str, payload: dict[str, object]):
            if method == "initialize":
                return _CallResult({"agentCapabilities": {}})
            if method == "session/new":
                return _CallResult({"sessionId": "acp-session-hardened"})
            if method == "_tldw/session/close":
                return _CallResult({})
            raise AssertionError(f"unexpected method: {method}")

        async def close(self) -> None:
            return None

    class _Store:
        def put_acp_session_control(self, **kwargs) -> None:
            return None

        def delete_acp_session_control(self, session_id: str) -> bool:
            return True

    fake_service = _FakeSandboxService()
    monkeypatch.setattr(src.sandbox_ep, "_service", fake_service, raising=True)
    monkeypatch.setattr(src, "get_hub", lambda: _FakeHub())
    monkeypatch.setattr(src, "ACPStreamClient", _FakeStreamClient)
    monkeypatch.setattr(manager, "_get_sandbox_store", lambda: _Store())
    monkeypatch.setattr(manager, "_generate_ssh_keypair", lambda: ("PRIVATE", "ssh-ed25519 AAAATEST"))

    async def _fake_allocate_ssh_port() -> int:
        return 4567

    monkeypatch.setattr(manager, "_allocate_ssh_port", _fake_allocate_ssh_port)

    session_id = await manager.create_session(cwd="/workspace", user_id=55)
    if session_id != "acp-session-hardened":
        pytest.fail(f"Expected acp-session-hardened, got {session_id!r}")

    session_spec = capture.get("session_spec")
    run_spec = capture.get("run_spec")
    if session_spec is None:
        pytest.fail("Expected sandbox session spec capture")
    if run_spec is None:
        pytest.fail("Expected sandbox run spec capture")
    if getattr(session_spec, "network_policy", None) != "deny_all":
        pytest.fail(f"Expected session spec network_policy='deny_all', got {getattr(session_spec, 'network_policy', None)!r}")
    if getattr(run_spec, "run_as_root", None) is not False:
        pytest.fail(f"Expected run spec run_as_root=False, got {getattr(run_spec, 'run_as_root', None)!r}")
    if getattr(run_spec, "read_only_root", None) is not True:
        pytest.fail(f"Expected run spec read_only_root=True, got {getattr(run_spec, 'read_only_root', None)!r}")
    if getattr(run_spec, "network_policy", None) != "deny_all":
        pytest.fail(f"Expected run spec network_policy='deny_all', got {getattr(run_spec, 'network_policy', None)!r}")
    run_env = getattr(run_spec, "env", {}) or {}
    if run_env.get("ACP_RUNTIME_HOME") != "/workspace/.acp-home":
        pytest.fail(f"Expected ACP_RUNTIME_HOME=/workspace/.acp-home, got {run_env.get('ACP_RUNTIME_HOME')!r}")
    if run_env.get("ACP_SSH_PORT") != "2222":
        pytest.fail(f"Expected ACP_SSH_PORT='2222', got {run_env.get('ACP_SSH_PORT')!r}")
    port_mappings = list(getattr(run_spec, "port_mappings", []) or [])
    if not port_mappings:
        pytest.fail("Expected ACP run spec to include SSH port mapping")
    if port_mappings[0].get("container_port") != 2222:
        pytest.fail(f"Expected container_port=2222, got {port_mappings[0].get('container_port')!r}")
    if port_mappings[0].get("host_port") != 4567:
        pytest.fail(f"Expected host_port=4567, got {port_mappings[0].get('host_port')!r}")

    await manager.close_session(session_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_session_rolls_back_when_control_record_persist_fails(monkeypatch) -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            agent_command="/usr/local/bin/codex",
            ssh_enabled=False,
        )
    )
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "1")
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "1")

    import tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_runner_client as src

    class _Obj:
        def __init__(self, obj_id: str) -> None:
            self.id = obj_id

    class _FakeSandboxService:
        def __init__(self) -> None:
            self.cancelled: list[str] = []
            self.destroyed: list[str] = []

        def create_session(self, **kwargs):
            return _Obj("sandbox-session-atomic")

        def start_run_scaffold(self, **kwargs):
            return _Obj("run-atomic")

        def cancel_run(self, run_id: str) -> None:
            self.cancelled.append(run_id)

        def destroy_session(self, session_id: str) -> None:
            self.destroyed.append(session_id)

    class _FakeHub:
        def subscribe_with_buffer(self, run_id: str) -> asyncio.Queue:
            return asyncio.Queue()

        def push_stdin(self, run_id: str, data: bytes) -> None:
            return None

    class _CallResult:
        def __init__(self, result: dict[str, object]) -> None:
            self.result = result

    class _FakeStreamClient:
        def __init__(self, send_bytes) -> None:
            self._send_bytes = send_bytes

        def set_notification_handler(self, handler) -> None:
            return None

        def set_request_handler(self, handler) -> None:
            return None

        async def start(self) -> None:
            return None

        async def call(self, method: str, payload: dict[str, object]):
            if method == "initialize":
                return _CallResult({"agentCapabilities": {}})
            if method == "session/new":
                return _CallResult({"sessionId": "acp-session-atomic"})
            raise AssertionError(f"unexpected method: {method}")

        async def close(self) -> None:
            return None

    class _BrokenStore:
        def put_acp_session_control(self, **kwargs) -> None:
            raise RuntimeError("store_write_failed")

    fake_service = _FakeSandboxService()
    monkeypatch.setattr(src.sandbox_ep, "_service", fake_service, raising=True)
    monkeypatch.setattr(src, "get_hub", lambda: _FakeHub())
    monkeypatch.setattr(src, "ACPStreamClient", _FakeStreamClient)
    monkeypatch.setattr(manager, "_get_sandbox_store", lambda: _BrokenStore())

    with pytest.raises(ACPResponseError, match="persist ACP sandbox session control metadata"):
        await manager.create_session(cwd="/workspace", user_id=88)

    await asyncio.sleep(0)
    if fake_service.cancelled != ["run-atomic"]:
        pytest.fail(f"Expected run rollback cancellation, got: {fake_service.cancelled!r}")
    if fake_service.destroyed != ["sandbox-session-atomic"]:
        pytest.fail(f"Expected sandbox session rollback destroy, got: {fake_service.destroyed!r}")
    if "acp-session-atomic" in manager._sessions:
        pytest.fail("Create-session rollback left stale in-memory ACP session handle")
    if "acp-session-atomic" in manager._updates:
        pytest.fail("Create-session rollback left stale ACP update queue state")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_control_record_fallback_supports_access_and_metadata(monkeypatch) -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            agent_command="/usr/local/bin/codex",
        )
    )
    control_row = {
        "id": "acp-session-1",
        "user_id": "42",
        "sandbox_session_id": "sandbox-session-1",
        "run_id": "run-1",
        "ssh_host": "127.0.0.1",
        "ssh_port": 4022,
        "ssh_user": "acp",
        "ssh_private_key": "PRIVATE",
        "persona_id": "persona-1",
        "workspace_id": "workspace-1",
        "workspace_group_id": "wg-1",
        "scope_snapshot_id": "scope-1",
    }
    monkeypatch.setattr(manager, "_load_control_record", lambda session_id: dict(control_row))

    assert await manager.verify_session_access("acp-session-1", 42) is True
    assert await manager.verify_session_access("acp-session-1", 7) is False

    metadata = await manager.get_session_metadata("acp-session-1", user_id=42)
    assert metadata is not None
    assert metadata["sandbox_session_id"] == "sandbox-session-1"
    assert metadata["sandbox_run_id"] == "run-1"
    assert metadata["ssh_user"] == "acp"
    assert metadata["persona_id"] == "persona-1"

    ssh_info = await manager.get_ssh_info("acp-session-1", user_id=42)
    assert ssh_info is not None
    assert ssh_info[0] == "127.0.0.1"
    assert ssh_info[1] == 4022
    assert ssh_info[2] == "acp"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_session_rehydrates_and_caches_from_control_record(monkeypatch) -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            agent_command="/usr/local/bin/codex",
        )
    )

    class _DummyClient:
        async def close(self) -> None:
            return None

    task = asyncio.create_task(asyncio.sleep(60))
    handle = SandboxSessionHandle(
        session_id="acp-session-2",
        user_id=99,
        sandbox_session_id="sandbox-session-2",
        run_id="run-2",
        client=_DummyClient(),  # type: ignore[arg-type]
        reader_task=task,
    )

    control_row = {
        "id": "acp-session-2",
        "user_id": "99",
        "sandbox_session_id": "sandbox-session-2",
        "run_id": "run-2",
    }
    monkeypatch.setattr(manager, "_load_control_record", lambda session_id: dict(control_row))
    attach_calls = {"count": 0}

    async def _fake_attach(control):
        attach_calls["count"] += 1
        return handle

    monkeypatch.setattr(manager, "_attach_to_existing_session", _fake_attach)
    monkeypatch.setattr(manager, "_store_control_record", lambda sess: None)

    try:
        restored = await manager._get_session("acp-session-2", required=True)
        assert restored is handle
        restored_again = await manager._get_session("acp-session-2", required=True)
        assert restored_again is handle
        assert attach_calls["count"] == 1
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_session_falls_back_to_persisted_control(monkeypatch) -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            agent_command="/usr/local/bin/codex",
        )
    )

    control_row = {
        "id": "acp-session-3",
        "user_id": "101",
        "sandbox_session_id": "sandbox-session-3",
        "run_id": "run-3",
        "ssh_port": 4044,
    }
    monkeypatch.setattr(manager, "_get_session", lambda session_id, required=False: asyncio.sleep(0, result=None))
    monkeypatch.setattr(manager, "_load_control_record", lambda session_id: dict(control_row))
    deleted = {"value": False}

    def _fake_delete(session_id: str) -> bool:
        deleted["value"] = True
        return True

    monkeypatch.setattr(manager, "_delete_control_record", _fake_delete)

    released_ports: list[int] = []

    async def _fake_release(port: int) -> None:
        released_ports.append(port)

    monkeypatch.setattr(manager, "_release_ssh_port", _fake_release)

    import tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_runner_client as src

    class _FakeSandboxService:
        def __init__(self) -> None:
            self.cancelled: list[str] = []
            self.destroyed: list[str] = []

        def cancel_run(self, run_id: str) -> None:
            self.cancelled.append(run_id)

        def destroy_session(self, session_id: str) -> None:
            self.destroyed.append(session_id)

    fake_service = _FakeSandboxService()
    monkeypatch.setattr(src.sandbox_ep, "_service", fake_service, raising=True)

    await manager.close_session("acp-session-3")
    assert fake_service.cancelled == ["run-3"]
    assert fake_service.destroyed == ["sandbox-session-3"]
    assert released_ports == [4044]
    assert deleted["value"] is True
