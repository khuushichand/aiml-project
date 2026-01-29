import configparser

from tldw_Server_API.app.core.DB_Management import content_backend


def _make_config(password: str, sslmode: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.add_section("Database")
    cfg.set("Database", "type", "postgresql")
    cfg.set("Database", "pg_host", "localhost")
    cfg.set("Database", "pg_port", "5432")
    cfg.set("Database", "pg_database", "tldw_content")
    cfg.set("Database", "pg_user", "tldw_user")
    cfg.set("Database", "pg_password", password)
    cfg.set("Database", "pg_sslmode", sslmode)
    return cfg


def test_content_backend_cache_includes_password_and_sslmode(monkeypatch) -> None:
    created = []

    def fake_create(cfg):
        obj = object()
        created.append(obj)
        return obj

    monkeypatch.delenv("TLDW_CONTENT_DB_BACKEND", raising=False)
    monkeypatch.delenv("TLDW_CONTENT_PG_PASSWORD", raising=False)
    monkeypatch.delenv("TLDW_PG_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_TEST_PASSWORD", raising=False)
    monkeypatch.delenv("TLDW_CONTENT_PG_SSLMODE", raising=False)
    monkeypatch.delenv("TLDW_PG_SSLMODE", raising=False)

    monkeypatch.setattr(content_backend, "_cached_backend", None)
    monkeypatch.setattr(content_backend, "_cached_backend_signature", None)
    monkeypatch.setattr(
        content_backend.DatabaseBackendFactory,
        "create_backend",
        staticmethod(fake_create),
    )

    cfg = _make_config(password="pw1", sslmode="prefer")
    backend_a = content_backend.get_content_backend(cfg)
    backend_b = content_backend.get_content_backend(cfg)
    assert backend_a is backend_b
    assert len(created) == 1

    cfg.set("Database", "pg_password", "pw2")
    backend_c = content_backend.get_content_backend(cfg)
    assert backend_c is not backend_a

    cfg.set("Database", "pg_sslmode", "require")
    backend_d = content_backend.get_content_backend(cfg)
    assert backend_d is not backend_c
