import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.ingestion_claims import (
    extract_claims_for_chunks,
)


@pytest.mark.unit
def test_ingestion_time_ner_extractor_skips_if_unavailable():
    try:
        import spacy  # type: ignore
        try:
            nlp = spacy.load("en_core_web_sm")
            have_model = True
        except Exception:
            have_model = False
    except Exception:
        have_model = False

    if not have_model:
        pytest.skip("spaCy or en_core_web_sm not available; skipping NER extractor test")

    text = "Alice founded Acme Corp in 2020. It is based in Paris."
    chunks = [{"text": text, "metadata": {"chunk_index": 0}}]

    claims = extract_claims_for_chunks(chunks, extractor_mode="ner", max_per_chunk=3)
    assert claims, "NER extractor returned no claims on named-entity rich text"
    # Expect at least one sentence-like claim with entities
    joined = "\n".join(c.get("claim_text", "") for c in claims)
    assert any(s in joined for s in ("Alice", "Acme", "Paris", "2020"))
