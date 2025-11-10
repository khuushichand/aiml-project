from typing import Any


class _DummyProvider:
    # Reuse ChatProvider.normalize_error via composition to avoid abstract base
    from tldw_Server_API.app.core.LLM_Calls.providers.base import ChatProvider as _Base

    def __init__(self) -> None:
        class _Impl(self._Base):  # type: ignore
            name = "dummy"
            def capabilities(self):
                return {}
            def chat(self, request, *, timeout=None):  # pragma: no cover - not used
                return {}
            def stream(self, request, *, timeout=None):  # pragma: no cover - not used
                return []
        self._impl = _Impl()

    def norm(self, exc: Exception):
        return self._impl.normalize_error(exc)


def _requests_http_error(status_code: int) -> Exception:
    import requests
    resp = requests.models.Response()
    resp.status_code = status_code
    resp._content = b"{\"error\":{\"message\":\"x\"}}"
    return requests.exceptions.HTTPError(response=resp)


def test_normalize_requests_http_errors():
    p = _DummyProvider()
    assert p.norm(_requests_http_error(400)).__class__.__name__ == "ChatBadRequestError"
    assert p.norm(_requests_http_error(401)).__class__.__name__ == "ChatAuthenticationError"
    assert p.norm(_requests_http_error(403)).__class__.__name__ == "ChatAuthenticationError"
    assert p.norm(_requests_http_error(429)).__class__.__name__ == "ChatRateLimitError"
    assert p.norm(_requests_http_error(500)).__class__.__name__ == "ChatProviderError"


def _httpx_status_error(status_code: int) -> Exception:
    import httpx
    # Build a minimal response and associated HTTPStatusError
    request = httpx.Request("POST", "https://example.com/chat/completions")
    response = httpx.Response(status_code, request=request, content=b'{"error":{"message":"x"}}')
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return e
    raise AssertionError("Expected HTTPStatusError was not raised")


def test_normalize_httpx_http_errors():
    p = _DummyProvider()
    assert p.norm(_httpx_status_error(400)).__class__.__name__ == "ChatBadRequestError"
    assert p.norm(_httpx_status_error(401)).__class__.__name__ == "ChatAuthenticationError"
    assert p.norm(_httpx_status_error(403)).__class__.__name__ == "ChatAuthenticationError"
    assert p.norm(_httpx_status_error(429)).__class__.__name__ == "ChatRateLimitError"
    # 5xx
    err = p.norm(_httpx_status_error(503))
    assert err.__class__.__name__ == "ChatProviderError"
    assert getattr(err, "status_code", None) in (503, None)
