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
