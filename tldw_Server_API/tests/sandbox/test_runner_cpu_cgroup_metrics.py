from __future__ import annotations

import types
import subprocess
from typing import Any, List

import pytest

from tldw_Server_API.app.core.Sandbox.runners.docker_runner import DockerRunner
from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType


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
def test_pre_kill_cpu_snapshot_preferred(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Ensure Docker path is active (non-fake) but do not require a real daemon
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Sandbox.runners.docker_runner.docker_available",
        lambda: True,
    )

    # Create a fake cgroup v2 cpu.stat file and seed baseline usage
    cpu_stat = tmp_path / "cpu.stat"
    cpu_stat.write_text("usage_usec 1000000\n")  # 1.0s baseline

    # Resolve cgroup file to our fake path
    def _resolve_file(_cid: str):
        return (str(cpu_stat), "v2")

    monkeypatch.setattr(DockerRunner, "_resolve_cgroup_cpu_file_by_cid", staticmethod(_resolve_file))

    # Avoid real docker stats usage for memory reading
    monkeypatch.setattr(DockerRunner, "_get_mem_usage_mb", staticmethod(lambda _cid: 0))

    # check_output: docker create returns a CID; image inspect returns empty
    def _check_output(args: List[str], text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] not in ("image",):
            return "cid_test"
        return ""

    # check_call: docker cp/start/kill/rm succeed
    def _check_call(args: List[str], timeout: int | None = None):
        return 0

    # run: docker wait times out; before raising, bump cpu.stat to simulate accumulated CPU
    def _run(args: List[str], capture_output: bool = False, text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] == "wait":
            cpu_stat.write_text("usage_usec 3000000\n")  # 3.0s pre-kill snapshot
            raise subprocess.TimeoutExpired(cmd=args, timeout=timeout or 1)
        return types.SimpleNamespace(returncode=0, stdout="0")

    monkeypatch.setattr("subprocess.check_output", _check_output)
    monkeypatch.setattr("subprocess.check_call", _check_call)
    monkeypatch.setattr("subprocess.run", _run)

    dr = DockerRunner()
    rs = dr.start_run("rid_cpu_delta", _spec(["python", "-c", "print('hi')"]))

    # Expect timeout phase and CPU delta = 2s (3s - 1s)
    assert rs.phase.value == "timed_out"
    assert rs.resource_usage is not None
    assert rs.resource_usage.get("cpu_time_sec") == 2


@pytest.mark.unit
def test_cgroup_v1_delta_on_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Sandbox.runners.docker_runner.docker_available",
        lambda: True,
    )

    # Fake cgroup v1 cpuacct.usage file (nanoseconds)
    cpuacct = tmp_path / "cpuacct.usage"
    cpuacct.write_text(str(1_000_000_000))  # 1s baseline

    def _resolve_file(_cid: str):
        return (str(cpuacct), "v1")

    monkeypatch.setattr(DockerRunner, "_resolve_cgroup_cpu_file_by_cid", staticmethod(_resolve_file))
    monkeypatch.setattr(DockerRunner, "_get_mem_usage_mb", staticmethod(lambda _cid: 0))

    def _check_output(args: List[str], text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] not in ("image",):
            return "cid_v1"
        return ""

    def _check_call(args: List[str], timeout: int | None = None):
        return 0

    # Timeout on wait; bump cpuacct usage to 3s before raising
    def _run(args: List[str], capture_output: bool = False, text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] == "wait":
            cpuacct.write_text(str(3_000_000_000))
            raise subprocess.TimeoutExpired(cmd=args, timeout=timeout or 1)
        return types.SimpleNamespace(returncode=0, stdout="0")

    monkeypatch.setattr("subprocess.check_output", _check_output)
    monkeypatch.setattr("subprocess.check_call", _check_call)
    monkeypatch.setattr("subprocess.run", _run)

    dr = DockerRunner()
    rs = dr.start_run("rid_v1", _spec(["python", "-c", "print('hi')"]))
    assert rs.phase.value == "timed_out"
    assert rs.resource_usage.get("cpu_time_sec") == 2


@pytest.mark.unit
def test_fallback_when_cgroup_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Sandbox.runners.docker_runner.docker_available",
        lambda: True,
    )

    # Do not resolve a cgroup file; use PID-based reader that fails on second call
    monkeypatch.setattr(DockerRunner, "_resolve_cgroup_cpu_file_by_cid", staticmethod(lambda _cid: None))
    # Stateful reader: first call returns 1, second returns None to trigger fallback
    calls = {"n": 0}

    def _read_by_cid(_cid: str) -> int | None:
        calls["n"] += 1
        return 1 if calls["n"] == 1 else None

    monkeypatch.setattr(DockerRunner, "_read_cgroup_cpu_time_sec_by_cid", staticmethod(_read_by_cid))
    # Fallback estimator
    monkeypatch.setattr(DockerRunner, "_get_cpu_time_sec", staticmethod(lambda _cid, _s, _f: 7))

    def _check_output(args: List[str], text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] not in ("image",):
            return "cid_fail"
        return ""

    def _check_call(args: List[str], timeout: int | None = None):
        return 0

    def _run(args: List[str], capture_output: bool = False, text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] == "wait":
            raise subprocess.TimeoutExpired(cmd=args, timeout=timeout or 1)
        return types.SimpleNamespace(returncode=0, stdout="0")

    monkeypatch.setattr("subprocess.check_output", _check_output)
    monkeypatch.setattr("subprocess.check_call", _check_call)
    monkeypatch.setattr("subprocess.run", _run)

    dr = DockerRunner()
    rs = dr.start_run("rid_fail", _spec(["python", "-c", "print('hi')"]))
    assert rs.phase.value == "timed_out"
    # With final None and baseline present, code should use fallback estimator
    assert rs.resource_usage.get("cpu_time_sec") == 7


@pytest.mark.unit
def test_cgroup_v2_delta_on_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Sandbox.runners.docker_runner.docker_available",
        lambda: True,
    )

    cpu_stat = tmp_path / "cpu.stat"
    cpu_stat.write_text("usage_usec 2000000\n")  # 2s baseline

    def _resolve_file(_cid: str):
        return (str(cpu_stat), "v2")

    monkeypatch.setattr(DockerRunner, "_resolve_cgroup_cpu_file_by_cid", staticmethod(_resolve_file))
    monkeypatch.setattr(DockerRunner, "_get_mem_usage_mb", staticmethod(lambda _cid: 0))

    def _check_output(args: List[str], text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] not in ("image",):
            return "cid_success"
        return ""

    def _check_call(args: List[str], timeout: int | None = None):
        return 0

    # run: docker wait returns immediately with exit code 0
    def _run(args: List[str], capture_output: bool = False, text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] == "wait":
            # Before wait returns, bump cpu.stat to 5.5s
            cpu_stat.write_text("usage_usec 5500000\n")
            return types.SimpleNamespace(returncode=0, stdout="0")
        return types.SimpleNamespace(returncode=0, stdout="0")

    monkeypatch.setattr("subprocess.check_output", _check_output)
    monkeypatch.setattr("subprocess.check_call", _check_call)
    monkeypatch.setattr("subprocess.run", _run)

    dr = DockerRunner()
    rs = dr.start_run("rid_success", _spec(["python", "-c", "print('hi')"]))
    assert rs.phase.value in {"completed", "failed"}  # Completed since exit 0
    assert rs.resource_usage.get("cpu_time_sec") == 3


@pytest.mark.unit
def test_baseline_file_but_prekill_read_fails_fallback_used(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Use real path but fake docker
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Sandbox.runners.docker_runner.docker_available",
        lambda: True,
    )

    # Create cpu.stat for baseline only; will delete before pre-kill read
    cpu_stat = tmp_path / "cpu.stat"
    cpu_stat.write_text("usage_usec 2000000\n")  # 2s baseline

    def _resolve_file(_cid: str):
        return (str(cpu_stat), "v2")

    monkeypatch.setattr(DockerRunner, "_resolve_cgroup_cpu_file_by_cid", staticmethod(_resolve_file))
    monkeypatch.setattr(DockerRunner, "_get_mem_usage_mb", staticmethod(lambda _cid: 0))

    # CID resolution etc.
    def _check_output(args: List[str], text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] not in ("image",):
            return "cid_missing_after"
        return ""

    def _check_call(args: List[str], timeout: int | None = None):
        return 0

    # Before raising timeout on wait, delete the cgroup file to make pre-kill read fail
    def _run(args: List[str], capture_output: bool = False, text: bool = False, timeout: int | None = None):
        if args and args[0] == "docker" and args[1] == "wait":
            try:
                cpu_stat.unlink(missing_ok=True)
            except TypeError:
                # For Python <3.8, ignore
                try:
                    cpu_stat.unlink()
                except FileNotFoundError:
                    pass
            raise subprocess.TimeoutExpired(cmd=args, timeout=timeout or 1)
        return types.SimpleNamespace(returncode=0, stdout="0")

    # Fallback estimator should be used
    monkeypatch.setattr(DockerRunner, "_get_cpu_time_sec", staticmethod(lambda _cid, _s, _f: 9))

    monkeypatch.setattr("subprocess.check_output", _check_output)
    monkeypatch.setattr("subprocess.check_call", _check_call)
    monkeypatch.setattr("subprocess.run", _run)

    dr = DockerRunner()
    rs = dr.start_run("rid_missing", _spec(["python", "-c", "print('hi')"]))
    assert rs.phase.value == "timed_out"
    assert rs.resource_usage.get("cpu_time_sec") == 9
