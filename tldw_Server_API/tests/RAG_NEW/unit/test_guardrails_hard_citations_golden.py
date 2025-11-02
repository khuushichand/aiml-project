from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.RAG.rag_service.guardrails import build_hard_citations


def test_build_hard_citations_offsets_golden():
    text = "We ran 42 experiments. The findings were consistent across trials."
    d = Document(id="gold1", content=text, metadata={"title": "Paper"}, source=DataSource.MEDIA_DB, score=0.9)
    answer = "We ran 42 experiments. The findings were consistent across trials."
    hc = build_hard_citations(answer, [d])
    assert isinstance(hc, dict) and hc.get("sentences")
    for entry in hc["sentences"]:
        s = entry.get("text", "")
        cites = entry.get("citations") or []
        assert cites, "Expected at least one citation per sentence"
        st, en = cites[0].get("start", 0), cites[0].get("end", 0)
        assert text[int(st):int(en)].strip() in {s.strip(), s.strip()[: len(text[int(st):int(en)].strip())]}
