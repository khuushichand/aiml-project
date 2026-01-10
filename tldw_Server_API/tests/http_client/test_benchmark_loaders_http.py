import os
from typing import Any

import httpx

from tldw_Server_API.app.core.Evaluations.benchmark_loaders import DatasetLoader
import tldw_Server_API.app.core.http_client as http_client


def _mock_transport(responses: dict[str, tuple[int, dict[str, str], bytes]]):
    def handler(request: httpx.Request) -> httpx.Response:
        key = str(request.url)
        status, headers, body = responses.get(key, (404, {"content-type": "text/plain"}, b"not found"))
        return httpx.Response(status_code=status, headers=headers, content=body, request=request)

    return httpx.MockTransport(handler)


def test_load_jsonl_via_http_monkeypatch(monkeypatch):
    monkeypatch.setenv("EGRESS_ALLOWLIST", "example.com")
    url = "http://example.com/data.jsonl"
    payload = b"\n".join([b"{\"a\":1}", b"{\"b\":2}", b"{\"c\":3}"])
    transport = _mock_transport({
        url: (200, {"content-type": "application/x-ndjson"}, payload),
    })

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=transport)

    monkeypatch.setattr(http_client, "create_client", fake_create_client)

    data = DatasetLoader.load_jsonl(url)
    assert isinstance(data, list)
    assert data == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_load_csv_via_http_monkeypatch(monkeypatch):
    monkeypatch.setenv("EGRESS_ALLOWLIST", "example.com")
    url = "http://example.com/data.csv"
    csv_text = "id,name\n1,Alice\n2,Bob\n"
    transport = _mock_transport({
        url: (200, {"content-type": "text/csv"}, csv_text.encode("utf-8")),
    })

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=transport)

    monkeypatch.setattr(http_client, "create_client", fake_create_client)

    rows = DatasetLoader.load_csv(url)
    assert rows == [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]


def test_stream_large_file_jsonl_chunks_via_http(monkeypatch):
    monkeypatch.setenv("EGRESS_ALLOWLIST", "example.com")
    url = "http://example.com/stream.jsonl"
    lines = [b"{\"i\":1}", b"{\"i\":2}", b"{\"i\":3}"]
    payload = b"\n".join(lines)
    transport = _mock_transport({
        url: (200, {"content-type": "application/x-ndjson"}, payload),
    })

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=transport)

    monkeypatch.setattr(http_client, "create_client", fake_create_client)

    chunks = list(DatasetLoader.stream_large_file(url, format="jsonl", chunk_size=2))
    assert len(chunks) == 2
    assert chunks[0] == [{"i": 1}, {"i": 2}]
    assert chunks[1] == [{"i": 3}]
