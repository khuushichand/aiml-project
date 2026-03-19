import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


pytestmark = pytest.mark.unit


_ENTERPRISE_ENV_KEYS = (
    "PROFILE",
    "AUTH_MODE",
    "DATABASE_URL",
    "JWT_SECRET_KEY",
    "SINGLE_USER_API_KEY",
    "AUTH_FEDERATION_ENABLED",
    "MCP_CREDENTIAL_BROKER_ENABLED",
    "SECRET_BACKENDS_ENABLED",
)


@pytest.fixture(autouse=True)
def _reset_settings_cache(monkeypatch: pytest.MonkeyPatch):
    reset_settings()
    for key in _ENTERPRISE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
    reset_settings()


def _configure_multi_user_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://tldw_user:TestPassword123!@localhost:5432/tldw_users",
    )
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)


def _configure_single_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "single-user-key-1234567890")


def test_enterprise_federation_requires_multi_user_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_single_user(monkeypatch)
    monkeypatch.setenv("AUTH_FEDERATION_ENABLED", "true")

    settings = get_settings()

    assert settings.AUTH_FEDERATION_ENABLED is True
    assert settings.enterprise_federation_supported is False


def test_enterprise_federation_requires_postgres_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("AUTH_FEDERATION_ENABLED", "true")

    settings = get_settings()

    assert settings.AUTH_FEDERATION_ENABLED is True
    assert settings.enterprise_federation_supported is False


def test_enterprise_flags_supported_in_multi_user_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_multi_user_postgres(monkeypatch)
    monkeypatch.setenv("AUTH_FEDERATION_ENABLED", "true")
    monkeypatch.setenv("SECRET_BACKENDS_ENABLED", "true")
    monkeypatch.setenv("MCP_CREDENTIAL_BROKER_ENABLED", "true")

    settings = get_settings()

    assert settings.enterprise_federation_supported is True
    assert settings.enterprise_secret_backends_supported is True
    assert settings.enterprise_mcp_credential_broker_supported is True


def test_mcp_credential_broker_requires_secret_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_multi_user_postgres(monkeypatch)
    monkeypatch.setenv("MCP_CREDENTIAL_BROKER_ENABLED", "true")
    monkeypatch.setenv("SECRET_BACKENDS_ENABLED", "false")

    settings = get_settings()

    assert settings.MCP_CREDENTIAL_BROKER_ENABLED is True
    assert settings.enterprise_mcp_credential_broker_supported is False
