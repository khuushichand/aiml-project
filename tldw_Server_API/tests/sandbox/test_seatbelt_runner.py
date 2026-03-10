from __future__ import annotations

from tldw_Server_API.app.core.Sandbox.models import RunPhase, RunSpec, RuntimeType, TrustLevel
from tldw_Server_API.app.core.Sandbox.runners.seatbelt_runner import SeatbeltRunner


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
