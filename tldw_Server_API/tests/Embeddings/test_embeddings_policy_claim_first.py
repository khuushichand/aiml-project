from __future__ import annotations

import pytest

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


@pytest.mark.unit
def test_policy_bypass_claim_first_prefers_admin_role_on_principal():
    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as emb_mod

    user = User(id=9, username="u", email="u@example.com", is_active=True, is_admin=False)
    principal = AuthPrincipal(
        kind="user",
        user_id=9,
        subject="user:9",
        roles=["admin"],
        permissions=[],
        is_admin=False,
    )

    assert emb_mod._is_policy_bypass_admin(principal=principal, user=user) is True


@pytest.mark.unit
def test_policy_bypass_falls_back_to_user_admin_when_principal_absent():
    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as emb_mod

    user = User(id=10, username="u2", email="u2@example.com", is_active=True, is_admin=True)

    assert emb_mod._is_policy_bypass_admin(principal=None, user=user) is True
