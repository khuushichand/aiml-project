from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import _websearch_browser_headers


def test_websearch_browser_headers_shape():
    headers = _websearch_browser_headers(accept_lang="en-US,en;q=0.5")
    # Core browser headers
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert "Accept-Language" in headers and "en-US" in headers["Accept-Language"]
    assert "Accept-Encoding" in headers
    assert "sec-ch-ua" in headers
    assert "sec-ch-ua-platform" in headers
    # Provider additions
    assert headers.get("Connection") == "keep-alive"
    assert headers.get("Referer") == "https://www.google.com/"
