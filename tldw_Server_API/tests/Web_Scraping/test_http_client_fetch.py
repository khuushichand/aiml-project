import types

import builtins
import pytest

import tldw_Server_API.app.core.http_client as hc


class DummyResp:
    def __init__(self, url: str, headers: dict):
        self.status_code = 200
        self.headers = headers
        self.text = "<html><body>ok</body></html>"
        self.url = url


class DummyClient:
    def __init__(self, timeout=None, trust_env=None, proxies=None):
        self.last_headers = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, method, url, headers=None, cookies=None, follow_redirects=None):
        self.last_headers = headers or {}
        # echo headers back in response for assertions
        return DummyResp(url, self.last_headers)


_DUMMY_HTTP_BACKEND = types.SimpleNamespace(Client=DummyClient)


def test_httpx_fetch_sanitizes_accept_encoding_and_backend_label(monkeypatch):
    # allow egress
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: True)
    # swap client constructor via resolver
    monkeypatch.setattr(hc, "_resolve_httpx", lambda: _DUMMY_HTTP_BACKEND)

    headers = {"Accept-Encoding": "gzip, deflate, br, zstd"}
    resp = hc.fetch("https://example.com/", headers=headers, backend="httpx")
    assert resp["backend"] == "httpx"
    # zstd should be removed for httpx path
    assert "zstd" not in resp["headers"].get("Accept-Encoding", "").lower()


def test_httpx_fetch_accept_encoding_case_and_params(monkeypatch):
    # allow egress
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: True)
    # swap client constructor via resolver
    monkeypatch.setattr(hc, "_resolve_httpx", lambda: _DUMMY_HTTP_BACKEND)

    # Lower-case header key with parameterized zstd; should be dropped and canonicalized
    headers = {"accept-encoding": "gzip, zstd;q=0.9, br"}
    resp = hc.fetch("https://example.com/", headers=headers, backend="httpx")

    # Original exact lower-case key should not remain; canonical should be present
    assert "accept-encoding" not in resp["headers"].keys()
    enc = resp["headers"].get("Accept-Encoding", "")
    assert "zstd" not in enc.lower()
    assert "gzip" in enc.lower() and "br" in enc.lower()


def test_httpx_fetch_accept_encoding_all_removed(monkeypatch):
    # allow egress
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: True)
    # swap client constructor via resolver
    monkeypatch.setattr(hc, "_resolve_httpx", lambda: _DUMMY_HTTP_BACKEND)

    headers = {"Accept-Encoding": "zstd;q=0.9, zstd"}
    resp = hc.fetch("https://example.com/", headers=headers, backend="httpx")

    # Accept-Encoding should be removed entirely if no tokens remain
    keys_lower = {k.lower() for k in resp["headers"].keys()}
    assert "accept-encoding" not in keys_lower


def test_requests_fetch_sanitizes_accept_encoding(monkeypatch):
    # allow egress
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: True)
    # swap client constructor via resolver
    monkeypatch.setattr(hc, "_resolve_httpx", lambda: _DUMMY_HTTP_BACKEND)

    headers = {"Accept-Encoding": "gzip, deflate, br, zstd"}
    resp = hc.fetch("https://example.com/", headers=headers, backend="requests")

    enc = resp["headers"].get("Accept-Encoding", "").lower()
    assert "zstd" not in enc
    assert "br" not in enc


def test_fetch_egress_denied_raises(monkeypatch):
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: False)
    with pytest.raises(ValueError):
        hc.fetch("https://example.com/")


def test_curl_fetch_uses_curl_session_and_preserves_encodings(monkeypatch):
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: True)
    monkeypatch.setattr(hc, "_validate_proxies_or_raise", lambda proxies: None)

    calls = {}

    class DummyCurlSession:
        def __init__(self, impersonate=None):
            calls["impersonate"] = impersonate

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, **kwargs):
            calls["url"] = url
            calls["kwargs"] = kwargs
            return DummyResp(url, kwargs.get("headers", {}))

    monkeypatch.setattr(hc, "_resolve_curl_session", lambda: DummyCurlSession)

    headers = {"Accept-Encoding": "gzip, deflate, br, zstd"}
    resp = hc.fetch(
        "https://example.com/",
        headers=headers,
        backend="curl",
        impersonate="chrome120",
    )

    assert resp["backend"] == "curl"
    assert calls["impersonate"] == "chrome120"
    assert "zstd" in resp["headers"].get("Accept-Encoding", "").lower()
