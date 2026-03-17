from __future__ import annotations

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.identity_provider_schemas import (
    IdentityProviderUpsertRequest,
)


pytestmark = pytest.mark.unit


def test_identity_provider_upsert_normalizes_slug_and_issuer_before_constraints() -> None:
    payload = IdentityProviderUpsertRequest(
        slug=" Corp-IdP ",
        issuer=" https://issuer.example.com ",
    )

    assert payload.slug == "corp-idp"
    assert payload.issuer == "https://issuer.example.com"
    assert payload.owner_scope_id is None


def test_identity_provider_upsert_requires_scope_id_for_org_scope_even_when_omitted() -> None:
    with pytest.raises(ValidationError):
        IdentityProviderUpsertRequest(
            slug="corp",
            issuer="https://issuer.example.com",
            owner_scope_type="org",
        )


def test_identity_provider_upsert_rejects_blank_issuer_after_trimming() -> None:
    with pytest.raises(ValidationError):
        IdentityProviderUpsertRequest(
            slug="corp",
            issuer="   ",
        )
