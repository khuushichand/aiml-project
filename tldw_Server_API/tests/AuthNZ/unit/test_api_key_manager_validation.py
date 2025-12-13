import pytest


pytestmark = pytest.mark.unit


class _StubRepo:
    def __init__(self, key_info: dict):
        self._key_info = dict(key_info)

    async def fetch_active_by_hash_candidates(self, hash_candidates):  # noqa: ARG002
        return dict(self._key_info)


async def _noop_async(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
    return None


@pytest.mark.asyncio
async def test_validate_api_key_parses_zulu_expires_at(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.core.AuthNZ.settings import Settings

    api_key = "tldw_test_zulu_expiry"

    manager = APIKeyManager()
    manager.settings = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY="test-secret-for-zulu-expiry-1234567890")
    manager._initialized = True

    primary_hash = manager.hash_candidates(api_key)[0]
    repo = _StubRepo(
        {
            "id": 1,
            "user_id": 1,
            "key_hash": primary_hash,
            "expires_at": "2099-01-01T00:00:00Z",
            "allowed_ips": None,
            "scope": "read",
        }
    )

    monkeypatch.setattr(manager, "_get_repo", lambda: repo, raising=True)
    manager._update_usage = _noop_async  # type: ignore[method-assign]

    result = await manager.validate_api_key(api_key)

    assert result is not None
    assert result["id"] == 1
    assert "key_hash" not in result


@pytest.mark.asyncio
async def test_validate_api_key_allows_missing_scope_for_read(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.core.AuthNZ.settings import Settings

    api_key = "tldw_test_missing_scope"

    manager = APIKeyManager()
    manager.settings = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY="test-secret-for-missing-scope-1234567890")
    manager._initialized = True

    primary_hash = manager.hash_candidates(api_key)[0]
    repo = _StubRepo(
        {
            "id": 2,
            "user_id": 1,
            "key_hash": primary_hash,
            "expires_at": None,
            "allowed_ips": None,
        }
    )

    monkeypatch.setattr(manager, "_get_repo", lambda: repo, raising=True)
    manager._update_usage = _noop_async  # type: ignore[method-assign]

    result = await manager.validate_api_key(api_key, required_scope="read")

    assert result is not None
    assert result["id"] == 2
