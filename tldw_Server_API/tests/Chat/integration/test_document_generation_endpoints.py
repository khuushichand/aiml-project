import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_router

pytestmark = pytest.mark.usefixtures("setup_dependencies")


def _make_payload(**overrides):
    base = {
        "conversation_id": 42,
        "document_type": "summary",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key": "sk-test",
        "stream": False,
        "async_generation": False,
    }
    base.update(overrides)
    return base


def test_document_generate_streams_as_sse(monkeypatch, authenticated_client):
    calls = {}

    class StreamingStubService:
        def __init__(self, db):
            self._db = db

        def generate_document(self, *, stream, **kwargs):
            calls["stream"] = stream

            async def _generator():
                yield "first chunk"
                yield b"second chunk"

            return _generator()

    monkeypatch.setattr(chat_router, "DocumentGeneratorService", StreamingStubService)

    response = authenticated_client.post(
        "/api/v1/chat/documents/generate",
        json=_make_payload(stream=True),
    )

    assert response.status_code == 200
    assert calls["stream"] is True
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "data: first chunk\n\n" in body
    assert "data: second chunk\n\n" in body
    assert body.strip().endswith("data: [DONE]")
    response.close()


def test_document_generate_bubbles_service_error(monkeypatch, authenticated_client):
    class FailingStubService:
        def __init__(self, db):
            self._db = db

        def generate_document(self, *args, **kwargs):
            return {"success": False, "error": "No messages found for conversation 42"}

        def get_generated_documents(self, *args, **kwargs):
            return []

    monkeypatch.setattr(chat_router, "DocumentGeneratorService", FailingStubService)

    response = authenticated_client.post(
        "/api/v1/chat/documents/generate",
        json=_make_payload(),
    )

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "No messages found for conversation 42"}
    response.close()
