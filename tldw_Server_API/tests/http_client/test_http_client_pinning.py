import hashlib
import types
import pytest


pytestmark = pytest.mark.unit


def _has_httpx():
    try:
        import httpx  # noqa: F401
        return True
    except Exception:
        return False


requires_httpx = pytest.mark.skipif(not _has_httpx(), reason="httpx not installed")


@requires_httpx
def test_tls_pinning_success(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc
    from tldw_Server_API.app.core.http_client import _check_cert_pinning

    fake_der = b"fakecert"
    pin = hashlib.sha256(fake_der).hexdigest().lower()

    class FakeSSLSocket:
        def __init__(self, der):
            self._der = der

        def getpeercert(self, binary_form=False):
            return self._der if binary_form else None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeSSLContext:
        def __init__(self):
            self.minimum_version = None

        def wrap_socket(self, sock, server_hostname=None):  # noqa: ARG002
            return FakeSSLSocket(fake_der)

    def fake_create_default_context(*args, **kwargs):  # noqa: ARG001
        return FakeSSLContext()

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_create_connection(addr, timeout=None):  # noqa: ARG002
        return FakeSocket()

    import ssl as _ssl
    import socket as _socket

    monkeypatch.setattr(_ssl, "create_default_context", fake_create_default_context)
    monkeypatch.setattr(_socket, "create_connection", fake_create_connection)
    # Avoid invoking the real egress policy (which may perform DNS lookups) in this unit test
    monkeypatch.setattr(hc, "_validate_egress_or_raise", lambda url: None)

    # Should not raise
    _check_cert_pinning("example.com", 443, {pin}, "1.2")


@requires_httpx
def test_tls_pinning_mismatch(monkeypatch):
    from tldw_Server_API.app.core import http_client as hc
    from tldw_Server_API.app.core.http_client import _check_cert_pinning
    from tldw_Server_API.app.core.exceptions import EgressPolicyError

    fake_der = b"anothercert"

    class FakeSSLSocket:
        def __init__(self, der):
            self._der = der

        def getpeercert(self, binary_form=False):
            return self._der if binary_form else None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeSSLContext:
        def __init__(self):
            self.minimum_version = None

        def wrap_socket(self, sock, server_hostname=None):  # noqa: ARG002
            return FakeSSLSocket(fake_der)

    def fake_create_default_context(*args, **kwargs):  # noqa: ARG001
        return FakeSSLContext()

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_create_connection(addr, timeout=None):  # noqa: ARG002
        return FakeSocket()

    import ssl as _ssl
    import socket as _socket

    monkeypatch.setattr(_ssl, "create_default_context", fake_create_default_context)
    monkeypatch.setattr(_socket, "create_connection", fake_create_connection)
    # Avoid invoking the real egress policy in this unit test; we only care about pin mismatch behavior
    monkeypatch.setattr(hc, "_validate_egress_or_raise", lambda url: None)

    with pytest.raises(EgressPolicyError):
        _check_cert_pinning("example.com", 443, {"deadbeef"}, "1.2")


def test_tls_min_version_mapping():
    import ssl
    from tldw_Server_API.app.core.http_client import _tls_min_version_from_str

    assert _tls_min_version_from_str("1.3") == ssl.TLSVersion.TLSv1_3
    assert _tls_min_version_from_str("1.2") == ssl.TLSVersion.TLSv1_2


@requires_httpx
def test_env_pins_attached_to_client(monkeypatch):
    import os
    from tldw_Server_API.app.core.http_client import create_client, _get_client_cert_pins

    monkeypatch.setenv("HTTP_CERT_PINS", "example.com=deadbeef|cafebabe,api.example.com=abcd")
    c = create_client()
    pins = _get_client_cert_pins(c)
    assert pins is not None
    assert "example.com" in pins and "deadbeef" in pins["example.com"]
    assert "api.example.com" in pins and "abcd" in pins["api.example.com"]
