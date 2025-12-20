import types

from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws


def test_search_web_searx_handles_json_payload(monkeypatch):
    json_payload = {
        "results": [
            {
                "title": "Example Result",
                "url": "https://example.com",
                "content": "Snippet content",
                "publishedDate": "2024-01-01",
            }
        ]
    }

    class DummyResponse:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        text = ""

        def json(self):
            return json_payload

    from tldw_Server_API.app.core.Security import egress as egress_module
    monkeypatch.setattr(
        egress_module,
        "evaluate_url_policy",
        lambda url: types.SimpleNamespace(allowed=True),
    )

    from tldw_Server_API.app.core import http_client as http_client_module
    monkeypatch.setattr(http_client_module, "fetch", lambda *_, **__: DummyResponse())
    monkeypatch.setattr(ws.time, "sleep", lambda *_: None)
    monkeypatch.setattr(ws.random, "uniform", lambda *_: 0.0)

    result = ws.search_web_searx("query", searx_url="https://searx.example")

    assert "results" in result
    assert result["results"][0]["title"] == "Example Result"
    assert result["results"][0]["link"] == "https://example.com"
    assert result["results"][0]["snippet"] == "Snippet content"
    assert result["results"][0]["publishedDate"] == "2024-01-01"
