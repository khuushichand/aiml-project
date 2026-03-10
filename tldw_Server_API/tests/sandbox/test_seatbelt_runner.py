from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import tldw_Server_API.app.core.Sandbox.runners.seatbelt_runner as seatbelt_module
from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunSpec, RuntimeType, TrustLevel
from tldw_Server_API.app.core.Sandbox.runners.seatbelt_runner import SeatbeltRunner
from tldw_Server_API.app.core.Sandbox.streams import get_hub


def test_seatbelt_preflight_defaults_to_trusted_only(monkeypatch) -> None:
    monkeypatch.delenv("TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED", raising=False)

    result = SeatbeltRunner().preflight(network_policy="deny_all")

    assert "trusted" in result.supported_trust_levels
    assert "standard" not in result.supported_trust_levels
    assert "untrusted" not in result.supported_trust_levels


def test_seatbelt_preflight_allows_standard_when_explicitly_enabled(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED", "1")

    result = SeatbeltRunner().preflight(network_policy="deny_all")

    assert "trusted" in result.supported_trust_levels
    assert "standard" in result.supported_trust_levels
    assert "untrusted" not in result.supported_trust_levels


def test_seatbelt_preflight_reports_missing_launcher(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_AVAILABLE", "1")
    monkeypatch.setattr(seatbelt_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        seatbelt_module,
        "vz_host_facts",
        lambda: {"os": "darwin", "arch": "arm64", "apple_silicon": True},
    )
    monkeypatch.setattr(seatbelt_module, "_sandbox_exec_exists", lambda: False)

    result = SeatbeltRunner().preflight(network_policy="deny_all")

    assert result.available is False
    assert "sandbox_exec_missing" in result.reasons


def test_seatbelt_preflight_rejects_allowlist_even_when_launcher_exists(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_AVAILABLE", "1")
    monkeypatch.setattr(seatbelt_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        seatbelt_module,
        "vz_host_facts",
        lambda: {"os": "darwin", "arch": "arm64", "apple_silicon": True},
    )
    monkeypatch.setattr(seatbelt_module, "_sandbox_exec_exists", lambda: True)

    result = SeatbeltRunner().preflight(network_policy="allowlist")

    assert result.available is False
    assert "strict_allowlist_not_supported" in result.reasons


def test_seatbelt_fake_run_completes(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_FAKE_EXEC", "1")

    runner = SeatbeltRunner()
    status = runner.start_run(
        run_id="run-seatbelt-1",
        spec=RunSpec(
            session_id=None,
            runtime=RuntimeType.seatbelt,
            base_image=None,
            command=["echo", "ok"],
            network_policy="deny_all",
            trust_level=TrustLevel.trusted,
        ),
    )

    assert status.phase == RunPhase.completed
    assert status.exit_code == 0


def test_seatbelt_start_run_executes_real_subprocess_and_collects_artifacts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TLDW_SANDBOX_SEATBELT_FAKE_EXEC", raising=False)
    monkeypatch.setattr(seatbelt_module, "_sandbox_exec_exists", lambda: True)

    run_root = tmp_path / "seatbelt-run"
    run_root.mkdir()
    workspace_root = run_root / "workspace"
    control_root = run_root / "control"
    home_root = run_root / "home"
    temp_root = run_root / "tmp"

    monkeypatch.setattr(seatbelt_module.tempfile, "mkdtemp", lambda prefix: str(run_root))

    class _FakePopen:
        def __init__(self, argv, cwd=None, env=None, stdout=None, stderr=None, stdin=None, start_new_session=None):
            del stdout, stderr, stdin, start_new_session
            assert argv[0] == "/usr/bin/sandbox-exec"
            assert argv[1] == "-f"
            profile_path = Path(argv[2])
            assert profile_path.parent == control_root
            assert cwd == str(workspace_root)
            assert env is not None
            assert env["HOME"] == str(home_root)
            assert env["TMPDIR"] == str(temp_root)
            assert (workspace_root / "inputs" / "seed.txt").read_bytes() == b"seed"
            (workspace_root / "generated.txt").write_bytes(b"artifact-data")
            self.pid = 4242
            self.returncode = 0

        def communicate(self, timeout=None):
            assert timeout == 7
            return (b"stdout-line\n", b"stderr-line\n")

    monkeypatch.setattr(seatbelt_module.subprocess, "Popen", _FakePopen)

    runner = SeatbeltRunner()
    run_id = "run-seatbelt-real-1"
    hub = get_hub()
    hub._buffers.pop(run_id, None)  # type: ignore[attr-defined]

    status = runner.start_run(
        run_id=run_id,
        spec=RunSpec(
            session_id=None,
            runtime=RuntimeType.seatbelt,
            base_image="host-local",
            command=["/bin/echo", "ok"],
            network_policy="deny_all",
            trust_level=TrustLevel.trusted,
            timeout_sec=7,
            files_inline=[("inputs/seed.txt", b"seed")],
            capture_patterns=["generated.txt"],
        ),
        session_workspace=None,
    )

    assert status.phase == RunPhase.completed
    assert status.exit_code == 0
    assert status.artifacts == {"generated.txt": b"artifact-data"}
    frames = list(hub._buffers.get(run_id, []))  # type: ignore[attr-defined]
    assert any(frame.get("type") == "stdout" and "stdout-line" in frame.get("data", "") for frame in frames)
    assert any(frame.get("type") == "stderr" and "stderr-line" in frame.get("data", "") for frame in frames)
    assert not run_root.exists()


def test_seatbelt_runner_docstring_covers_constraints() -> None:
    doc = SeatbeltRunner.__doc__ or ""

    assert "trusted" in doc
    assert "fake" in doc


def test_seatbelt_fake_run_logs_publish_failures(monkeypatch) -> None:
    monkeypatch.setenv("TLDW_SANDBOX_SEATBELT_FAKE_EXEC", "1")

    class _BrokenHub:
        def publish_event(self, run_id: str, event: str, data: dict | None = None) -> None:
            del run_id, event, data
            raise OSError("hub down")

    mock_logger = MagicMock()
    monkeypatch.setattr(seatbelt_module, "get_hub", lambda: _BrokenHub())
    monkeypatch.setattr(seatbelt_module, "logger", mock_logger, raising=False)

    status = SeatbeltRunner().start_run(
        run_id="run-seatbelt-log-1",
        spec=RunSpec(
            session_id=None,
            runtime=RuntimeType.seatbelt,
            base_image=None,
            command=["echo", "ok"],
            network_policy="deny_all",
            trust_level=TrustLevel.trusted,
        ),
    )

    assert status.phase == RunPhase.completed
    mock_logger.warning.assert_called()
