import pytest


pytestmark = pytest.mark.unit


def test_limits_raise_when_budget_exhausted():
    from tldw_Server_API.app.core.Research.limits import ResearchLimits, ensure_limit_available

    limits = ResearchLimits(max_searches=2, max_fetched_docs=5, max_runtime_seconds=300)
    usage = {"searches": 2}
    exc = ensure_limit_available(limits, usage, "searches")
    assert exc.code == "research_limit_exceeded"
