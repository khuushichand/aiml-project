import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.testing import (
    is_explicit_pytest_runtime,
    validate_test_runtime_flags,
)


def _clear_test_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("TLDW_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


def test_validate_test_runtime_flags_allows_without_test_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_test_flags(monkeypatch)
    validate_test_runtime_flags()


@pytest.mark.parametrize("flag_name", ["TEST_MODE", "TESTING", "TLDW_TEST_MODE"])
def test_validate_test_runtime_flags_rejects_outside_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
    flag_name: str,
) -> None:
    _clear_test_flags(monkeypatch)
    monkeypatch.setenv(flag_name, "1")

    with pytest.raises(RuntimeError, match="PYTEST_CURRENT_TEST"):
        validate_test_runtime_flags()


def test_validate_test_runtime_flags_allows_when_pytest_runtime_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_test_flags(monkeypatch)
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "authnz::test_runtime_guard")

    assert is_explicit_pytest_runtime() is True
    validate_test_runtime_flags()


def test_app_startup_hard_fails_when_test_mode_without_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_test_flags(monkeypatch)
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.main import app

    with pytest.raises(RuntimeError, match="PYTEST_CURRENT_TEST"):
        with TestClient(app):
            pass
