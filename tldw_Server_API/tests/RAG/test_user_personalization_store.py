from __future__ import annotations

import json

from tldw_Server_API.app.core.RAG.rag_service.user_personalization_store import UserPersonalizationStore


def test_personalization_store_persists_event_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path))

    store = UserPersonalizationStore("user-1")
    store.record_event(
        event_type="dwell_time",
        doc_id="doc-1",
        chunk_ids=["chunk-1"],
        rank=2,
        session_id="sess-1",
        conversation_id="conv-1",
        message_id="msg-1",
        dwell_ms=3000,
        query="reset auth",
        impression=["doc-1", "doc-2"],
        corpus="media_db",
    )

    data = json.loads(store.path.read_text(encoding="utf-8"))
    assert data.get("event_log")
    entry = data["event_log"][-1]
    assert entry["event_type"] == "dwell_time"
    assert entry["doc_id"] == "doc-1"
    assert entry["chunk_ids"] == ["chunk-1"]
    assert entry["rank"] == 2
    assert entry["dwell_ms"] == 3000
    assert entry["session_id"] == "sess-1"
    assert entry["conversation_id"] == "conv-1"
    assert entry["message_id"] == "msg-1"
    assert entry["query"] == "reset auth"
    assert entry["impression_list"] == ["doc-1", "doc-2"]
