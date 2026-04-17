import pytest

from tldw_Server_API.app.core.Evaluations.run_state import (
    can_transition_run_status,
    normalize_run_status,
)


@pytest.mark.unit
def test_normalize_run_status_maps_legacy_canceled_to_cancelled():
    assert normalize_run_status("canceled") == "cancelled"


@pytest.mark.unit
def test_can_transition_run_status_rejects_terminal_status_rewrite():
    assert can_transition_run_status("completed", "cancelled") is False


@pytest.mark.unit
def test_can_transition_run_status_allows_normalized_same_terminal_status():
    assert can_transition_run_status("canceled", "cancelled") is True
