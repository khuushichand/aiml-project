import pytest
from cryptography.fernet import Fernet

from tldw_Server_API.app.core.AuthNZ.session_manager import (
    SessionManager,
    reset_session_manager,
)
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.config import settings as core_settings


@pytest.mark.asyncio
async def test_session_manager_accepts_configured_fernet_key(monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-session-key")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", key)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    reset_settings()

    try:
        manager = SessionManager()
        await manager.initialize()
        sample = "token-123"
        encrypted = manager.encrypt_token(sample)
        assert manager.decrypt_token(encrypted) == sample
    finally:
        await reset_session_manager()
        for env_key in (
            "AUTH_MODE",
            "SINGLE_USER_API_KEY",
            "SESSION_ENCRYPTION_KEY",
            "DATABASE_URL",
        ):
            monkeypatch.delenv(env_key, raising=False)
        reset_settings()


@pytest.mark.asyncio
async def test_session_manager_persists_generated_key(monkeypatch, tmp_path):
    # Ensure persistence path points at temporary directory
    monkeypatch.setitem(core_settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/auth.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "old-secret-value-12345678901234567890ABCDEF")
    reset_settings()

    key_path = tmp_path / "Config_Files" / "session_encryption.key"
    if key_path.exists():
        key_path.unlink()

    manager = SessionManager()
    sample = "persist-me"
    encrypted = manager.encrypt_token(sample)
    assert key_path.exists(), "session_encryption.key should be persisted"
    assert manager.decrypt_token(encrypted) == sample

    await reset_session_manager()
    reset_settings()

    manager_again = SessionManager()
    assert manager_again.decrypt_token(encrypted) == sample

    await reset_session_manager()
    for env_key in ("AUTH_MODE", "DATABASE_URL", "JWT_SECRET_KEY"):
        monkeypatch.delenv(env_key, raising=False)
    reset_settings()


@pytest.mark.asyncio
async def test_session_manager_uses_secondary_secret_on_rotation(monkeypatch, tmp_path):
    monkeypatch.setitem(core_settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    old_secret = "old-secret-rotation-abcdefghijklmnopqrstuvwxyz123"
    new_secret = "new-secret-rotation-abcdefghijklmnopqrstuvwxyz456"
    monkeypatch.setenv("JWT_SECRET_KEY", old_secret)
    reset_settings()

    # Simulate environments where we cannot persist the generated key
    monkeypatch.setattr(SessionManager, "_persist_session_key", lambda self, key: False, raising=False)

    manager = SessionManager()
    payload = "rotation-token"
    encrypted = manager.encrypt_token(payload)

    await reset_session_manager()

    monkeypatch.setenv("JWT_SECRET_KEY", new_secret)
    monkeypatch.setenv("JWT_SECONDARY_SECRET", old_secret)
    reset_settings()

    manager_after_rotation = SessionManager()
    assert manager_after_rotation.decrypt_token(encrypted) == payload

    await reset_session_manager()
    for env_key in ("AUTH_MODE", "DATABASE_URL", "JWT_SECRET_KEY", "JWT_SECONDARY_SECRET"):
        monkeypatch.delenv(env_key, raising=False)
    reset_settings()


@pytest.mark.asyncio
async def test_session_manager_rejects_symlink_persistence(monkeypatch, tmp_path):
    monkeypatch.setitem(core_settings, "PROJECT_ROOT", tmp_path)
    key_path = tmp_path / "Config_Files" / "session_encryption.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "captured.key"
    target.write_text("stealme", encoding="utf-8")
    key_path.symlink_to(target)

    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", "symlink-test-secret-key-0123456789abcdef0123456789abcdef")
    reset_settings()

    try:
        manager = SessionManager()
        assert key_path.is_symlink()
        # Session manager resolves the symlink before persisting; ensure it landed on the target file.
        assert manager._persisted_key_path == target.resolve()
        persisted_payload = target.read_text(encoding="utf-8").strip()
        assert persisted_payload and persisted_payload != "stealme"
    finally:
        await reset_session_manager()
        for env_key in ("AUTH_MODE", "DATABASE_URL", "JWT_SECRET_KEY"):
            monkeypatch.delenv(env_key, raising=False)
        key_path.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
    reset_settings()
