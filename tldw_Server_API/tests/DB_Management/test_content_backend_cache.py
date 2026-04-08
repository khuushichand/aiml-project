import configparser
import threading

import pytest

from tldw_Server_API.app.core.DB_Management import content_backend
from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
    defaults as media_runtime_defaults,
)


class _FakePool:
    def __init__(self) -> None:
        self.closed = 0

    def close_all(self) -> None:
        self.closed += 1


class _FakeBackend:
    def __init__(self) -> None:
        self.pool = _FakePool()

    def get_pool(self):
        return self.pool


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


def _make_sqlite_config(sqlite_path: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.add_section("Database")
    cfg.set("Database", "type", "sqlite")
    cfg.set("Database", "sqlite_path", sqlite_path)
    return cfg


def test_get_content_backend_closes_superseded_cached_backend(monkeypatch) -> None:
    old_backend = _FakeBackend()
    new_backend = _FakeBackend()

    monkeypatch.setattr(content_backend, "_cached_backend", old_backend)
    monkeypatch.setattr(content_backend, "_cached_backend_signature", ("old",))
    monkeypatch.setattr(
        content_backend.DatabaseBackendFactory,
        "create_backend",
        staticmethod(lambda _cfg: new_backend),
    )

    cfg = _make_config("pw-new", "prefer")
    backend = content_backend.get_content_backend(cfg)

    if backend is not new_backend:
        pytest.fail("expected replacement backend to be returned")
    if old_backend.pool.closed != 1:
        pytest.fail("expected superseded cached backend pool to close exactly once")


def test_reset_media_runtime_defaults_closes_cached_backend(monkeypatch) -> None:
    cached_backend = _FakeBackend()

    monkeypatch.setattr(content_backend, "_cached_backend", cached_backend)
    monkeypatch.setattr(content_backend, "_cached_backend_signature", ("cached",))

    media_runtime_defaults._clear_content_backend_cache()

    if cached_backend.pool.closed != 1:
        pytest.fail("expected clearing cached backend to close the pool exactly once")


def test_reset_media_runtime_defaults_blocks_stale_backend_reads_during_clear(
    monkeypatch,
    tmp_path,
) -> None:
    stale_backend = _FakeBackend()
    sqlite_cfg = _make_sqlite_config(str(tmp_path / "media.db"))
    clear_started = threading.Event()
    allow_clear = threading.Event()
    load_finished = threading.Event()
    load_result = {}

    monkeypatch.setattr(media_runtime_defaults, "postgres_content_mode", True)
    monkeypatch.setattr(media_runtime_defaults, "content_db_backend", stale_backend)
    monkeypatch.setattr(media_runtime_defaults, "single_user_config", _make_config("pw1", "prefer"))

    def fake_clear_cached_backend() -> None:
        clear_started.set()
        allow_clear.wait(timeout=2)

    monkeypatch.setattr(content_backend, "clear_cached_backend", fake_clear_cached_backend)

    def run_reset() -> None:
        media_runtime_defaults.reset_media_runtime_defaults(config=sqlite_cfg, reload=False)

    def run_load() -> None:
        load_result["backend"] = media_runtime_defaults.ensure_content_backend_loaded()
        load_finished.set()

    reset_thread = threading.Thread(target=run_reset)
    reset_thread.start()

    if not clear_started.wait(timeout=2):
        pytest.fail("expected reset to begin clearing the cached backend")

    load_thread = threading.Thread(target=run_load)
    load_thread.start()

    if load_finished.wait(timeout=0.2):
        pytest.fail("expected runtime backend reads to block until reset finished")

    allow_clear.set()
    reset_thread.join(timeout=2)
    load_thread.join(timeout=2)

    if reset_thread.is_alive() or load_thread.is_alive():
        pytest.fail("expected reset/load threads to complete after cache clear was released")
    if load_result.get("backend") is not None:
        pytest.fail("expected reset to prevent returning the stale backend after cache clear")


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

    cfg = _make_config("pw1", "prefer")
    backend_a = content_backend.get_content_backend(cfg)
    backend_b = content_backend.get_content_backend(cfg)
    if backend_a is not backend_b:
        pytest.fail("expected identical config to reuse cached backend")
    if len(created) != 1:
        pytest.fail("expected only one backend instance for identical config")

    cfg.set("Database", "pg_password", "pw2")
    backend_c = content_backend.get_content_backend(cfg)
    if backend_c is backend_a:
        pytest.fail("expected password change to invalidate cached backend signature")

    cfg.set("Database", "pg_sslmode", "require")
    backend_d = content_backend.get_content_backend(cfg)
    if backend_d is backend_c:
        pytest.fail("expected sslmode change to invalidate cached backend signature")
