import json
from pathlib import Path

from tldw_Server_API.app.core.RAG.rag_service.payload_exemplars import maybe_record_exemplar, _redact


def test_redact_basic():
    s = "Contact me at test@example.com, visit https://example.com and number 12345678"
    out = _redact(s)
    assert "[EMAIL]" in out
    assert "[URL]" in out
    assert "[NUM]" in out


def test_exemplar_writes(tmp_path, monkeypatch):
    sink = tmp_path / "ex.jsonl"
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
