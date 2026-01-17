import pytest


@pytest.fixture(autouse=True)
def _http_client_permissive_egress(monkeypatch):
    """Keep http_client unit tests independent of external egress profiles."""
    monkeypatch.setenv("WORKFLOWS_EGRESS_PROFILE", "permissive")
