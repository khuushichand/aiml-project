import pytest

from tldw_Server_API.app.core.Evaluations.config_validator import EvaluationConfigValidator


def _clear_rate_limit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = (
        "RG_ENABLED",
        "RG_POLICY_PATH",
    )
    for key in keys:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.unit
def test_rate_limit_validation_warns_when_rg_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_rate_limit_env(monkeypatch)
    validator = EvaluationConfigValidator()

    validator._validate_rate_limiting()

    messages = [issue.message for issue in validator.issues]
    assert "Resource Governor rate limiting is disabled" in messages


@pytest.mark.unit
def test_rate_limit_validation_warns_when_policy_path_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_rate_limit_env(monkeypatch)
    monkeypatch.setenv("RG_ENABLED", "true")
    monkeypatch.setenv("RG_POLICY_PATH", "/tmp/does-not-exist-rg-policy.yaml")  # nosec B108
    validator = EvaluationConfigValidator()

    validator._validate_rate_limiting()

    assert any(
        issue.message.startswith("Resource Governor policy file not found")
        for issue in validator.issues
    )


@pytest.mark.unit
def test_rate_limit_validation_passes_when_rg_enabled_without_legacy_knobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_rate_limit_env(monkeypatch)
    monkeypatch.setenv("RG_ENABLED", "true")
    validator = EvaluationConfigValidator()

    validator._validate_rate_limiting()

    assert validator.issues == []
