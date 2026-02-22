import asyncio
from typing import Any, Optional

import pytest

from tldw_Server_API.app.core.Claims_Extraction.claims_engine import ClaimsEngine


class Doc:
    def __init__(self, id: str, content: str, score: float = 0.0):
        self.id = id
        self.content = content
        self.score = score


def _analyze_stub(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                  api_key: Optional[str] = None, system_message: Optional[str] = None,
                  temp: Optional[float] = None, **kwargs):
    # Extraction path (LLM-based extractor)
    if system_message and "extract" in system_message.lower() and isinstance(custom_prompt_arg, str):
        return '{"claims": [{"text": "Stub claim one."}]}'
    # Judge path
    if system_message and "fact-checking judge" in system_message:
        return '{"label": "supported", "confidence": 0.9, "rationale": "stub"}'
    return '{"claims": []}'


@pytest.mark.unit
def test_claims_engine_llm_only_labels_supported():
    engine = ClaimsEngine(_analyze_stub)
    answer = "Alpha. Beta."
    query = "Q"
    documents = [Doc("d1", "Alpha Beta context", 0.5)]

    async def _run():
        result = await engine.run(
            answer=answer,
            query=query,
            documents=documents,
            claim_extractor="auto",
            claim_verifier="llm",
            claims_top_k=2,
            claims_conf_threshold=0.5,
            claims_max=5,
        )
        claims = result.get("claims") or []
        assert claims, "No claims returned"
        assert all(c.get("label") in {"supported", "refuted", "nei"} for c in claims)
        # Our stub judge always marks supported
        assert any(c.get("label") == "supported" for c in claims)

    asyncio.run(_run())


@pytest.mark.unit
def test_claims_engine_nli_only_without_model_returns_nei():
    # No transformers/NLI model available in test env, so NLI path should return NEI without LLM fallback
    def _analyze_noop(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                      api_key: Optional[str] = None, system_message: Optional[str] = None,
                      temp: Optional[float] = None, **kwargs):
                          return '{"claims": []}'

    engine = ClaimsEngine(_analyze_noop)
    answer = "Acme was founded in 2000."
    query = "When was Acme founded?"
    documents = [Doc("d1", "Acme context", 0.1)]

    async def _run():
        result = await engine.run(
            answer=answer,
            query=query,
            documents=documents,
            claim_extractor="auto",  # LLM path returns empty -> fallback to heuristic
            claim_verifier="nli",
            claims_top_k=2,
            claims_conf_threshold=0.7,
            claims_max=3,
        )
        claims = result.get("claims") or []
        assert claims, "Expected at least one heuristic claim"
        assert all(c.get("label") == "nei" for c in claims)

    asyncio.run(_run())


@pytest.mark.unit
def test_claims_engine_uses_structured_response_format():
    observed_formats = []

    def _analyze_with_capture(
        api_name: str,
        input_data: Any,
        custom_prompt_arg: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        **kwargs,
    ):
        observed_formats.append(kwargs.get("response_format"))
        if system_message and "fact-checking judge" in system_message:
            return '{"label": "nei", "confidence": 0.4, "rationale": "stub"}'
        return '{"claims": [{"text": "Captured claim."}]}'

    engine = ClaimsEngine(_analyze_with_capture)
    documents = [Doc("d1", "Captured claim context.", 0.5)]

    async def _run():
        result = await engine.run(
            answer="Captured claim.",
            query="Q",
            documents=documents,
            claim_extractor="llm",
            claim_verifier="llm",
            claims_max=2,
        )
        assert result.get("claims")

    asyncio.run(_run())
    assert any(isinstance(fmt, dict) for fmt in observed_formats if fmt is not None)


@pytest.mark.unit
def test_claims_engine_parse_error_records_parse_event_and_fallback(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.claims_engine as engine_mod

    captured = {"parse": [], "fallback": []}

    def _record_parse(**kwargs):
        captured["parse"].append(kwargs)

    def _record_fallback(**kwargs):
        captured["fallback"].append(kwargs)

    monkeypatch.setattr(engine_mod, "record_claims_output_parse_event", _record_parse)
    monkeypatch.setattr(engine_mod, "record_claims_fallback", _record_fallback)

    def _analyze_invalid_json(
        api_name: str,
        input_data: Any,
        custom_prompt_arg: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        **kwargs,
    ):
        return "not valid json"

    engine = ClaimsEngine(_analyze_invalid_json)
    documents = [Doc("d1", "Context for parse fallback path.", 0.1)]

    async def _run():
        result = await engine.run(
            answer=(
                "Iota fact sentence for extractor fallback. "
                "Kappa fact sentence for extractor fallback."
            ),
            query="Q",
            documents=documents,
            claim_extractor="llm",
            claim_verifier="nli",
            claims_max=2,
        )
        claims = result.get("claims") or []
        assert claims

    asyncio.run(_run())

    assert any(
        item.get("mode") == "extract" and item.get("outcome") == "error"
        for item in captured["parse"]
    )
    assert any(
        item.get("mode") == "extract" and item.get("reason") == "parse_error"
        for item in captured["fallback"]
    )


@pytest.mark.unit
def test_claims_engine_verify_parse_error_records_parse_event_and_fallback(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.claims_engine as engine_mod

    captured = {"parse": [], "fallback": []}

    def _record_parse(**kwargs):
        captured["parse"].append(kwargs)

    def _record_fallback(**kwargs):
        captured["fallback"].append(kwargs)

    monkeypatch.setattr(engine_mod, "record_claims_output_parse_event", _record_parse)
    monkeypatch.setattr(engine_mod, "record_claims_fallback", _record_fallback)

    def _analyze_invalid_verify(
        api_name: str,
        input_data: Any,
        custom_prompt_arg: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        **kwargs,
    ):
        return "not valid json"

    engine = ClaimsEngine(_analyze_invalid_verify)
    documents = [Doc("d1", "Verifier context for parse fallback path.", 0.6)]

    async def _run():
        result = await engine.run(
            answer="Lambda fact sentence for verifier fallback.",
            query="Q",
            documents=documents,
            claim_extractor="heuristic",
            claim_verifier="llm",
            claims_max=2,
        )
        claims = result.get("claims") or []
        assert claims

    asyncio.run(_run())

    assert any(
        item.get("mode") == "verify" and item.get("outcome") == "error"
        for item in captured["parse"]
    )
    assert any(
        item.get("mode") == "verify" and item.get("reason") == "parse_error"
        for item in captured["fallback"]
    )


@pytest.mark.unit
def test_claims_engine_records_response_format_selection(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.claims_engine as engine_mod

    captured: list[dict[str, Any]] = []

    monkeypatch.setattr(
        engine_mod,
        "record_claims_response_format_selection",
        lambda **kwargs: captured.append(kwargs),
    )

    def _analyze_stub(
        api_name: str,
        input_data: Any,
        custom_prompt_arg: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        **kwargs,
    ):
        if system_message and "fact-checking judge" in system_message:
            return '{"label": "nei", "confidence": 0.4, "rationale": "stub"}'
        return '{"claims": [{"text": "Captured metric claim."}]}'

    engine = ClaimsEngine(_analyze_stub)
    documents = [Doc("d1", "Captured metric claim context.", 0.5)]

    async def _run():
        result = await engine.run(
            answer="Captured metric claim context.",
            query="Q",
            documents=documents,
            claim_extractor="llm",
            claim_verifier="llm",
            claims_max=2,
        )
        assert result.get("claims")

    asyncio.run(_run())
    modes = {item.get("mode") for item in captured}
    assert "extract" in modes
    assert "verify" in modes


@pytest.mark.unit
def test_claims_engine_multi_pass_dedupes_first_pass_wins(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.claims_engine as engine_mod

    calls = {"extract": 0}

    monkeypatch.setattr(engine_mod, "_resolve_claims_extraction_passes", lambda: 3)
    monkeypatch.setattr(engine_mod, "_resolve_claims_context_window_chars", lambda: 64)

    def _analyze_multi_pass(
        api_name: str,
        input_data: Any,
        custom_prompt_arg: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        **kwargs,
    ):
        if system_message and "fact-checking judge" in system_message:
            return '{"label": "nei", "confidence": 0.4, "rationale": "stub"}'
        calls["extract"] += 1
        return '{"claims": [{"text": "Repeated multi-pass claim."}]}'

    engine = ClaimsEngine(_analyze_multi_pass)

    async def _run():
        result = await engine.run(
            answer="Repeated multi-pass claim.",
            query="Q",
            documents=[Doc("d1", "Repeated multi-pass claim context.", 0.5)],
            claim_extractor="llm",
            claim_verifier="nli",
            claims_max=5,
        )
        claims = result.get("claims") or []
        assert len(claims) == 1
        assert claims[0].get("text") == "Repeated multi-pass claim."

    asyncio.run(_run())
    assert calls["extract"] == 3


@pytest.mark.unit
def test_claims_engine_summary_includes_refuted_status_count():
    def _analyze_refuted(
        api_name: str,
        input_data: Any,
        custom_prompt_arg: Optional[str] = None,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        temp: Optional[float] = None,
        **kwargs,
    ):
        if system_message and "fact-checking judge" in system_message:
            return '{"label": "refuted", "confidence": 0.95, "rationale": "stub"}'
        return '{"claims": [{"text": "Claim to refute."}]}'

    engine = ClaimsEngine(_analyze_refuted)

    async def _run():
        result = await engine.run(
            answer="Claim to refute.",
            query="Q",
            documents=[Doc("d1", "Contradictory context.", 0.9)],
            claim_extractor="llm",
            claim_verifier="llm",
            claims_max=2,
        )
        summary = result.get("summary") or {}
        assert int(summary.get("refuted_status", 0)) >= 1

    asyncio.run(_run())
