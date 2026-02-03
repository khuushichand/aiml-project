import asyncio
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.TTS.tts_jobs_worker import _handle_tts_job


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
