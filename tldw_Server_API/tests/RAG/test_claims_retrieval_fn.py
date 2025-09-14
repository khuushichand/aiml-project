import asyncio

from tldw_Server_API.app.core.RAG.rag_service.claims import ClaimsEngine


class DummyDoc:
    def __init__(self, id, content, score=0.5):
        self.id = id
        self.content = content
        self.metadata = {}
        self.score = score


def test_claims_engine_uses_retrieve_fn(monkeypatch):
    # Analyze returns no claims JSON for extractor to fall back to heuristic; judge supports
    def fake_analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, **kw):
        if isinstance(custom_prompt_arg, str) and custom_prompt_arg.startswith("Extract up to"):
            return '{"claims": []}'
        return '{"label": "supported", "confidence": 0.9}'

    engine = ClaimsEngine(fake_analyze)
    answer = "Paris is the capital of France."
    docs = [DummyDoc("0", "noise"), DummyDoc("1", "Paris is the capital of France.", score=0.9)]

    calls = []

    async def retrieve_fn(claim_text: str, top_k: int = 5):
        calls.append(claim_text)
        return [DummyDoc("2", claim_text, score=0.95)]

    out = asyncio.get_event_loop().run_until_complete(
        engine.run(
            answer=answer,
            query="What is the capital?",
            documents=docs,
            claims_top_k=2,
            claims_max=3,
            retrieve_fn=retrieve_fn,
        )
    )

    assert calls, "retrieve_fn was not called"
    assert isinstance(out.get("claims"), list)
