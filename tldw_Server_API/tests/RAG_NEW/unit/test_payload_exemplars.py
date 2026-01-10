import json
from pathlib import Path

import tldw_Server_API.app.core.RAG.rag_service.payload_exemplars as payload_exemplars
from tldw_Server_API.app.core.RAG.rag_service.payload_exemplars import (
    _redact,
    maybe_record_exemplar,
)


def test_redact_basic():


     s = "Contact me at test@example.com, visit https://example.com and number 12345678"
    out = _redact(s)
    assert "[EMAIL]" in out
    assert "[URL]" in out
    assert "[NUM]" in out


def test_exemplar_writes(tmp_path, monkeypatch):


     base_dir = tmp_path / "observability"
    sink = base_dir / "ex.jsonl"
    monkeypatch.setattr(payload_exemplars, "BASE_DIR", base_dir)
    monkeypatch.setattr(payload_exemplars, "SINK", base_dir / "rag_payload_exemplars.jsonl")
    monkeypatch.setenv("RAG_PAYLOAD_EXEMPLAR_PATH", str(sink))
    monkeypatch.setenv("RAG_PAYLOAD_EXEMPLAR_SAMPLING", "1.0")  # force write

    class D:
        def __init__(self, id, score, content):
                     self.id = id
            self.score = score
            self.content = content

    docs = [D("a", 0.7, "hello world"), D("b", 0.6, "bye world")]
    maybe_record_exemplar(query="q", documents=docs, answer="A", reason="test", user_id="u1")
    assert sink.exists()
    data = [json.loads(line) for line in sink.read_text().splitlines() if line.strip()]
    assert len(data) >= 1
    assert data[-1]["reason"] == "test"
    # When explicit path override is used, namespace is still recorded but does not affect sink
    assert "namespace" in data[-1]


def test_safe_sink_enforces_base_dir(tmp_path, monkeypatch):


     base_dir = tmp_path / "observability"
    sink = base_dir / "rag_payload_exemplars.jsonl"
    monkeypatch.setattr(payload_exemplars, "BASE_DIR", base_dir)
    monkeypatch.setattr(payload_exemplars, "SINK", sink)
    monkeypatch.setenv("RAG_PAYLOAD_EXEMPLAR_PATH", str(tmp_path / "outside.jsonl"))

    path = payload_exemplars._safe_sink()
    assert path == sink

    inside = base_dir / "custom.jsonl"
    monkeypatch.setenv("RAG_PAYLOAD_EXEMPLAR_PATH", str(inside))
    path = payload_exemplars._safe_sink()
    assert path == inside.resolve()


def test_safe_sink_namespace_and_user_fallback(tmp_path, monkeypatch):


     base_dir = tmp_path / "observability"
    sink = base_dir / "rag_payload_exemplars.jsonl"
    monkeypatch.setattr(payload_exemplars, "BASE_DIR", base_dir)
    monkeypatch.setattr(payload_exemplars, "SINK", sink)
    monkeypatch.delenv("RAG_PAYLOAD_EXEMPLAR_PATH", raising=False)

    path = payload_exemplars._safe_sink(namespace="tenant-1")
    assert path == base_dir / "tenants" / "tenant-1" / "rag_payload_exemplars.jsonl"

    path = payload_exemplars._safe_sink(user_id="user-1")
    assert path == base_dir / "users" / "user-1" / "rag_payload_exemplars.jsonl"

    path = payload_exemplars._safe_sink(namespace="!!!")
    assert path == sink
