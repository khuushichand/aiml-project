import pytest

from tldw_Server_API.app.api.v1.endpoints import auth as auth_endpoints


pytestmark = pytest.mark.unit


def test_is_pytest_context_accepts_tldw_test_mode_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "y")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    assert auth_endpoints._is_pytest_context() is True
