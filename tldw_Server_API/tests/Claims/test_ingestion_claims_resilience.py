from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.Claims_Extraction.budget_guard import ClaimsJobBudget
from tldw_Server_API.app.core.Claims_Extraction.ingestion_claims import extract_claims_for_chunks
from tldw_Server_API.app.core.config import settings


@pytest.mark.unit
def test_ingestion_provider_error_falls_back_to_heuristic_and_records_error(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    calls: dict[str, Any] = {"provider_errors": []}

    def _failing_chat_api_call(*args, **kwargs):
        raise RuntimeError("provider down")

    def _record_provider_request(**kwargs):
        if kwargs.get("error"):
            calls["provider_errors"].append(kwargs["error"])

    monkeypatch.setattr(ingestion_mod, "chat_api_call", _failing_chat_api_call, raising=False)
    monkeypatch.setattr(ingestion_mod, "record_claims_provider_request", _record_provider_request)
    monkeypatch.setitem(settings, "CLAIMS_JSON_PARSE_MODE", "lenient")

    claims = extract_claims_for_chunks(
        [
            {
                "text": (
                    "Alpha fact sentence for resilience fallback. "
                    "Beta fact sentence for resilience fallback."
                ),
                "metadata": {"chunk_index": 0},
            }
        ],
        extractor_mode="openai",
        max_per_chunk=2,
    )

    assert claims
    assert all(c.get("extractor_mode") == "heuristic" for c in claims)
    assert calls["provider_errors"], "Expected provider error metric to be recorded."


@pytest.mark.unit
def test_ingestion_throttle_falls_back_to_heuristic_and_records_throttle(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    captured: dict[str, Any] = {"throttle": []}

    def _fake_chat_api_call(*args, **kwargs):
        raise AssertionError("Provider call should not execute when throttled.")

    def _record_throttle(**kwargs):
        captured["throttle"].append(kwargs)

    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)
    monkeypatch.setattr(
        ingestion_mod,
        "should_throttle_claims_provider",
        lambda **kwargs: (True, "health"),
    )
    monkeypatch.setattr(ingestion_mod, "record_claims_throttle", _record_throttle)

    claims = extract_claims_for_chunks(
        [
            {
                "text": (
                    "Gamma fact sentence for throttle fallback. "
                    "Delta fact sentence for throttle fallback."
                ),
                "metadata": {"chunk_index": 0},
            }
        ],
        extractor_mode="openai",
        max_per_chunk=2,
    )

    assert claims
    assert all(c.get("extractor_mode") == "heuristic" for c in claims)
    assert captured["throttle"], "Expected throttle metric call."


@pytest.mark.unit
def test_ingestion_budget_exhaustion_falls_back_to_heuristic(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    captured: dict[str, Any] = {"budget": []}
    provider_calls = {"count": 0}

    def _fake_chat_api_call(*args, **kwargs):
        provider_calls["count"] += 1
        return '{"claims":[{"text":"Should not be used"}]}'

    def _record_budget(**kwargs):
        captured["budget"].append(kwargs)

    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)
    monkeypatch.setattr(ingestion_mod, "record_claims_budget_exhausted", _record_budget)

    budget = ClaimsJobBudget(max_tokens=1, strict=True)
    claims = extract_claims_for_chunks(
        [
            {
                "text": (
                    "Epsilon fact sentence for budget fallback. "
                    "Zeta fact sentence for budget fallback."
                ),
                "metadata": {"chunk_index": 0},
            }
        ],
        extractor_mode="openai",
        max_per_chunk=2,
        budget=budget,
    )

    assert claims
    assert all(c.get("extractor_mode") == "heuristic" for c in claims)
    assert provider_calls["count"] == 0
    assert captured["budget"], "Expected budget exhausted metric call."


@pytest.mark.unit
def test_ingestion_parse_error_falls_back_and_records_parse_event(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    captured: dict[str, Any] = {"parse": [], "fallback": []}

    def _fake_chat_api_call(*args, **kwargs):
        return "not valid json"

    def _record_parse(**kwargs):
        captured["parse"].append(kwargs)

    def _record_fallback(**kwargs):
        captured["fallback"].append(kwargs)

    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)
    monkeypatch.setattr(ingestion_mod, "record_claims_output_parse_event", _record_parse)
    monkeypatch.setattr(ingestion_mod, "record_claims_fallback", _record_fallback)

    claims = extract_claims_for_chunks(
        [
            {
                "text": (
                    "Eta fact sentence for parse fallback. "
                    "Theta fact sentence for parse fallback."
                ),
                "metadata": {"chunk_index": 0},
            }
        ],
        extractor_mode="openai",
        max_per_chunk=2,
    )

    assert claims
    assert all(c.get("extractor_mode") == "heuristic" for c in claims)
    assert any(item.get("outcome") == "error" for item in captured["parse"])
    assert any(item.get("reason") == "parse_error" for item in captured["fallback"])


@pytest.mark.unit
def test_ingestion_records_response_format_selection(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    captured: dict[str, Any] = {"format": []}

    def _fake_chat_api_call(*args, **kwargs):
        return '{"claims":[{"text":"Metric claim one."}]}'

    def _record_format(**kwargs):
        captured["format"].append(kwargs)

    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)
    monkeypatch.setattr(
        ingestion_mod,
        "record_claims_response_format_selection",
        _record_format,
    )

    claims = extract_claims_for_chunks(
        [{"text": "Metric claim one.", "metadata": {"chunk_index": 0}}],
        extractor_mode="openai",
        max_per_chunk=1,
    )

    assert claims
    assert any(item.get("mode") == "ingestion" for item in captured["format"])
