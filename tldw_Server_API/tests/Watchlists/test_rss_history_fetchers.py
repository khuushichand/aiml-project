import asyncio
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Watchlists import fetchers as F


pytestmark = pytest.mark.unit


class _FakeResp:
    def __init__(self, status_code: int, text: str, headers: dict | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class _FakeAsyncClient:
    def __init__(self, mapping):
        self._mapping = mapping

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        entry = self._mapping.get(url)
        if entry is None:
            return _FakeResp(404, "", {})
        return _FakeResp(entry.get("status", 200), entry.get("text", ""), entry.get("headers", {}))


def _atom_feed(page: int, prev_href: str | None = None) -> str:
    prev = f'<link rel="prev-archive" href="{prev_href}" />' if prev_href else ""
    return f"""
<feed xmlns='http://www.w3.org/2005/Atom'>
  <title>Example Feed</title>
  {prev}
  <entry>
    <title>Item {page}</title>
    <link rel='alternate' href='https://example.com/item{page}' />
    <id>urn:item:{page}</id>
    <updated>2024-01-01T00:00:00Z</updated>
  </entry>
</feed>
""".strip()


@pytest.mark.asyncio
async def test_atom_links_extraction_and_follow(monkeypatch):
    base = "https://feed.example.com/atom"
    p2 = "https://feed.example.com/atom?page=2"

    mapping = {
        base: {"status": 200, "text": _atom_feed(1, prev_href=p2), "headers": {"ETag": "e1"}},
        p2: {"status": 200, "text": _atom_feed(2, prev_href=None), "headers": {}},
    }

    monkeypatch.setattr(F, "httpx", SimpleNamespace(AsyncClient=lambda timeout, follow_redirects: _FakeAsyncClient(mapping)))
    # Allow outgoing URL by bypassing egress policy in test
    monkeypatch.setattr(F, "is_url_allowed_for_tenant", lambda url, tenant_id: True)
    monkeypatch.setattr(F, "is_url_allowed", lambda url: True)

    # Single fetch parses atom_links
    res1 = await F.fetch_rss_feed(base)
    assert res1["status"] == 200
    links = res1.get("atom_links") or []
    assert any(l.get("rel") == "prev-archive" and l.get("href") == p2 for l in links)

    # History follow picks up page 2 and aggregates
    res2 = await F.fetch_rss_feed_history(base, strategy="atom", max_pages=5)
    assert res2["status"] == 200
    assert res2.get("pages_fetched") >= 2
    urls = [it.get("url") for it in res2.get("items", [])]
    assert "https://example.com/item1" in urls and "https://example.com/item2" in urls


@pytest.mark.asyncio
async def test_wordpress_paged_urls_behavior(monkeypatch):
    base = "https://blog.example.com/feed/"
    called = []

    async def fake_fetch(url: str, **kwargs):
        called.append(url)
        # pretend each page has one unique item based on URL
        key = url.split("paged=")[-1] if "paged=" in url else "1"
        return {
            "status": 200,
            "items": [{"title": f"P{key}", "url": f"https://blog.example.com/p{key}", "summary": ""}],
        }

    monkeypatch.setattr(F, "fetch_rss_feed", fake_fetch)
    res = await F.fetch_rss_feed_history(base, strategy="wordpress", max_pages=3)
    assert res["status"] == 200
    assert res.get("pages_fetched") >= 2
    # Ensure generator hit paged=2 and paged=3 forms
    joined = "|".join(called)
    assert "paged=2" in joined and "paged=3" in joined
