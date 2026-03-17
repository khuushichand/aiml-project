from __future__ import annotations

import json

import pytest

from tldw_Server_API.app.core.AuthNZ.federation.state_repo import FederationStateRepo


@pytest.mark.asyncio
async def test_federation_state_repo_consumes_state_atomically() -> None:
    class _StubSessionManager:
        def __init__(self) -> None:
            self.consumed: list[str] = []

        async def consume_ephemeral_value(self, key: str):
            self.consumed.append(key)
            return json.dumps({"provider_id": 7, "nonce": "nonce-123"})

        async def get_ephemeral_value(self, key: str):
            raise AssertionError("consume_state should not call get_ephemeral_value")

        async def delete_ephemeral_value(self, key: str) -> None:
            raise AssertionError("consume_state should not call delete_ephemeral_value")

    session_manager = _StubSessionManager()
    repo = FederationStateRepo(session_manager=session_manager)

    payload = await repo.consume_state(state="state-123")

    assert payload == {"provider_id": 7, "nonce": "nonce-123"}
    assert session_manager.consumed == ["oidc-login:state-123"]
