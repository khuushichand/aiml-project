from types import SimpleNamespace

import pytest

from tldw_Server_API.app.services import tts_history_cleanup_service as cleanup


pytestmark = pytest.mark.unit


def _clear_history_cleanup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TTS_HISTORY_PURGE_INTERVAL_HOURS", raising=False)
    monkeypatch.delenv("TTS_HISTORY_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("TTS_HISTORY_MAX_ROWS_PER_USER", raising=False)


def test_resolve_cleanup_settings_uses_settings_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_history_cleanup_env(monkeypatch)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_PURGE_INTERVAL_HOURS", 12, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_RETENTION_DAYS", 45, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_MAX_ROWS_PER_USER", 678, raising=False)

    assert cleanup._resolve_cleanup_settings() == (12, 45, 678)


def test_resolve_cleanup_settings_env_overrides_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_history_cleanup_env(monkeypatch)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_PURGE_INTERVAL_HOURS", 24, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_RETENTION_DAYS", 90, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_MAX_ROWS_PER_USER", 10000, raising=False)
    monkeypatch.setenv("TTS_HISTORY_PURGE_INTERVAL_HOURS", "6")
    monkeypatch.setenv("TTS_HISTORY_RETENTION_DAYS", "14")
    monkeypatch.setenv("TTS_HISTORY_MAX_ROWS_PER_USER", "321")

    assert cleanup._resolve_cleanup_settings() == (6, 14, 321)


@pytest.mark.asyncio
async def test_cleanup_loop_disabled_when_interval_nonpositive(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_history_cleanup_env(monkeypatch)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_PURGE_INTERVAL_HOURS", 0, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_RETENTION_DAYS", 90, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_MAX_ROWS_PER_USER", 10000, raising=False)

    sleep_called = False

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_called
        sleep_called = True

    monkeypatch.setattr(cleanup.asyncio, "sleep", _fake_sleep)

    await cleanup.run_tts_history_cleanup_loop()

    assert sleep_called is False


@pytest.mark.asyncio
async def test_cleanup_loop_disabled_when_retention_and_rows_nonpositive(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_history_cleanup_env(monkeypatch)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_PURGE_INTERVAL_HOURS", 24, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_RETENTION_DAYS", 0, raising=False)
    monkeypatch.setattr(cleanup.settings, "TTS_HISTORY_MAX_ROWS_PER_USER", 0, raising=False)

    sleep_called = False

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_called
        sleep_called = True

    monkeypatch.setattr(cleanup.asyncio, "sleep", _fake_sleep)

    await cleanup.run_tts_history_cleanup_loop()

    assert sleep_called is False


@pytest.mark.asyncio
async def test_cleanup_loop_uses_create_media_database_for_sqlite_users(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    stop_event = cleanup.asyncio.Event()
    events: list[object] = []
    user_db_paths = {
        "1": tmp_path / "probe.sqlite3",
        "11": tmp_path / "11.sqlite3",
        "22": tmp_path / "22.sqlite3",
    }
    user_removed = {"11": 3, "22": 5}

    monkeypatch.setattr(cleanup, "_resolve_cleanup_settings", lambda: (1, 30, 100))

    async def _fake_sleep(_seconds: float) -> None:
        return None

    async def _fake_wait_for(coro, timeout: float):
        events.append(("wait_for", timeout))
        stop_event.set()
        await coro
        return True

    def _fake_create_media_database(client_id: str, **kwargs):
        db_path = kwargs.get("db_path")
        events.append(("create", client_id, db_path))
        if db_path == str(user_db_paths["1"]):
            return SimpleNamespace(
                backend_type=SimpleNamespace(name="sqlite"),
                close_connection=lambda: events.append(("close", "probe")),
            )

        user_id = next(uid for uid, path in user_db_paths.items() if str(path) == db_path)
        return SimpleNamespace(
            purge_tts_history_for_user=lambda **purge_kwargs: events.append(
                ("purge", user_id, purge_kwargs)
            ) or user_removed[user_id]
            ,
            close_connection=lambda: events.append(("close", user_id)),
        )

    monkeypatch.setattr(cleanup.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(cleanup.asyncio, "wait_for", _fake_wait_for)
    monkeypatch.setattr(cleanup, "create_media_database", _fake_create_media_database)
    monkeypatch.setattr(cleanup.DatabasePaths, "get_single_user_id", lambda: "1")
    monkeypatch.setattr(cleanup.DatabasePaths, "get_media_db_path", lambda uid: user_db_paths[str(uid)])
    monkeypatch.setattr(cleanup, "_enumerate_user_ids_from_fs", lambda: ["11", "22"])

    await cleanup.run_tts_history_cleanup_loop(stop_event=stop_event)

    assert events == [
        ("create", "tts_history_cleanup", str(user_db_paths["1"])),
        ("close", "probe"),
        ("create", "tts_history_cleanup", str(user_db_paths["11"])),
        (
            "purge",
            "11",
            {"user_id": "11", "retention_days": 30, "max_rows": 100},
        ),
        ("close", "11"),
        ("create", "tts_history_cleanup", str(user_db_paths["22"])),
        (
            "purge",
            "22",
            {"user_id": "22", "retention_days": 30, "max_rows": 100},
        ),
        ("close", "22"),
        ("wait_for", 3600),
    ]


@pytest.mark.asyncio
async def test_cleanup_loop_uses_create_media_database_for_postgres(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    stop_event = cleanup.asyncio.Event()
    events: list[object] = []
    probe_path = tmp_path / "probe.sqlite3"
    probe_db = SimpleNamespace(
        backend_type=SimpleNamespace(name="postgresql"),
        list_tts_history_user_ids=lambda: ["7", "8"],
        close_connection=lambda: events.append(("close", "probe")),
    )

    monkeypatch.setattr(cleanup, "_resolve_cleanup_settings", lambda: (1, 14, 55))

    async def _fake_sleep(_seconds: float) -> None:
        return None

    async def _fake_wait_for(coro, timeout: float):
        events.append(("wait_for", timeout))
        stop_event.set()
        await coro
        return True

    def _fake_create_media_database(client_id: str, **kwargs):
        events.append(("create", client_id, kwargs.get("db_path")))
        return probe_db

    def _fake_purge_with_db(db, user_ids, retention_days: int, max_rows: int) -> int:
        events.append(("purge_with_db", db, list(user_ids), retention_days, max_rows))
        return 9

    monkeypatch.setattr(cleanup.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(cleanup.asyncio, "wait_for", _fake_wait_for)
    monkeypatch.setattr(cleanup, "create_media_database", _fake_create_media_database)
    monkeypatch.setattr(cleanup, "_purge_with_db", _fake_purge_with_db)
    monkeypatch.setattr(cleanup.DatabasePaths, "get_single_user_id", lambda: "1")
    monkeypatch.setattr(cleanup.DatabasePaths, "get_media_db_path", lambda uid: probe_path)

    await cleanup.run_tts_history_cleanup_loop(stop_event=stop_event)

    assert events == [
        ("create", "tts_history_cleanup", str(probe_path)),
        ("purge_with_db", probe_db, ["7", "8"], 14, 55),
        ("close", "probe"),
        ("wait_for", 3600),
    ]
