import json
import pytest
from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import _sse_orchestrator_stream


def _override_user_admin():
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=2, username="admin", email="a@x", is_active=True, is_admin=True)
    return _f


@pytest.mark.unit
def test_orchestrator_sse_first_event_direct(redis_client):
    redis_client.run(redis_client.xadd("embeddings:embedding", {"seq": "0"}))

    async def _take_first():
        agen = _sse_orchestrator_stream(redis_client.client)
        first = await agen.__anext__()
        return first
    data_line = redis_client.run(_take_first())
    assert isinstance(data_line, str)
    # Find the data line even if an 'event:' prefix is present
    lines = [l for l in data_line.splitlines() if l.strip()]
    data_lines = [l for l in lines if l.startswith('data: ')]
    assert data_lines, f"No data line in SSE chunk: {data_line!r}"
    payload = json.loads(data_lines[0][6:])
    assert 'queues' in payload and 'dlq' in payload and 'stages' in payload
    assert 'embeddings:embedding' in payload['queues']


@pytest.mark.unit
@pytest.mark.parametrize('stage', ['chunking', 'embedding', 'storage'])
def test_orchestrator_sse_flags_reflected(redis_client, stage):

    async def _take_first_after_flags():
        # Set flags for the specific stage
        await redis_client.set(f"embeddings:stage:{stage}:paused", "1")
        await redis_client.set(f"embeddings:stage:{stage}:drain", "1")
        agen = _sse_orchestrator_stream(redis_client.client)
        first = await agen.__anext__()
        return first

    data_line = redis_client.run(_take_first_after_flags())
    lines = [l for l in data_line.splitlines() if l.strip()]
    data_lines = [l for l in lines if l.startswith('data: ')]
    assert data_lines, f"No data line in SSE chunk: {data_line!r}"
    payload = json.loads(data_lines[0][6:])
    assert payload['flags'][stage]['paused'] is True
    assert payload['flags'][stage]['drain'] is True
