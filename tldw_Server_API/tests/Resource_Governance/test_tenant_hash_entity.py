import hmac
import os
from hashlib import sha256

import pytest

from tldw_Server_API.app.core.Resource_Governance import tenant


def _expected_hash(key: str, value: str) -> str:
    return hmac.new(key.encode(), value.encode(), sha256).hexdigest()


def test_hash_entity_prefers_dedicated_log_hash_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TLDW_LOG_HASH_SECRET", "log-secret")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "single-user-secret")
    monkeypatch.setattr(tenant, "_LOG_HASH_SECRET_WARNED", False)

    assert tenant.hash_entity("entity-1") == _expected_hash("log-secret", "entity-1")


def test_hash_entity_uses_stable_auth_secret_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TLDW_LOG_HASH_SECRET", raising=False)
    monkeypatch.delenv("API_KEY_PEPPER", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("SINGLE_USER_API_KEY", "single-user-secret")
    monkeypatch.setattr(tenant, "_LOG_HASH_SECRET_WARNED", False)

    assert tenant.hash_entity("entity-2") == _expected_hash("single-user-secret", "entity-2")


def test_hash_entity_enforced_mode_requires_dedicated_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TLDW_ENFORCE_LOG_HASH_SECRET", "1")
    monkeypatch.delenv("TLDW_LOG_HASH_SECRET", raising=False)
    monkeypatch.setenv("SINGLE_USER_API_KEY", "single-user-secret")
    monkeypatch.setattr(tenant, "_LOG_HASH_SECRET_WARNED", False)

    with pytest.raises(RuntimeError, match="TLDW_LOG_HASH_SECRET is required"):
        tenant.hash_entity("entity-3")


def test_hash_entity_process_local_fallback_when_no_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TLDW_LOG_HASH_SECRET", raising=False)
    monkeypatch.delenv("TLDW_ENFORCE_LOG_HASH_SECRET", raising=False)
    monkeypatch.delenv("API_KEY_PEPPER", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(tenant, "_LOG_HASH_SECRET_WARNED", False)

    expected = _expected_hash(repr(os.getpid()), "entity-4")
    assert tenant.hash_entity("entity-4") == expected
