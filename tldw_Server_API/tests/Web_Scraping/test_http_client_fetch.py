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


def test_httpx_fetch_sanitizes_accept_encoding_and_backend_label(monkeypatch):


     # allow egress
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: True)
    # patch httpx.Client
    monkeypatch.setattr(hc.httpx, "Client", DummyClient)

    headers = {"Accept-Encoding": "gzip, deflate, br, zstd"}
    resp = hc.fetch("https://example.com/", headers=headers, backend="httpx")
    assert resp["backend"] == "httpx"
    # zstd should be removed for httpx path
    assert "zstd" not in resp["headers"].get("Accept-Encoding", "").lower()


def test_httpx_fetch_accept_encoding_case_and_params(monkeypatch):


     # allow egress
    monkeypatch.setattr(hc, "_is_url_allowed", lambda url: True)
    # patch httpx.Client
    monkeypatch.setattr(hc.httpx, "Client", DummyClient)

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
    # patch httpx.Client
    monkeypatch.setattr(hc.httpx, "Client", DummyClient)

    headers = {"Accept-Encoding": "zstd;q=0.9, zstd"}
    resp = hc.fetch("https://example.com/", headers=headers, backend="httpx")

    # Accept-Encoding should be removed entirely if no tokens remain
    keys_lower = {k.lower() for k in resp["headers"].keys()}
    assert "accept-encoding" not in keys_lower


def test_fetch_egress_denied_raises(monkeypatch):


     monkeypatch.setattr(hc, "_is_url_allowed", lambda url: False)
    with pytest.raises(ValueError):
        hc.fetch("https://example.com/")
