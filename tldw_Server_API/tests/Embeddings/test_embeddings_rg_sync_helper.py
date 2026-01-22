import pytest

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as emb_create


@pytest.mark.asyncio
async def test_rg_sync_helper_runs_in_event_loop(monkeypatch):
    monkeypatch.setattr(emb_create, "_rg_embeddings_server_enabled", lambda: True)

    async def _fake_rg():
        return {"allowed": True, "retry_after": None}

    monkeypatch.setattr(emb_create, "_maybe_enforce_with_rg_embeddings_server_async", _fake_rg)

    decision = emb_create._maybe_enforce_with_rg_embeddings_server_sync()
    assert decision is not None
    assert decision.get("allowed") is True
