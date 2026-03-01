from tldw_Server_API.app.core.WebSearch import Web_Search as web_search


def test_deprecated_websearch_session_shims_removed() -> None:
    assert not hasattr(web_search, "create_session")  # nosec B101
    assert not hasattr(web_search, "searx_create_session")  # nosec B101
