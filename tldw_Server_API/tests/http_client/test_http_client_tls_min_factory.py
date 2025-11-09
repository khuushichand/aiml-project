import pytest


pytestmark = pytest.mark.unit


def test_create_client_applies_min_tls(monkeypatch):
    import ssl
    import tldw_Server_API.app.core.http_client as hc

    captured = {}

    def fake_instantiate(factory, kwargs):  # noqa: ARG001
        captured.update(kwargs)
        class Dummy:
            def close(self):
                pass
        return Dummy()

    class FakeCtx:
        def __init__(self):
            self.minimum_version = None

    def fake_create_default_context(*args, **kwargs):  # noqa: ARG001
        return FakeCtx()

    monkeypatch.setattr(hc, "_instantiate_client", fake_instantiate)
    monkeypatch.setattr(hc.ssl, "create_default_context", fake_create_default_context)

    hc.create_client(enforce_tls_min_version=True, tls_min_version="1.3")
    assert isinstance(captured.get("verify"), FakeCtx)
    # _build_ssl_context should have set minimum_version on the fake context
    assert captured["verify"].minimum_version == ssl.TLSVersion.TLSv1_3


@pytest.mark.asyncio
async def test_create_async_client_applies_min_tls(monkeypatch):
    import ssl
    import tldw_Server_API.app.core.http_client as hc

    captured = {}

    def fake_instantiate(factory, kwargs):  # noqa: ARG001
        captured.update(kwargs)
        class Dummy:
            async def aclose(self):
                pass
        return Dummy()

    class FakeCtx:
        def __init__(self):
            self.minimum_version = None

    def fake_create_default_context(*args, **kwargs):  # noqa: ARG001
        return FakeCtx()

    monkeypatch.setattr(hc, "_instantiate_client", fake_instantiate)
    monkeypatch.setattr(hc.ssl, "create_default_context", fake_create_default_context)

    hc.create_async_client(enforce_tls_min_version=True, tls_min_version="1.2")
    assert isinstance(captured.get("verify"), FakeCtx)
    assert captured["verify"].minimum_version == ssl.TLSVersion.TLSv1_2
