import os
import stat

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
    # Prefer API component storage for session key to avoid using PROJECT_ROOT
    monkeypatch.setenv("SESSION_KEY_STORAGE", "api")
    # Still set PROJECT_ROOT to a tmp dir for isolation of other paths
    monkeypatch.setitem(core_settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/auth.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "old-secret-value-12345678901234567890ABCDEF")
    reset_settings()

    manager = SessionManager()
    sample = "persist-me"
    encrypted = manager.encrypt_token(sample)
    # Expect the API path to exist when SESSION_KEY_STORAGE=api
    api_key_path = manager._resolve_api_key_path()
    assert api_key_path is not None and api_key_path.exists(), "API session_encryption.key should exist"
    assert manager.decrypt_token(encrypted) == sample

    await reset_session_manager()
    reset_settings()

    manager_again = SessionManager()
    assert manager_again.decrypt_token(encrypted) == sample

    await reset_session_manager()
    for env_key in ("AUTH_MODE", "DATABASE_URL", "JWT_SECRET_KEY", "SESSION_KEY_STORAGE"):
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


@pytest.mark.asyncio
async def test_session_manager_rejects_insecure_key_permissions(monkeypatch, tmp_path):
    if os.name == "nt":
        pytest.skip("File permission enforcement is not reliable on Windows")
    if not hasattr(os, "getuid"):
        pytest.skip("OS does not expose uid/gid for permission enforcement")

    monkeypatch.setitem(core_settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/auth.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "perm-test-secret-key-0123456789abcdef0123456789abcdef")
    reset_settings()

    key_path = tmp_path / "Config_Files" / "session_encryption.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    insecure_key = Fernet.generate_key().decode("utf-8")
    key_path.write_text(insecure_key, encoding="utf-8")
    os.chmod(key_path, 0o644)

    try:
        manager = SessionManager()
        assert manager.cipher_suite is not None
        repaired_key = key_path.read_text(encoding="utf-8").strip()
        assert repaired_key and repaired_key != insecure_key
        mode = stat.S_IMODE(os.stat(key_path, follow_symlinks=False).st_mode)
        assert mode & (stat.S_IRWXG | stat.S_IRWXO) == 0
    finally:
        await reset_session_manager()
        for env_key in ("AUTH_MODE", "DATABASE_URL", "JWT_SECRET_KEY"):
            monkeypatch.delenv(env_key, raising=False)
        reset_settings()
