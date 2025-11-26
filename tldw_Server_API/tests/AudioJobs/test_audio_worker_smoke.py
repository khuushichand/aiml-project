import os
import shutil
import asyncio
import tempfile
import numpy as np
import soundfile as sf
import pytest


pytestmark = pytest.mark.smoke


def _has_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg"))


def _allow_heavy() -> bool:
    return os.getenv("ALLOW_HEAVY_AUDIO_SMOKE", "").lower() in ("1", "true", "yes")


@pytest.mark.asyncio
async def test_audio_worker_pipeline_smoke_skip_if_missing():
    """
    Smoke test for audio worker pipeline. Skips unless explicitly allowed and ffmpeg is present.

    This test enqueues a local_path job and briefly runs the worker loop. It is designed
    to be opt-in (ALLOW_HEAVY_AUDIO_SMOKE=1) and will skip otherwise to keep CI fast.
    """
    if not _allow_heavy() or not _has_ffmpeg():
        pytest.skip("Audio worker smoke test skipped (set ALLOW_HEAVY_AUDIO_SMOKE=1 and install ffmpeg to enable)")

    # Create a tiny WAV file
    sr = 16000
    data = np.zeros(sr // 10, dtype=np.float32)  # 0.1s silence
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, data, sr)
            tmp_path = f.name

        # Create an audio job pointing to this local file
        from tldw_Server_API.app.core.Jobs.manager import JobManager
        jm = JobManager()
        row = jm.create_job(
            domain="audio",
            queue="default",
            job_type="audio_convert",
            payload={"local_path": tmp_path, "perform_chunking": False, "perform_analysis": False, "model": "whisper-1"},
            owner_user_id="1",
        )
        assert row.get("id")

        # Run the worker for a brief period
        from tldw_Server_API.app.services.audio_jobs_worker import run_audio_jobs_worker
        stop = asyncio.Event()

        async def _stop_soon():
            await asyncio.sleep(1.0)
            stop.set()

        task = asyncio.create_task(run_audio_jobs_worker(stop))
        stopper = asyncio.create_task(_stop_soon())
        await asyncio.gather(task, stopper)

        # If we reach here without exceptions, smoke passes
        assert True
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_audio_worker_transcribe_normalizes_segments_and_text_tuple(monkeypatch, tmp_path):
    """
    The CPU audio_jobs_worker should normalize speech_to_text results that come
    back as (segments, language) into a payload with both 'segments' and merged
    'text' for downstream stages.
    """
    # Isolate jobs DB for this test
    jobs_db_path = tmp_path / "jobs_cpu.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(jobs_db_path))

    from tldw_Server_API.app.core.Jobs.manager import JobManager

    jm = JobManager()

    # Stub quota helpers to avoid external dependencies
    import tldw_Server_API.app.services.audio_jobs_worker as worker

    async def _fake_get_limits_for_user(user_id: int):
        return {"daily_minutes": 30.0, "concurrent_streams": 1, "concurrent_jobs": 0, "max_file_size_mb": 25}

    async def _fake_can_start_job(user_id: int):
        return True, ""

    async def _fake_increment_jobs_started(user_id: int):
        return None

    async def _fake_finish_job(user_id: int):
        return None

    monkeypatch.setattr(worker, "get_limits_for_user", _fake_get_limits_for_user, raising=True)
    monkeypatch.setattr(worker, "can_start_job", _fake_can_start_job, raising=True)
    monkeypatch.setattr(worker, "increment_jobs_started", _fake_increment_jobs_started, raising=True)
    monkeypatch.setattr(worker, "finish_job", _fake_finish_job, raising=True)

    # Stub speech_to_text so no real STT runs
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib

    def _fake_speech_to_text(*args, **kwargs):
        segs = [{"Text": "hello worker", "start_seconds": 0.0, "end_seconds": 1.0}]
        return segs, "en"

    monkeypatch.setattr(atlib, "speech_to_text", _fake_speech_to_text, raising=True)

    # Create a dummy wav file and corresponding audio_transcribe job
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"\x00\x00")
    row = jm.create_job(
        domain="audio",
        queue="default",
        job_type="audio_transcribe",
        payload={
            "wav_path": str(wav_path),
            "model": "whisper-1",
            "perform_chunking": False,
            "perform_analysis": False,
        },
        owner_user_id="1",
    )
    assert row.get("id")

    stop = asyncio.Event()
    task = asyncio.create_task(worker.run_audio_jobs_worker(stop))
    try:
        # Poll for the next-stage job (audio_store) created from the transcribe stage
        created = None
        for _ in range(50):
            await asyncio.sleep(0.05)
            jobs = jm.list_jobs(domain="audio", job_type="audio_store", owner_user_id="1")
            if jobs:
                created = jobs[0]
                break

        assert created is not None, "audio_store job was not created by worker"
        payload = created.get("payload") or {}
        assert isinstance(payload.get("segments"), list)
        assert payload.get("text") == "hello worker"
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.asyncio
async def test_audio_gpu_worker_normalizes_segments_and_text(monkeypatch, tmp_path):
    """
    The GPU audio_transcribe worker should normalize both plain segments and
    (segments, language) results into 'segments' and merged 'text' payload.
    """
    jobs_db_path = tmp_path / "jobs_gpu.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(jobs_db_path))
    # Allow the GPU worker's 'transcribe' queue for the audio domain
    monkeypatch.setenv("JOBS_ALLOWED_QUEUES_AUDIO", "transcribe")

    from tldw_Server_API.app.core.Jobs.manager import JobManager

    jm = JobManager()

    import tldw_Server_API.app.services.audio_transcribe_gpu_worker as gpu_worker

    async def _fake_can_start_job(user_id: int):
        return True, ""

    async def _fake_increment_jobs_started(user_id: int):
        return None

    async def _fake_finish_job(user_id: int):
        return None

    monkeypatch.setattr(gpu_worker, "can_start_job", _fake_can_start_job, raising=True)
    monkeypatch.setattr(gpu_worker, "increment_jobs_started", _fake_increment_jobs_started, raising=True)
    monkeypatch.setattr(gpu_worker, "finish_job", _fake_finish_job, raising=True)

    # Stub speech_to_text for GPU worker
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib

    def _fake_speech_to_text_gpu(*args, **kwargs):
        segs = [{"Text": "hello gpu", "start_seconds": 0.0, "end_seconds": 1.0}]
        # Return plain segments (no language) to exercise the non-tuple path
        return segs

    monkeypatch.setattr(atlib, "speech_to_text", _fake_speech_to_text_gpu, raising=True)

    wav_path = tmp_path / "sample_gpu.wav"
    wav_path.write_bytes(b"\x00\x00")
    row = jm.create_job(
        domain="audio",
        queue="transcribe",
        job_type="audio_transcribe",
        payload={
            "wav_path": str(wav_path),
            "model": "whisper-1",
            "perform_chunking": False,
            "perform_analysis": False,
        },
        owner_user_id="1",
    )
    assert row.get("id")

    stop = asyncio.Event()
    task = asyncio.create_task(gpu_worker.run_audio_transcribe_gpu_worker(stop))
    try:
        created = None
        for _ in range(50):
            await asyncio.sleep(0.05)
            jobs = jm.list_jobs(domain="audio", queue="default", job_type="audio_store", owner_user_id="1")
            if jobs:
                created = jobs[0]
                break

        assert created is not None, "audio_store job was not created by GPU worker"
        payload = created.get("payload") or {}
        assert isinstance(payload.get("segments"), list)
        assert payload.get("text") == "hello gpu"
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=2.0)
