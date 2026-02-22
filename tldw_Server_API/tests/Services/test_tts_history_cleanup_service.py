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
