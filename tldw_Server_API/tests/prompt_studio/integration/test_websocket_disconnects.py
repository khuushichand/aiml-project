import pytest

from tldw_Server_API.app.api.v1.endpoints import prompt_studio_websocket as ws_mod


pytestmark = pytest.mark.integration


def test_websocket_disconnects_decrement_connection_count(prompt_studio_dual_backend_client):
    backend_label, client, _db = prompt_studio_dual_backend_client

    # Access the shared connection manager used by the WebSocket endpoints
    mgr = ws_mod.connection_manager

    before = mgr.get_connection_count()

    # Open a base WebSocket connection and ensure the count increases
    with client.websocket_connect("/api/v1/prompt-studio/ws") as websocket:
        during = mgr.get_connection_count()
        assert during >= before + 1

    # After exiting the context, the server should clean up the connection
    after = mgr.get_connection_count()
    # At minimum, it should have decreased by one and ideally returned to baseline
    assert after <= during - 1
    assert after == before
