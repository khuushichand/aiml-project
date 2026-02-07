import pytest

from tldw_Server_API.app.api.v1.endpoints.prompt_studio import (
    prompt_studio_evaluations as ps_eval,
)


@pytest.mark.unit
def test_prompt_studio_evaluations_test_mode_accepts_single_letter_y(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "y")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    assert ps_eval._is_prompt_studio_test_mode() is True
