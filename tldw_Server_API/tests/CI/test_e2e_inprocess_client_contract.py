import pytest


def test_inprocess_testclient_fallback_enters_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.main import app as shared_app
    from tldw_Server_API.tests.e2e import fixtures

    entered_clients: list[object] = []

    class _FakeStartedClient:
        def __init__(self, app, **kwargs) -> None:
            self.app = app
            self.kwargs = kwargs

        def __enter__(self):
            entered_clients.append(self)
            return self

    def _raise_old_transport(*args, **kwargs):
        raise TypeError("lifespan unsupported")

    monkeypatch.setattr("starlette.testclient.TestClient", _FakeStartedClient)
    helper_globals = fixtures._build_inprocess_httpx_client.__globals__
    original_httpx = helper_globals["httpx"]
    helper_globals["httpx"] = type(
        "_FakeHttpxModule",
        (),
        {"ASGITransport": staticmethod(_raise_old_transport)},
    )()
    try:
        client = fixtures._build_inprocess_httpx_client()
    finally:
        helper_globals["httpx"] = original_httpx

    assert isinstance(client, _FakeStartedClient)
    assert client.app is shared_app
    assert entered_clients == [client]
