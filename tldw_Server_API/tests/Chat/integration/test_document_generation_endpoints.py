import datetime
import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_router
from tldw_Server_API.tests._plugins.chat_fixtures import get_auth_headers

pytestmark = pytest.mark.usefixtures("setup_dependencies")


def _make_payload(**overrides):
    base = {
        "conversation_id": "chat-42",
        "document_type": "summary",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key": "sk-test",
        "stream": False,
        "async_generation": False,
    }
    base.update(overrides)
    return base


def test_document_generate_streams_as_sse(monkeypatch, authenticated_client, auth_token):
    calls = {}

    class StreamingStubService:
        stored_docs: list[dict] = []
        next_id: int = 1

        def __init__(self, db):
            self._db = db

        def generate_document(self, *, stream, **kwargs):
            calls["stream"] = stream

            async def _generator():
                yield "first chunk"
                yield b"second chunk"

            return _generator()

        def record_streamed_document(
            self,
            *,
            conversation_id,
            document_type,
            content,
            provider,
            model,
            generation_time_ms,
            token_count=None,
        ):
            doc_id = StreamingStubService.next_id
            StreamingStubService.next_id += 1
            StreamingStubService.stored_docs.append(
                {
                    "id": doc_id,
                    "conversation_id": conversation_id,
                    "document_type": document_type.value if hasattr(document_type, "value") else document_type,
                    "title": "Streamed Document",
                    "content": content,
                    "provider": provider,
                    "model": model,
                    "generation_time_ms": generation_time_ms,
                    "token_count": token_count,
                    "created_at": datetime.datetime.utcnow(),
                    "metadata": {},
                }
            )
            return doc_id

        def get_generated_documents(self, conversation_id=None, document_type=None, limit=50):
            docs = list(StreamingStubService.stored_docs)
            if conversation_id is not None:
                docs = [doc for doc in docs if doc["conversation_id"] == conversation_id]
            if document_type is not None:
                dtype = document_type.value if hasattr(document_type, "value") else document_type
                docs = [doc for doc in docs if doc["document_type"] == dtype]
            docs.sort(key=lambda item: item["id"], reverse=True)
            return docs[:limit]

    monkeypatch.setattr(chat_router, "DocumentGeneratorService", StreamingStubService)
    StreamingStubService.stored_docs = []
    StreamingStubService.next_id = 1

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

    headers = get_auth_headers(auth_token, getattr(authenticated_client, "csrf_token", ""))
    list_response = authenticated_client.get(
        "/api/v1/chat/documents",
        params={"conversation_id": "chat-42"},
        headers=headers,
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["documents"][0]["content"] == "first chunksecond chunk"
    assert StreamingStubService.stored_docs, "Streamed document was not persisted"


def test_document_generate_bubbles_service_error(monkeypatch, authenticated_client):
    class FailingStubService:
        record_calls = 0

        def __init__(self, db):
            self._db = db

        def generate_document(self, *args, **kwargs):
            return {"success": False, "error": "No messages found for conversation chat-42"}

        def get_generated_documents(self, *args, **kwargs):
            return []

        def record_streamed_document(self, *args, **kwargs):
            FailingStubService.record_calls += 1
            return None

    monkeypatch.setattr(chat_router, "DocumentGeneratorService", FailingStubService)
    FailingStubService.record_calls = 0

    response = authenticated_client.post(
        "/api/v1/chat/documents/generate",
        json=_make_payload(),
    )

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "No messages found for conversation chat-42"}
    response.close()
    assert FailingStubService.record_calls == 0


def test_document_generate_uses_configured_api_key(monkeypatch, authenticated_client):
    captured = {}

    class KeyCaptureService:
        def __init__(self, db):
            self._db = db

        def generate_document(self, *, stream, **kwargs):
            captured["api_key"] = kwargs.get("api_key")
            captured["provider"] = kwargs.get("provider")
            return "Generated content"

        def get_generated_documents(self, conversation_id=None, document_type=None, limit=50):
            return [
                {
                    "id": 101,
                    "conversation_id": conversation_id,
                    "document_type": document_type.value if hasattr(document_type, "value") else document_type,
                    "title": "Doc",
                    "content": "Generated content",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "generation_time_ms": 123,
                    "created_at": datetime.datetime.utcnow(),
                }
            ]

    from tldw_Server_API.app.api.v1.schemas import chat_request_schemas as chat_schemas

    monkeypatch.setattr(chat_router, "DocumentGeneratorService", KeyCaptureService)
    monkeypatch.setitem(chat_router.API_KEYS, "openai", "sk-configured")
    monkeypatch.setitem(chat_schemas.API_KEYS, "openai", "sk-configured")

    payload = _make_payload()
    payload.pop("api_key", None)

    response = authenticated_client.post(
        "/api/v1/chat/documents/generate",
        json=payload,
    )

    assert response.status_code == 200, response.text
    assert captured["api_key"] == "sk-configured"
    assert captured["provider"] == "openai"
