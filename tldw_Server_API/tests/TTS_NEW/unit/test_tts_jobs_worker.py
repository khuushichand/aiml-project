import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.TTS import tts_jobs_worker
from tldw_Server_API.app.core.TTS.tts_jobs_worker import _handle_tts_job
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.config import settings


@pytest.mark.unit
def test_open_media_db_for_history_uses_media_db_api_factory(tmp_path, monkeypatch):
    captured = {}
    sentinel = object()
    db_path = tmp_path / "tts-history.sqlite3"

    monkeypatch.setattr(
        tts_jobs_worker.DatabasePaths,
        "get_media_db_path",
        lambda user_id: db_path,
    )

    def _fake_create_media_database(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(tts_jobs_worker, "create_media_database", _fake_create_media_database)

    result = tts_jobs_worker._open_media_db_for_history("17")

    assert result is sentinel
    assert captured == {
        "client_id": "tts_jobs_worker",
        "db_path": str(db_path),
    }


@pytest.mark.unit
async def test_tts_jobs_worker_writes_output(tmp_path, monkeypatch):
    progress_calls = []

    class DummyJM:
        def update_job_progress(self, job_id, *, progress_percent=None, progress_message=None):
            progress_calls.append((job_id, progress_percent, progress_message))
            return True

    class DummyService:
        def generate_speech(self, *args, **kwargs):
            async def _gen():
                yield b"\x00\x01"
                yield b"\x02\x03"
            return _gen()

    async def _get_service():
        return DummyService()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.get_tts_service_v2",
        _get_service,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.JobManager",
        lambda: DummyJM(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.emit_job_event",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.DatabasePaths.get_user_outputs_dir",
        lambda user_id: tmp_path,
    )

    class DummyCDB:
        def resolve_output_storage_path(self, name):
            return name

        def create_output_artifact(self, **kwargs):
            return SimpleNamespace(
                id=123,
                storage_path=kwargs.get("storage_path"),
                format=kwargs.get("format_"),
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.CollectionsDatabase.for_user",
        lambda user_id: DummyCDB(),
    )

    job = {
        "id": 55,
        "job_type": "tts_longform",
        "owner_user_id": "1",
        "payload": {
            "user_id": "1",
            "speech_request": {
                "model": "kokoro",
                "input": "hello",
                "voice": "af_heart",
                "response_format": "mp3",
                "stream": False,
            },
        },
    }

    result = await _handle_tts_job(job)
    assert result["output_id"] == 123
    assert (tmp_path / "tts_job_55.mp3").exists()
    assert progress_calls


@pytest.mark.unit
async def test_tts_jobs_worker_writes_history_with_artifact_ids(tmp_path, monkeypatch):
    class DummyService:
        def generate_speech(self, *args, **kwargs):
            async def _gen():
                yield b"\x10\x11"
            return _gen()

    async def _get_service():
        return DummyService()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.get_tts_service_v2",
        _get_service,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.JobManager",
        lambda: SimpleNamespace(update_job_progress=lambda *args, **kwargs: True),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.emit_job_event",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.DatabasePaths.get_user_outputs_dir",
        lambda user_id: tmp_path,
    )

    db_path = tmp_path / "Media_DB_v2.db"
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.DatabasePaths.get_media_db_path",
        lambda user_id: db_path,
    )

    class DummyCDB:
        def resolve_output_storage_path(self, name):
            return name

        def create_output_artifact(self, **kwargs):
            return SimpleNamespace(
                id=987,
                storage_path=kwargs.get("storage_path"),
                format=kwargs.get("format_"),
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.CollectionsDatabase.for_user",
        lambda user_id: DummyCDB(),
    )
    monkeypatch.setattr(settings, "TTS_HISTORY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "TTS_HISTORY_STORE_TEXT", True, raising=False)
    monkeypatch.setattr(settings, "TTS_HISTORY_STORE_FAILED", True, raising=False)
    monkeypatch.setattr(settings, "TTS_HISTORY_HASH_KEY", "unit-stage2-history-key", raising=False)

    job = {
        "id": 56,
        "job_type": "tts_longform",
        "request_id": "job-req-stage2",
        "owner_user_id": "1",
        "payload": {
            "user_id": "1",
            "speech_request": {
                "model": "kokoro",
                "input": "artifact id history test",
                "voice": "af_heart",
                "response_format": "mp3",
                "stream": False,
            },
        },
    }

    result = await _handle_tts_job(job)
    assert result["output_id"] == 987

    media_db = MediaDatabase(db_path=str(db_path), client_id="tts_jobs_worker_history_assert")
    try:
        row = media_db.execute_query(
            "SELECT job_id, output_id, artifact_ids FROM tts_history WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            ("1",),
        ).fetchone()
    finally:
        media_db.close_connection()

    assert row is not None
    assert int(row["job_id"]) == 56
    assert int(row["output_id"]) == 987
    artifact_ids = json.loads(row["artifact_ids"])
    assert artifact_ids == ["output:987"]


@pytest.mark.unit
async def test_tts_jobs_worker_history_write_failure_logs_job_and_request_id(tmp_path, monkeypatch):
    class DummyService:
        def generate_speech(self, *args, **kwargs):
            async def _gen():
                yield b"\xAA\xBB"
            return _gen()

    async def _get_service():
        return DummyService()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.get_tts_service_v2",
        _get_service,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.JobManager",
        lambda: SimpleNamespace(update_job_progress=lambda *args, **kwargs: True),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.emit_job_event",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.DatabasePaths.get_user_outputs_dir",
        lambda user_id: tmp_path,
    )

    class DummyCDB:
        def resolve_output_storage_path(self, name):
            return name

        def create_output_artifact(self, **kwargs):
            return SimpleNamespace(
                id=654,
                storage_path=kwargs.get("storage_path"),
                format=kwargs.get("format_"),
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.CollectionsDatabase.for_user",
        lambda user_id: DummyCDB(),
    )

    class FailingHistoryDB:
        def create_tts_history_entry(self, **kwargs):
            raise RuntimeError("history insert failed")

        def close_connection(self):
            return None

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker._open_media_db_for_history",
        lambda user_id: FailingHistoryDB(),
    )
    monkeypatch.setattr(settings, "TTS_HISTORY_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "TTS_HISTORY_STORE_TEXT", True, raising=False)
    monkeypatch.setattr(settings, "TTS_HISTORY_STORE_FAILED", True, raising=False)
    monkeypatch.setattr(settings, "TTS_HISTORY_HASH_KEY", "unit-stage2-log-key", raising=False)

    debug_lines: list[str] = []

    def _capture_debug(message, *args, **kwargs):
        try:
            rendered = str(message).format(*args)
        except Exception:
            rendered = f"{message} {args}"
        debug_lines.append(rendered)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_jobs_worker.logger.debug",
        _capture_debug,
    )

    job = {
        "id": 57,
        "job_type": "tts_longform",
        "request_id": "job-req-57",
        "owner_user_id": "1",
        "payload": {
            "user_id": "1",
            "speech_request": {
                "model": "kokoro",
                "input": "log correlation test",
                "voice": "af_heart",
                "response_format": "mp3",
                "stream": False,
            },
        },
    }

    result = await _handle_tts_job(job)
    assert result["output_id"] == 654
    assert any(
        "failed to write history record" in line and "job_id=57" in line and "request_id=job-req-57" in line
        for line in debug_lines
    )
