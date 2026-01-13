from __future__ import annotations

import pytest


def test_validate_credential_fields_default_allowlist():
    from tldw_Server_API.app.core.AuthNZ.byok_helpers import validate_credential_fields

    fields = {"org_id": "org-123", "project_id": "proj-456"}
    cleaned = validate_credential_fields("unknown-provider", fields)
    assert cleaned == fields

    with pytest.raises(ValueError):
        validate_credential_fields("unknown-provider", {"api_key": "nope"})


def test_validate_credential_fields_required_policy(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ.byok_helpers import validate_credential_fields
    from tldw_Server_API.app.core.LLM_Calls import provider_metadata

    monkeypatch.setitem(
        provider_metadata.BYOK_CREDENTIAL_FIELDS,
        "test-provider",
        {"allowed": {"org_id"}, "required": {"org_id"}},
    )

    cleaned = validate_credential_fields("test-provider", {"org_id": "org-789"})
    assert cleaned == {"org_id": "org-789"}

    with pytest.raises(ValueError):
        validate_credential_fields("test-provider", {})
