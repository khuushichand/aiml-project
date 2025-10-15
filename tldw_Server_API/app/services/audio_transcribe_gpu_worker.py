from __future__ import annotations

import asyncio
import os
from typing import Optional, Dict, Any

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Usage.audio_quota import can_start_job, finish_job, increment_jobs_started, get_limits_for_user


DOMAIN = "audio"


async def run_audio_transcribe_gpu_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """GPU-focused worker that only processes the `audio_transcribe` stage.

    This is a stub container-friendly worker meant to be deployed on GPU nodes.
    It acquires jobs from the `audio` domain and processes only `audio_transcribe` jobs,
    handing off other stages back to the queue with a small retryable backoff.

    Env:
      - JOBS_POLL_INTERVAL_SECONDS (float): poll interval
      - JOBS_LEASE_SECONDS (int): lease duration per job
    """
    jm = JobManager()
    worker_id = "audio-gpu-worker"
    poll_sleep = float(os.getenv("JOBS_POLL_INTERVAL_SECONDS", "1.0") or "1.0")
    lease_seconds = int(os.getenv("JOBS_LEASE_SECONDS", "180") or "180")

    logger.info("Starting Audio GPU worker (transcription-only stub)")
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping Audio GPU worker on shutdown signal")
            return
        job = None
        owner = None
        acquired_slot = False
        try:
            job = jm.acquire_next_job(domain=DOMAIN, queue="transcribe", lease_seconds=lease_seconds, worker_id=worker_id)
            if not job:
                await asyncio.sleep(poll_sleep)
                continue
            owner = job.get("owner_user_id") or "0"

            # Only process audio_transcribe jobs here
            jtype = str(job.get("job_type") or "").lower()
            if jtype != "audio_transcribe":
                jm.fail_job(int(job["id"]), error="not_transcribe_stage", retryable=True, backoff_seconds=2, worker_id=worker_id, lease_id=str(job.get("lease_id")))
                continue

            # Per-user concurrency guard for fairness
            ok_job, msg = await can_start_job(int(owner))
            if not ok_job:
                jm.fail_job(int(job["id"]), error=msg or "concurrency limit", retryable=True, backoff_seconds=10, worker_id=worker_id, lease_id=str(job.get("lease_id")))
                continue
            acquired_slot = True
            try:
                await increment_jobs_started(int(owner))
            except Exception:
                pass

            payload: Dict[str, Any] = job.get("payload") or {}
            wav_path = payload.get("wav_path")
            model_in = (payload.get("model") or "distil-whisper-large-v3").strip()
            model = "distil-whisper-large-v3" if model_in.lower().startswith("whisper") else model_in
            if not wav_path:
                raise ValueError("missing wav_path in payload")

            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import speech_to_text

            # Run STT (GPU-accelerated if available in environment/driver)
            result = await asyncio.to_thread(
                speech_to_text,
                audio_file_path=wav_path,
                whisper_model=model,
                selected_source_lang=None,
                vad_filter=False,
                diarize=False,
            )
            # Normalize payload for downstream stages
            segments_list = None
            if isinstance(result, tuple) and result:
                segments_list = result[0]
            else:
                segments_list = result
            if not isinstance(segments_list, list):
                raise ValueError("unexpected transcription result format; expected list of segments")
            text_merged = " ".join((seg.get("Text", "").strip() if isinstance(seg, dict) else "") for seg in segments_list).strip()
            updated_payload = dict(payload)
            updated_payload["segments"] = segments_list
            updated_payload["text"] = text_merged

            # Complete and enqueue next stage
            jm.complete_job(int(job["id"]), worker_id=worker_id, lease_id=str(job.get("lease_id")))
            next_type = payload.get("perform_chunking") and "audio_chunk" or "audio_store"
            jm.create_job(
                domain=DOMAIN,
                queue="default",
                job_type=next_type,
                payload=updated_payload,
                owner_user_id=str(owner),
                priority=5,
            )

        except Exception as e:
            try:
                if job:
                    jm.fail_job(int(job["id"]), error=str(e), retryable=True, backoff_seconds=15, worker_id=worker_id, lease_id=str(job.get("lease_id")))
            except Exception:
                pass
            logger.error(f"Audio GPU worker error: {e}")
        finally:
            try:
                if acquired_slot and owner is not None:
                    await finish_job(int(owner))
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(run_audio_transcribe_gpu_worker())
    except KeyboardInterrupt:
        pass
