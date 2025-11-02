from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import is_allowed_by_robots


class _Resp:
    def __init__(self, status: int, text: str, url: str):
        self.data = {"status": status, "text": text, "url": url, "headers": {}}
    def __getitem__(self, k):
        return self.data[k]


def test_is_allowed_by_robots_allows_when_unreachable(monkeypatch):
    def fake_fetch(url, **kwargs):
        raise RuntimeError("network error")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib.http_fetch",
        fake_fetch,
    )
    assert is_allowed_by_robots("https://example.com/page", "UA") is True


def test_is_allowed_by_robots_disallows_when_explicit(monkeypatch):
    robots_txt = """
User-agent: UA
Disallow: /page
""".strip()

    def fake_fetch(url, **kwargs):
        return _Resp(200, robots_txt, url)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib.http_fetch",
        fake_fetch,
    )
    assert is_allowed_by_robots("https://example.com/page", "UA") is False
