from tldw_Server_API.app.core.Workflows.engine import _is_allowed_transition


def test_state_contract_rejects_invalid_transition() -> None:
    assert _is_allowed_transition("running", "queued") is False
