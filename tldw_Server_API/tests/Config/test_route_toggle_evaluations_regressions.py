import pytest

from tldw_Server_API.app.core import config as config_mod


@pytest.fixture(autouse=True)
def _clear_route_policy_cache():
    config_mod._route_toggle_policy.cache_clear()
    yield
    config_mod._route_toggle_policy.cache_clear()


def test_route_enabled_evaluations_respects_disable_in_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ROUTES_DISABLE", "evaluations")
    monkeypatch.delenv("ROUTES_ENABLE", raising=False)

    assert config_mod.route_enabled("evaluations") is False


def test_route_enabled_evaluations_can_be_explicitly_enabled_in_test_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ROUTES_DISABLE", "evaluations")
    monkeypatch.setenv("ROUTES_ENABLE", "evaluations")

    assert config_mod.route_enabled("evaluations") is True


def test_route_enabled_evaluations_not_force_enabled_by_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("TLDW_TEST_MODE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ROUTES_DISABLE", "evaluations")
    monkeypatch.delenv("ROUTES_ENABLE", raising=False)

    assert config_mod.route_enabled("evaluations") is False


def test_routes_stable_only_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ROUTES_ENABLE", raising=False)
    monkeypatch.delenv("ROUTES_DISABLE", raising=False)
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "y")

    # "benchmarks" is experimental by default and not force-enabled in pytest.
    assert config_mod.route_enabled("benchmarks") is False
