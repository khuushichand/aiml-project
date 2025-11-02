from __future__ import annotations

import os
import types
from typing import Any, Dict, List, Tuple

import pytest

from tldw_Server_API.app.core.Sandbox.runners.docker_runner import DockerRunner
from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType
from tldw_Server_API.app.core.Sandbox.streams import get_hub


def _spec(cmd: List[str]) -> RunSpec:
    return RunSpec(
        session_id=None,
        runtime=RuntimeType.docker,
        base_image="python:3.11-slim",
        command=list(cmd),
        env={},
        timeout_sec=5,
        startup_timeout_sec=1,
        network_policy="deny_all",
    )


@pytest.mark.unit
def test_runner_cancel_term_grace_no_duplicate_end(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure runner uses small grace
    from tldw_Server_API.app.core.config import settings as app_settings
    monkeypatch.setattr(app_settings, "SANDBOX_CANCEL_GRACE_SECONDS", 0, raising=False)

    # Seed an active container mapping
    rid = "run_cancel_1"
    cid = "cid123"
    with DockerRunner._active_lock:  # type: ignore[attr-defined]
        DockerRunner._active_cid[rid] = cid  # type: ignore[attr-defined]

    # Simulate TERM stops container quickly
    states = {"running": True}

    def _is_running(_cid: str) -> bool:
        return states["running"]

    def _subproc_run(args: List[str], check: bool = False, **kwargs: Any):
        # When TERM is sent, mark as not running
        if args[:3] == ["docker", "kill", "--signal"] and args[3] == "TERM":
            states["running"] = False
        # Return a simple object like CompletedProcess
        cp = types.SimpleNamespace(returncode=0)
        return cp

    monkeypatch.setattr(DockerRunner, "_is_container_running", staticmethod(_is_running))
    monkeypatch.setattr("subprocess.run", _subproc_run)

    # Clear any prior frames for this run_id
    hub = get_hub()
    hub._buffers.pop(rid, None)  # type: ignore[attr-defined]

    ok = DockerRunner.cancel_run(rid)
    assert ok is True

    # Runner should NOT publish an end event; service layer does it
    frames = list(hub._buffers.get(rid, []))  # type: ignore[attr-defined]
    assert not any(f.get("type") == "event" and f.get("event") == "end" for f in frames)


@pytest.mark.unit
def test_runner_startup_timeout_on_create(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make docker available and non-fake
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.runners.docker_runner.docker_available", lambda: True)

    import subprocess

    def _raise_timeout(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "docker create", timeout=1)

    monkeypatch.setattr("subprocess.check_output", _raise_timeout)

    dr = DockerRunner()
    rid = "run_to_create_to"
    hub = get_hub()
    hub._buffers.pop(rid, None)  # type: ignore[attr-defined]
    rs = dr.start_run(rid, _spec(["python", "-c", "print('x')"]))
    assert rs.phase.value == "timed_out"
    assert (rs.message or "").startswith("startup_timeout")
    # Ensure WS end has reason=startup_timeout
    frames = list(hub._buffers.get(rid, []))  # type: ignore[attr-defined]
    assert any(f.get("type") == "event" and f.get("event") == "end" and f.get("data", {}).get("reason") == "startup_timeout" for f in frames)


@pytest.mark.unit
def test_runner_execution_timeout_on_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make docker available and non-fake
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.runners.docker_runner.docker_available", lambda: True)

    # Simulate docker create returns a CID, cp/start succeed, wait times out
    def _check_output(args: List[str], text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] not in ("image",):
            # docker create returns a CID once
            return "cid999"
        # image inspect can return some digest; return empty to skip
        return ""

    def _check_call(args: List[str], timeout: int | None = None):
        return 0

    import subprocess

    def _run(args: List[str], capture_output: bool = False, text: bool = False, timeout: int | None = None):
        # docker wait should time out
        if args and args[0] == "docker" and args[1] == "wait":
            raise subprocess.TimeoutExpired(cmd=args, timeout=timeout or 1)
        return types.SimpleNamespace(returncode=0, stdout="0")

    monkeypatch.setattr("subprocess.check_output", _check_output)
    monkeypatch.setattr("subprocess.check_call", _check_call)
    monkeypatch.setattr("subprocess.run", _run)

    dr = DockerRunner()
    rid = "run_to_wait_to"
    hub = get_hub()
    hub._buffers.pop(rid, None)  # type: ignore[attr-defined]
    rs = dr.start_run(rid, _spec(["python", "-c", "print('x')"]))
    assert rs.phase.value == "timed_out"
    assert (rs.message or "") == "execution_timeout"
    frames = list(hub._buffers.get(rid, []))  # type: ignore[attr-defined]
    assert any(f.get("type") == "event" and f.get("event") == "end" and f.get("data", {}).get("reason") == "execution_timeout" for f in frames)
