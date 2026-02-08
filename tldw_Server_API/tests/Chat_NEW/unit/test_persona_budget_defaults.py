"""Unit tests for chat persona exemplar default budget resolution."""

import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint_module


@pytest.mark.unit
def test_persona_default_budget_uses_fallback_when_missing(monkeypatch):
    monkeypatch.delenv("PERSONA_EXEMPLAR_DEFAULT_BUDGET_TOKENS", raising=False)

    resolved = chat_endpoint_module._resolve_persona_default_budget_tokens({})

    assert resolved == 600


@pytest.mark.unit
def test_persona_default_budget_prefers_env_over_config(monkeypatch):
    monkeypatch.setenv("PERSONA_EXEMPLAR_DEFAULT_BUDGET_TOKENS", "777")

    resolved = chat_endpoint_module._resolve_persona_default_budget_tokens(
        {"persona_exemplar_default_budget_tokens": "444"}
    )

    assert resolved == 777


@pytest.mark.unit
def test_persona_default_budget_uses_config_when_env_not_set(monkeypatch):
    monkeypatch.delenv("PERSONA_EXEMPLAR_DEFAULT_BUDGET_TOKENS", raising=False)

    resolved = chat_endpoint_module._resolve_persona_default_budget_tokens(
        {"persona_exemplar_default_budget_tokens": "512"}
    )

    assert resolved == 512


@pytest.mark.unit
def test_persona_default_budget_invalid_values_fallback_or_clamp(monkeypatch):
    monkeypatch.delenv("PERSONA_EXEMPLAR_DEFAULT_BUDGET_TOKENS", raising=False)

    assert chat_endpoint_module._resolve_persona_default_budget_tokens(
        {"persona_exemplar_default_budget_tokens": "not-a-number"}
    ) == 600
    assert chat_endpoint_module._resolve_persona_default_budget_tokens(
        {"persona_exemplar_default_budget_tokens": "0"}
    ) == 1
    assert chat_endpoint_module._resolve_persona_default_budget_tokens(
        {"persona_exemplar_default_budget_tokens": "999999"}
    ) == 20_000
