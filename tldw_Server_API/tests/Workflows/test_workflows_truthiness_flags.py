from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.endpoints import workflows as workflows_mod


pytestmark = pytest.mark.unit


def test_artifact_validation_strict_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", "y")

    assert workflows_mod._artifact_validation_strict(None) is True


def test_artifact_validation_strict_non_block_still_disables_enforcement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_VALIDATE_STRICT", "y")

    assert workflows_mod._artifact_validation_strict("non-block") is False
