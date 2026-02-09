"""Unit tests for persona_id alias deprecation/sunset policy."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint_module


@pytest.mark.unit
def test_persona_alias_resolves_before_removal_and_emits_headers(monkeypatch):
    req = SimpleNamespace(character_id=None, persona_id="123")
    monkeypatch.setattr(chat_endpoint_module, "_persona_alias_today", lambda: date(2026, 2, 9))

    alias_used = chat_endpoint_module._resolve_character_id_from_persona_alias(req)  # type: ignore[arg-type]
    headers = chat_endpoint_module._build_persona_alias_deprecation_headers(alias_used)

    assert alias_used is True
    assert req.character_id == "123"
    assert headers["X-TLDW-Persona-ID-Alias-Deprecated"] == "true"
    assert headers["X-TLDW-Persona-ID-Alias-Sunset-Date"] == "2026-07-01"


@pytest.mark.unit
def test_persona_alias_rejected_on_or_after_removal_date(monkeypatch):
    req = SimpleNamespace(character_id=None, persona_id="123")
    monkeypatch.setattr(chat_endpoint_module, "_persona_alias_today", lambda: date(2026, 7, 1))

    with pytest.raises(HTTPException) as excinfo:
        chat_endpoint_module._resolve_character_id_from_persona_alias(req)  # type: ignore[arg-type]

    assert excinfo.value.status_code == 400
    assert "removed on 2026-07-01" in str(excinfo.value.detail)
