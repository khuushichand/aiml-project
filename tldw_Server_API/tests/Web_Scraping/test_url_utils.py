import pytest

from tldw_Server_API.app.core.Web_Scraping.url_utils import normalize_for_crawl


@pytest.mark.unit
def test_normalize_resolves_relative_and_strips_fragment_and_tracking():
    src = "https://Example.COM/base/index.html"
    url = "../A/B?utm_source=x&foo=1#section"
    out = normalize_for_crawl(url, src)
    # host lowercased, default ports removed, fragment stripped, utm removed, path normalized
    assert out == "https://example.com/A/B?foo=1"


@pytest.mark.unit
def test_normalize_collapse_slashes_and_trailing_slash():
    src = "http://example.com/"
    url = "//example.com//a///b/"
    out = normalize_for_crawl(url, src)
    # Collapse duplicates and strip trailing slash (non-root)
    assert out == "http://example.com/a/b"


@pytest.mark.unit
def test_normalize_removes_default_ports():
    assert normalize_for_crawl("http://example.com:80/a", "http://x") == "http://example.com/a"
    assert normalize_for_crawl("https://example.com:443/a/", "http://x") == "https://example.com/a"
