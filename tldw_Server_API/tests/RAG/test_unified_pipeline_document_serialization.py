from __future__ import annotations

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import (
    _serialize_result_document,
)


def test_serialize_result_document_normalizes_dict_backed_documents() -> None:
    serialized = _serialize_result_document(
        {
            "id": "doc-1",
            "text": "Paris is the capital of France.",
            "score": 0.95,
            "source": "media_db",
            "media_id": "10",
            "metadata": {
                "note_id": "note-7",
            },
        }
    )

    assert serialized["id"] == "doc-1"
    assert serialized["content"] == "Paris is the capital of France."
    assert serialized["score"] == 0.95
    assert serialized["metadata"]["source"] == "media_db"
    assert serialized["metadata"]["media_id"] == "10"
    assert serialized["metadata"]["note_id"] == "note-7"
