from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws


def test_websearch_circuit_breaker_shim_removed() -> None:
    assert not hasattr(ws, "_make_simple_circuit_breaker")  # nosec B101
