import json
import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.fixture(scope="module")
def client():
    settings = get_settings()
    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as c:
        yield c


class _FakeProc:
    def __init__(self, captured):
        self._captured = captured
        self.returncode = 0
    async def communicate(self):
        # Build minimal embeddings array: 1 query + N docs, each 8-dim
        n = self._captured.get("n_docs", 3) + 1
        arr = [[0.1]*8 for _ in range(n)]
        payload = json.dumps({"embeddings": arr}).encode()
        return payload, b""


@pytest.mark.unit
def test_bge_prefix_applied(monkeypatch, client: TestClient):
    captured = {"args": None, "n_docs": 3}

    async def fake_cpe(*args, **kwargs):
        # Record full args
        captured["args"] = list(args)
        return _FakeProc(captured)

    # Patch the subprocess creator where it is used
    import tldw_Server_API.app.core.RAG.rag_service.advanced_reranking as ar
    monkeypatch.setattr(ar.asyncio, "create_subprocess_exec", fake_cpe)

    payload = {
        "query": "What do llamas eat?",
        "top_k": 2,
        "passages": [
            {"id": "a", "text": "Llamas eat bananas"},
            {"id": "b", "text": "Llamas in pyjamas"},
            {"id": "c", "text": "A bowl of fruit salad"}
        ],
        # Include 'bge' in model path to trigger auto prefixes
        "model": "/models/bge-small-en-v1.5.gguf"
    }
    resp = client.post("/api/v1/llamacpp/reranking", json=payload)
    assert resp.status_code == 200, resp.text
    args = captured["args"]
    # Flatten to string for easier checking
    flat = " ".join(map(str, args or []))
    assert "query: What do llamas eat?" in flat
    assert "passage: Llamas eat bananas" in flat
