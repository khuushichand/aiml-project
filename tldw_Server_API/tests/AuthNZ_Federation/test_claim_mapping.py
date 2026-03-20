from __future__ import annotations

import pytest

from tldw_Server_API.app.core.AuthNZ.federation.claim_mapping import preview_claim_mapping


pytestmark = [pytest.mark.unit]


def test_preview_claim_mapping_rejects_boolean_org_and_team_ids() -> None:
    result = preview_claim_mapping(
        {
            "default_org_ids": [True, 7, "9"],
            "default_team_ids": [False, "11", 13],
        },
        {"sub": "user-123", "email": "user@example.com"},
    )

    assert result["derived_org_ids"] == [7, 9]
    assert result["derived_team_ids"] == [11, 13]


def test_preview_claim_mapping_treats_blank_subject_and_email_as_missing() -> None:
    result = preview_claim_mapping(
        {"subject": "external_subject", "email": "mail"},
        {"external_subject": "   ", "mail": "\t"},
    )

    assert result["subject"] is None
    assert result["email"] is None
    assert "No subject claim resolved from the payload" in result["warnings"]
    assert "No email claim resolved from the payload" in result["warnings"]
