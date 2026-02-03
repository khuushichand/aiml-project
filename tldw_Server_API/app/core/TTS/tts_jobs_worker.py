"""
TTS Jobs worker for long-form speech generation.

- domain = "audio"
- queue = os.getenv("TTS_JOBS_QUEUE", "default")
- job_type = "tts_longform"
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Jobs.event_stream import emit_job_event
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.Jobs.worker_utils import coerce_int as _coerce_int
from tldw_Server_API.app.core.Jobs.worker_utils import jobs_manager_from_env as _jobs_manager
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSError, is_retryable_error
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2

TTS_DOMAIN = "audio"
TTS_JOB_TYPE = "tts_longform"


class TTSJobError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, backoff_seconds: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        if backoff_seconds is not None:
            self.backoff_seconds = int(backoff_seconds)


def _resolve_user_id(job: dict[str, Any], payload: dict[str, Any]) -> str:
    candidate = payload.get("user_id") or job.get("owner_user_id")
    if candidate is None or str(candidate).strip() == "":
        raise TTSJobError("missing user_id", retryable=False)
    return str(candidate)


async def _handle_tts_job(job: dict[str, Any]) -> dict[str, Any]:
    payload = job.get("payload") or {}
    job_type = str(job.get("job_type") or payload.get("job_type") or "").strip().lower()
    if job_type and job_type != TTS_JOB_TYPE:
        raise TTSJobError(f"unsupported job_type: {job_type}", retryable=False)

    user_id = _resolve_user_id(job, payload)
    speech_payload = payload.get("speech_request")
    if not isinstance(speech_payload, dict):
        raise TTSJobError("missing speech_request payload", retryable=False)

    # Force non-streaming in jobs worker
    speech_payload["stream"] = False
    try:
        request = OpenAISpeechRequest(**speech_payload)
    except Exception as exc:
        raise TTSJobError(f"invalid speech_request: {exc}", retryable=False) from exc

    provider_hint = payload.get("provider_hint")
    provider_overrides = payload.get("provider_overrides")

    jm = JobManager()
    tts_service = await get_tts_service_v2()
    job_id = int(job.get("id") or 0)
    start_ts = asyncio.get_event_loop().time()

    def _emit_progress(percent: float, message: str, eta_seconds: float | None = None) -> None:
        if job_id <= 0:
            return
        try:
            jm.update_job_progress(job_id, progress_percent=percent, progress_message=message)
        except Exception:
            pass
        try:
            attrs = {"progress_percent": percent, "progress_message": message}
            if eta_seconds is not None:
                attrs["eta_seconds"] = max(0.0, float(eta_seconds))
            emit_job_event("job.progress", job={"id": job_id}, attrs=attrs)
        except Exception:
            pass

    _emit_progress(5.0, "tts_started")
    try:
        speech_iter = tts_service.generate_speech(
            request,
            provider=provider_hint,
            fallback=True,
            provider_overrides=provider_overrides,
            user_id=int(user_id),
        )
        audio_bytes = bytearray()
        last_update = start_ts
        expected_chars_per_sec = 15.0
        try:
            expected_chars_per_sec = float(
                (request.extra_params or {}).get("audio_expected_chars_per_sec", expected_chars_per_sec)
            )
        except Exception:
            expected_chars_per_sec = 15.0
        expected_sec = max(1.0, len(request.input or "") / max(1.0, expected_chars_per_sec))
        async for chunk in speech_iter:
            if chunk:
                audio_bytes.extend(chunk)
            now = asyncio.get_event_loop().time()
            if now - last_update >= 1.0:
                elapsed = now - start_ts
                percent = min(80.0, (elapsed / expected_sec) * 80.0)
                eta = max(0.0, expected_sec - elapsed)
                _emit_progress(percent, "tts_synthesizing", eta_seconds=eta)
                last_update = now
    except TTSError as exc:
        retryable = is_retryable_error(exc)
        raise TTSJobError(str(exc), retryable=retryable) from exc
    except Exception as exc:
        raise TTSJobError(str(exc), retryable=True) from exc

    if not audio_bytes:
        raise TTSJobError("empty_audio", retryable=False)

    _emit_progress(85.0, "tts_synthesis_complete")
    outputs_dir = DatabasePaths.get_user_outputs_dir(user_id)
    filename = f"tts_job_{job.get('id')}.{request.response_format}"

    _emit_progress(92.0, "tts_writing_output")
    with CollectionsDatabase.for_user(user_id=user_id) as cdb:
        safe_name = cdb.resolve_output_storage_path(filename)
        output_path = outputs_dir / safe_name
        try:
            output_path.write_bytes(bytes(audio_bytes))
        except Exception as exc:
            logger.error("tts jobs worker: failed to write output {}: {}", output_path, exc)
            raise TTSJobError("write_failed", retryable=True) from exc

        metadata = {
            "artifact_type": "tts_audio",
            "provider": provider_hint,
            "model": request.model,
            "voice": request.voice,
            "format": request.response_format,
        }
        row = cdb.create_output_artifact(
            type_="tts_audio",
            title=f"TTS Job {job.get('id')}",
            format_=request.response_format,
            storage_path=safe_name,
            metadata_json=json.dumps(metadata),
            job_id=int(job.get("id")),
        )

    _emit_progress(100.0, "tts_completed", eta_seconds=0.0)
    return {
        "output_id": row.id,
        "storage_path": row.storage_path,
        "format": row.format,
        "bytes": len(audio_bytes),
    }


async def run_tts_jobs_worker(stop_event: asyncio.Event | None = None) -> None:
    worker_id = (os.getenv("TTS_JOBS_WORKER_ID") or f"tts-jobs-{os.getpid()}").strip()
    queue = (os.getenv("TTS_JOBS_QUEUE") or "default").strip() or "default"
    lease_seconds = _coerce_int(os.getenv("TTS_JOBS_LEASE_SECONDS") or os.getenv("JOBS_LEASE_SECONDS"), 60)
    renew_jitter = _coerce_int(os.getenv("TTS_JOBS_RENEW_JITTER_SECONDS") or os.getenv("JOBS_LEASE_RENEW_JITTER_SECONDS"), 5)
    renew_threshold = _coerce_int(os.getenv("TTS_JOBS_RENEW_THRESHOLD_SECONDS") or os.getenv("JOBS_LEASE_RENEW_THRESHOLD_SECONDS"), 10)
    cfg = WorkerConfig(
        domain=TTS_DOMAIN,
        queue=queue,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        renew_jitter_seconds=renew_jitter,
        renew_threshold_seconds=renew_threshold,
    )
    sdk = WorkerSDK(_jobs_manager(), cfg)
    _stop_watcher_task: asyncio.Task[None] | None = None

    if stop_event is not None:
        async def _watch_stop() -> None:
            await stop_event.wait()
            sdk.stop()

        _stop_watcher_task = asyncio.create_task(_watch_stop())

    logger.info("TTS Jobs worker starting (queue={}, worker_id={})", queue, worker_id)
    try:
        await sdk.run(handler=_handle_tts_job)
    finally:
        if _stop_watcher_task is not None and not _stop_watcher_task.done():
            _stop_watcher_task.cancel()
            try:
                await _stop_watcher_task
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run_tts_jobs_worker())
