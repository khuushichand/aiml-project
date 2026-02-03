# audio_transcriptions.py
# Description: Audio transcription, translation, and segmentation endpoints.
import asyncio
import json
import os
import tempfile
from pathlib import Path as PathLib
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from loguru import logger
from starlette import status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, require_token_scope
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.schemas.audio_schemas import (
    TranscriptSegmentationRequest,
    TranscriptSegmentationResponse,
)
from tldw_Server_API.app.core.Audio.error_payloads import _http_error_detail
from tldw_Server_API.app.core.Audio.quota_helpers import EXPECTED_DB_EXC
from tldw_Server_API.app.core.Audio.transcription_service import _map_openai_audio_model_to_whisper
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id
from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter

router = APIRouter(
    tags=["Audio"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limit exceeded"},
    },
)


def _audio_shim_attr(name: str):
    from tldw_Server_API.app.api.v1.endpoints import audio as audio_shim
    try:
        if name in getattr(audio_shim, "__dict__", {}):
            return getattr(audio_shim, name)
    except Exception:
        pass
    try:
        from tldw_Server_API.app.api.v1.endpoints.audio import audio as audio_mod

        if hasattr(audio_mod, name):
            return getattr(audio_mod, name)
    except Exception:
        pass
    if not hasattr(audio_shim, name):
        raise NameError(name)
    return getattr(audio_shim, name)


async def _check_daily_minutes_allow(user_id: int, minutes: float):
    return await _audio_shim_attr("check_daily_minutes_allow")(user_id, minutes)


async def _add_daily_minutes(user_id: int, minutes: float):
    return await _audio_shim_attr("add_daily_minutes")(user_id, minutes)


@router.post(
    "/transcriptions",
    summary="Transcribes audio into text (OpenAI Compatible)",
    dependencies=[
        Depends(check_rate_limit),
        Depends(
            require_token_scope("any", require_if_present=True, endpoint_id="audio.transcriptions", count_as="call")
        ),
    ],
)
async def create_transcription(
    request: Request,
    file: UploadFile = File(..., description="The audio file to transcribe"),
    model: Optional[str] = Form(
        default=None,
        description="Model to use for transcription (defaults to config when omitted)",
    ),
    language: Optional[str] = Form(default=None, description="Language of the audio in ISO-639-1 format"),
    prompt: Optional[str] = Form(default=None, description="Optional text to guide the model's style"),
    hotwords: Optional[str] = Form(
        default=None,
        description="Optional hotwords to guide transcription (CSV or JSON list). Primarily used by VibeVoice-ASR.",
    ),
    response_format: str = Form(default="json", description="Format of the transcript output"),
    temperature: float = Form(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Sampling temperature (currently ignored by all providers).",
    ),
    task: str = Form(
        default="transcribe",
        description="Task for Whisper models: 'transcribe' (default) or 'translate'. "
        "For non-Whisper providers this is ignored.",
    ),
    timestamp_granularities: Optional[str] = Form(
        default="segment", description="Timestamp granularities: 'segment', 'word' (comma-separated or JSON array)"
    ),
    # Auto-segmentation options
    segment: bool = Form(
        default=False, description="If true and JSON response, also run transcript segmentation (TreeSeg)"
    ),
    seg_K: int = Form(default=6, description="Max segments for TreeSeg (if segment=true)"),
    seg_min_segment_size: int = Form(default=5, description="Min items per segment for TreeSeg"),
    seg_lambda_balance: float = Form(default=0.01, description="Balance penalty for TreeSeg"),
    seg_utterance_expansion_width: int = Form(default=2, description="Context width for TreeSeg blocks"),
    seg_embeddings_provider: Optional[str] = Form(default=None, description="Embeddings provider override for TreeSeg"),
    seg_embeddings_model: Optional[str] = Form(default=None, description="Embeddings model override for TreeSeg"),
    current_user: User = Depends(get_request_user),
):
    """
    Transcribes audio into the input language.
    """
    rid = ensure_request_id(request)

    # Validate file presence
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No audio file provided")
    # Content-Type whitelist
    allowed_types = {
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/flac",
        "audio/ogg",
        "audio/opus",
        "audio/webm",
    }
    ctype = (file.content_type or "").lower()
    if ctype and ctype not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported media type: {file.content_type}"
        )

    job_heartbeat_task: Optional[asyncio.Task] = None

    async def _maybe_start_job_heartbeat(user_id: int) -> Optional[asyncio.Task]:
        """Best-effort RG job heartbeat loop (no-op when unsupported)."""
        try:
            interval = _audio_shim_attr("get_job_heartbeat_interval_seconds")()
        except Exception as exc:
            logger.debug(
                "audio.transcriptions: get_job_heartbeat_interval_seconds failed; "
                f"skipping job heartbeat. user_id={user_id}, error={exc}"
            )
            return None
        if not interval or interval <= 0:
            return None

        async def _hb_loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    await _audio_shim_attr("heartbeat_jobs")(user_id)
                except asyncio.CancelledError:
                    raise
                except Exception as hb_exc:
                    logger.debug(f"audio.transcriptions heartbeat_jobs failed: {hb_exc}")

        try:
            return asyncio.create_task(_hb_loop())
        except Exception as exc:
            logger.debug(
                "audio.transcriptions: failed to start job heartbeat task; "
                f"user_id={user_id}, error={exc}"
            )
            return None

    # Resolve per-tier file size limit
    try:
        limits = await _audio_shim_attr("get_limits_for_user")(current_user.id)
    except EXPECTED_DB_EXC as e:
        logger.exception(
            "Failed to get limits for user %s during upload, using defaults: %s; request_id=%s",
            current_user.id,
            e,
            rid,
        )
        limits = {
            "daily_minutes": 30.0,
            "concurrent_streams": 1,
            "concurrent_jobs": 1,
            "max_file_size_mb": 25,
        }
    try:
        max_file_size = int((limits.get("max_file_size_mb") or 25) * 1024 * 1024)
    except (ValueError, TypeError) as e:
        logger.warning(
            "Could not parse max_file_size_mb for user %s; defaulting to 25MB: %s; request_id=%s",
            current_user.id,
            e,
            rid,
        )
        max_file_size = 25 * 1024 * 1024
    upload_chunk_size = 1024 * 1024

    # Resolve default model from config when omitted.
    if not (model or "").strip():
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
            resolve_default_transcription_model,
        )

        model = resolve_default_transcription_model("whisper-1")

    # Before any heavy work, enforce concurrent jobs cap per user
    ok_job, msg_job = await _audio_shim_attr("can_start_job")(current_user.id)
    if not ok_job:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg_job)
    try:
        job_heartbeat_task = await _maybe_start_job_heartbeat(current_user.id)
    except Exception:
        job_heartbeat_task = None

    # Record job start (best-effort)
    acquired_job_slot = False
    try:
        await _audio_shim_attr("increment_jobs_started")(current_user.id)
        acquired_job_slot = True
    except EXPECTED_DB_EXC as e:
        logger.exception(
            "Failed to increment jobs started: user_id=%s, error=%s; request_id=%s",
            current_user.id,
            e,
            rid,
        )

    # Save uploaded file to temporary location and proceed with processing
    temp_audio_path = None
    canonical_path = None
    try:
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".wav"
        total_read = 0
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
            while True:
                chunk = await file.read(upload_chunk_size)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > max_file_size:
                    temp_audio_path = tmp_file.name
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File size exceeds maximum of {int(max_file_size/1024/1024)}MB",
                    )
                tmp_file.write(chunk)
            temp_audio_path = tmp_file.name

        # Convert to canonical 16k mono WAV for consistent processing; base_dir constrains output location.
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
                ConversionError,
            )
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
                convert_to_wav as _convert_to_wav,
            )
        except ImportError as e:
            logger.debug(
                "convert_to_wav import failed; using original temp file: path=%s, error=%s",
                temp_audio_path,
                e,
            )
            canonical_path = temp_audio_path
        else:
            try:
                canonical_path = _convert_to_wav(
                    temp_audio_path,
                    offset=0,
                    overwrite=False,
                    base_dir=PathLib(temp_audio_path).parent,
                )
            except (ConversionError, OSError, RuntimeError, ValueError) as e:
                logger.debug(
                    "convert_to_wav failed; using original temp file: path=%s, error=%s",
                    temp_audio_path,
                    e,
                )
                canonical_path = temp_audio_path

        if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
            source_label = "converted" if canonical_path != temp_audio_path else "original"
            logger.debug(f"TEST_MODE: canonical audio path resolved: path={canonical_path}, source={source_label}")

        base_dir = PathLib(canonical_path).parent

        sf_mod = _audio_shim_attr("sf")
        duration_seconds = 0.0
        try:
            info_fn = getattr(sf_mod, "info", None)
            if not callable(info_fn):
                raise AttributeError("soundfile.info not available")
            info = info_fn(canonical_path)
            frames = getattr(info, "frames", None)
            samplerate = getattr(info, "samplerate", None)
            if frames is None or not samplerate:
                raise ValueError("soundfile.info returned incomplete metadata")
            duration_seconds = float(frames) / float(samplerate)
        except Exception as e:
            logger.debug(f"soundfile.info failed; falling back to read for duration: error={e}")
            try:
                audio_data, sample_rate = sf_mod.read(canonical_path)
                duration_seconds = float(len(audio_data)) / float(sample_rate or 16000)
            except Exception as read_err:
                logger.debug(f"Failed to compute audio duration; defaulting to 0: error={read_err}")
                duration_seconds = 0.0

        granularity_tokens = set()
        try:
            if timestamp_granularities:
                s = str(timestamp_granularities).strip()
                if s.startswith("["):
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        granularity_tokens = {str(x).strip().lower() for x in arr}
                else:
                    granularity_tokens = {t.strip().lower() for t in s.split(",") if t.strip()}
        except Exception as e:
            logger.debug(f"Failed to parse timestamp_granularities; defaulting to 'segment': error={e}")
            granularity_tokens = {"segment"}
        if not granularity_tokens:
            granularity_tokens = {"segment"}

        task_normalized = (task or "transcribe").strip().lower()
        if task_normalized not in {"transcribe", "translate"}:
            task_normalized = "transcribe"

        hotwords_norm: Optional[list[str]] = None
        raw_hotwords = (hotwords or "").strip()
        if raw_hotwords:
            if raw_hotwords.startswith("["):
                try:
                    parsed_hotwords = json.loads(raw_hotwords)
                    if isinstance(parsed_hotwords, list):
                        hotwords_norm = [str(x).strip() for x in parsed_hotwords if str(x).strip()]
                except Exception as hotwords_exc:
                    logger.debug(f"Failed to parse hotwords JSON; falling back to CSV parsing: {hotwords_exc}")
            if hotwords_norm is None:
                hotwords_norm = [part.strip() for part in raw_hotwords.split(",") if part.strip()]
            if hotwords_norm:
                hotwords_norm = hotwords_norm[:128]
            else:
                hotwords_norm = None

        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import (
            Audio_Files as audio_files,
        )
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
            is_transcription_error_message as _is_transcription_error_message,
        )
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
            validate_whisper_model_identifier,
        )
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
            get_stt_provider_registry,
        )

        stt_registry = get_stt_provider_registry()
        provider, provider_model_name, provider_variant = stt_registry.resolve_provider_for_model(model or "")

        def _raise_on_transcription_error(text: Any) -> None:
            if _is_transcription_error_message(text):
                logger.error(f"Transcription failed: {text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Transcription failed. Please try again or use a different model.",
                )

        minutes_est = duration_seconds / 60.0
        try:
            allow, remaining_after = await _check_daily_minutes_allow(current_user.id, minutes_est)
        except EXPECTED_DB_EXC as e:
            logger.exception(
                "check_daily_minutes_allow failed; allowing by default: user_id=%s, error=%s; request_id=%s",
                current_user.id,
                e,
                rid,
            )
            allow = True
            remaining_after = None
        if not allow:
            try:
                await _audio_shim_attr("finish_job")(current_user.id)
            except EXPECTED_DB_EXC as e:
                logger.exception(
                    "Failed to release job slot after quota denial: user_id=%s, error=%s; request_id=%s",
                    current_user.id,
                    e,
                    rid,
                )
            acquired_job_slot = False
            if job_heartbeat_task:
                job_heartbeat_task.cancel()
                try:
                    await job_heartbeat_task
                except asyncio.CancelledError:
                    pass
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Transcription quota exceeded (daily minutes)"
            )
        detected_language: Optional[str] = None
        segments_for_timing: Optional[list[dict[str, Any]]] = None
        whisper_model_name = _map_openai_audio_model_to_whisper(model)
        if provider == "faster-whisper":
            try:
                whisper_model_name = validate_whisper_model_identifier(whisper_model_name)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_http_error_detail("Invalid transcription model identifier", rid, exc=exc),
                ) from exc
        try:
            if provider == "faster-whisper":
                try:
                    model_status = audio_files.check_transcription_model_status(whisper_model_name)
                    if not model_status.get("available", False):
                        detail_payload: dict[str, Any] = {
                            "status": "model_downloading",
                            "message": model_status.get("message")
                            or "Requested transcription model is not available locally yet.",
                            "model": model_status.get("model", whisper_model_name),
                        }
                        estimated_size = model_status.get("estimated_size")
                        if estimated_size:
                            detail_payload["estimated_size"] = estimated_size
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=detail_payload,
                        )
                except HTTPException:
                    raise
                except Exception as preflight_exc:  # pragma: no cover - defensive
                    logger.debug(f"Whisper model preflight check failed; proceeding without it: {preflight_exc}")
                try:
                    if task_normalized == "translate":
                        selected_lang_for_stt: Optional[str] = None
                    else:
                        selected_lang_for_stt = language if language else None

                    adapter = stt_registry.get_adapter(provider)
                    artifact = adapter.transcribe_batch(
                        canonical_path,
                        model=whisper_model_name,
                        language=selected_lang_for_stt,
                        task=task_normalized,
                        word_timestamps=("word" in granularity_tokens),
                        prompt=prompt,
                        hotwords=hotwords_norm,
                        base_dir=base_dir,
                    )
                    detected_language = artifact.get("language")
                    segments_for_timing = artifact.get("segments") or []
                    transcribed_text = artifact.get("text", "")
                except Exception as e:
                    logger.error(f"Whisper transcription failed: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Whisper transcription failed",
                    ) from e
            else:
                model_for_provider = model or provider_model_name
                try:
                    adapter = stt_registry.get_adapter(provider)
                    artifact = adapter.transcribe_batch(
                        canonical_path,
                        model=model_for_provider,
                        language=language,
                        task=task_normalized,
                        word_timestamps=("word" in granularity_tokens),
                        prompt=prompt,
                        hotwords=hotwords_norm,
                        base_dir=base_dir,
                    )
                    detected_language = artifact.get("language")
                    segments_for_timing = artifact.get("segments") or []
                    transcribed_text = artifact.get("text", "")
                except Exception as e:
                    logger.error(
                        "Transcription failed for provider=%s, model=%s: %s",
                        provider,
                        model_for_provider,
                        e,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=(
                            f"Transcription failed for provider '{provider}' "
                            f"and model '{model_for_provider}'"
                        ),
                    ) from e
        finally:
            try:
                if job_heartbeat_task:
                    job_heartbeat_task.cancel()
                    try:
                        await job_heartbeat_task
                    except asyncio.CancelledError:
                        pass
                if acquired_job_slot:
                    await _audio_shim_attr("finish_job")(current_user.id)
            except EXPECTED_DB_EXC as e:
                logger.exception(
                    "Failed to release job slot in finally: user_id=%s, error=%s; request_id=%s",
                    current_user.id,
                    e,
                    rid,
                )

        _raise_on_transcription_error(transcribed_text)

        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary import (
                postprocess_text_if_enabled as _cv_post,
            )

            transcribed_text = _cv_post(transcribed_text)
        except Exception as exc:
            logger.debug(f"Custom vocabulary postprocessing failed; continuing without it: {exc}")

        try:
            await _add_daily_minutes(current_user.id, minutes_est)
        except EXPECTED_DB_EXC as e:
            logger.exception(
                "Failed to record daily minutes: user_id=%s, error=%s; request_id=%s",
                current_user.id,
                e,
                rid,
            )

        if response_format == "text":
            return Response(content=transcribed_text, media_type="text/plain")

        if response_format == "srt":
            _raise_on_transcription_error(transcribed_text)
            if provider == "faster-whisper" and segments_for_timing:
                lines: list[str] = []

                def _fmt_srt_timestamp(total_seconds: float) -> str:
                    try:
                        if total_seconds is None:
                            total_seconds = 0.0
                        total_ms = int(round(max(float(total_seconds), 0.0) * 1000))
                    except Exception:
                        total_ms = 0
                    seconds, ms = divmod(total_ms, 1000)
                    hours, seconds = divmod(seconds, 3600)
                    minutes, seconds = divmod(seconds, 60)
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

                idx = 1
                for seg in segments_for_timing:
                    if not isinstance(seg, dict):
                        continue
                    text_seg = str(seg.get("Text", "")).strip()
                    if not text_seg:
                        continue
                    start = seg.get("start_seconds", 0.0)
                    end = seg.get("end_seconds", start)
                    start_ts = _fmt_srt_timestamp(start)
                    end_ts = _fmt_srt_timestamp(end)
                    lines.append(str(idx))
                    lines.append(f"{start_ts} --> {end_ts}")
                    lines.append(text_seg)
                    lines.append("")
                    idx += 1

                if lines:
                    srt_content = "\n".join(lines).rstrip() + "\n"
                else:
                    srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{transcribed_text}\n"
            else:
                srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{transcribed_text}\n"
            return Response(content=srt_content, media_type="text/plain")

        if response_format == "vtt":
            _raise_on_transcription_error(transcribed_text)
            if provider == "faster-whisper" and segments_for_timing:
                lines_vtt: list[str] = ["WEBVTT", ""]

                def _fmt_vtt_timestamp(total_seconds: float) -> str:
                    try:
                        if total_seconds is None:
                            total_seconds = 0.0
                        total_ms = int(round(max(float(total_seconds), 0.0) * 1000))
                    except Exception:
                        total_ms = 0
                    seconds, ms = divmod(total_ms, 1000)
                    hours, seconds = divmod(seconds, 3600)
                    minutes, seconds = divmod(seconds, 60)
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"

                for seg in segments_for_timing:
                    if not isinstance(seg, dict):
                        continue
                    text_seg = str(seg.get("Text", "")).strip()
                    if not text_seg:
                        continue
                    start = seg.get("start_seconds", 0.0)
                    end = seg.get("end_seconds", start)
                    start_ts = _fmt_vtt_timestamp(start)
                    end_ts = _fmt_vtt_timestamp(end)
                    lines_vtt.append(f"{start_ts} --> {end_ts}")
                    lines_vtt.append(text_seg)
                    lines_vtt.append("")

                vtt_content = "\n".join(lines_vtt).rstrip() + "\n"
            else:
                vtt_content = f"WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n{transcribed_text}\n"
            return Response(content=vtt_content, media_type="text/vtt")

        response_data: dict[str, Any] = {"text": transcribed_text}

        if language:
            response_data["language"] = language
        elif detected_language:
            response_data["language"] = detected_language

        duration = duration_seconds
        response_data["duration"] = duration

        if "segment" in granularity_tokens:
            if provider == "faster-whisper" and segments_for_timing:
                segs = []
                for i, seg in enumerate(segments_for_timing):
                    if not isinstance(seg, dict):
                        continue
                    start = float(seg.get("start_seconds", 0.0))
                    end = float(seg.get("end_seconds", duration))
                    seg_obj: dict[str, Any] = {
                        "id": i,
                        "start": start,
                        "end": end,
                        "text": seg.get("Text", ""),
                    }
                    if "word" in granularity_tokens and isinstance(seg.get("words"), list):
                        seg_obj["words"] = seg["words"]
                    segs.append(seg_obj)
                response_data["segments"] = segs
            else:
                response_data["segments"] = [
                    {
                        "id": 0,
                        "seek": 0,
                        "start": 0.0,
                        "end": duration,
                        "text": transcribed_text,
                    }
                ]

        if segment:
            try:
                import re

                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Transcript_TreeSegmentation import (
                    TreeSegmenter,
                )

                lines = [ln.strip() for ln in transcribed_text.splitlines() if ln.strip()]
                if not lines:
                    lines = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcribed_text) if s.strip()]
                entries = [{"composite": ln} for ln in lines]

                if entries:
                    configs = {
                        "MIN_SEGMENT_SIZE": seg_min_segment_size,
                        "LAMBDA_BALANCE": seg_lambda_balance,
                        "UTTERANCE_EXPANSION_WIDTH": seg_utterance_expansion_width,
                    }
                    if seg_embeddings_provider:
                        configs["EMBEDDINGS_PROVIDER"] = seg_embeddings_provider
                    if seg_embeddings_model:
                        configs["EMBEDDINGS_MODEL"] = seg_embeddings_model

                    segmenter = await TreeSegmenter.create_async(configs=configs, entries=entries)
                    transitions = segmenter.segment_meeting(K=seg_K)
                    segs = segmenter.get_segments()
                    response_data["segmentation"] = {
                        "transitions": transitions,
                        "transition_indices": segmenter.get_transition_indices(),
                        "segments": segs,
                    }
            except Exception as seg_err:
                logger.warning(f"Auto-segmentation failed: {seg_err}")

        if response_format == "verbose_json":
            response_data["task"] = task_normalized
            response_data["duration"] = duration

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during transcription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_http_error_detail("Transcription failed", rid, exc=e),
        ) from e
    finally:
        if canonical_path and canonical_path != temp_audio_path and os.path.exists(canonical_path):
            try:
                os.remove(canonical_path)
            except OSError as e:
                logger.warning(f"Failed to remove canonical audio file: path={canonical_path}, error={e}")
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except OSError as e:
                logger.warning(f"Failed to remove temp audio file: path={temp_audio_path}, error={e}")
                try:
                    increment_counter(
                        "app_warning_events_total", labels={"component": "audio", "event": "tempfile_remove_failed"}
                    )
                except Exception as m_err:
                    logger.debug(f"metrics increment failed (audio tempfile_remove_failed): error={m_err}")


@router.post(
    "/translations",
    summary="Translates audio into English (OpenAI Compatible)",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_token_scope("any", require_if_present=True, endpoint_id="audio.translations", count_as="call")),
    ],
)
async def create_translation(
    request: Request,
    file: UploadFile = File(..., description="The audio file to translate"),
    model: Optional[str] = Form(
        default=None,
        description="Model to use for translation (defaults to config when omitted)",
    ),
    prompt: Optional[str] = Form(default=None, description="Optional text to guide the model's style"),
    response_format: str = Form(default="json", description="Format of the transcript output"),
    temperature: float = Form(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Sampling temperature (currently ignored by all providers).",
    ),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Translates audio into English.
    """
    if not (model or "").strip():
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
            resolve_default_transcription_model,
        )

        model = resolve_default_transcription_model("whisper-1")

    try:
        usage_log.log_event(
            "audio.translations",
            tags=[str(model or "")],
            metadata={"filename": getattr(file, "filename", None), "language": "en"},
        )
    except Exception as e:
        logger.debug(f"usage_log audio.translations failed: error={e}")

    return await create_transcription(
        request=request,
        file=file,
        model=model,
        language=None,
        prompt=prompt,
        hotwords=None,
        response_format=response_format,
        temperature=temperature,
        task="translate",
        timestamp_granularities="segment",
        segment=False,
        seg_K=6,
        seg_min_segment_size=5,
        seg_lambda_balance=0.01,
        seg_utterance_expansion_width=2,
        seg_embeddings_provider=None,
        seg_embeddings_model=None,
        current_user=current_user,
    )


@router.post("/segment/transcript", summary="Segment a transcript into coherent blocks (TreeSeg)")
async def segment_transcript(
    req: TranscriptSegmentationRequest,
    request: Request,
    current_user: User = Depends(get_request_user),
):
    """
    Segment a transcript into coherent segments using TreeSeg (hierarchical segmentation).
    """
    try:
        if not req.entries or len(req.entries) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entries provided")

        configs = {
            "MIN_SEGMENT_SIZE": req.min_segment_size,
            "LAMBDA_BALANCE": req.lambda_balance,
            "UTTERANCE_EXPANSION_WIDTH": req.utterance_expansion_width,
            "MIN_IMPROVEMENT_RATIO": getattr(req, "min_improvement_ratio", 0.0),
        }
        if req.embeddings_provider:
            configs["EMBEDDINGS_PROVIDER"] = req.embeddings_provider
        if req.embeddings_model:
            configs["EMBEDDINGS_MODEL"] = req.embeddings_model

        entries = [e.model_dump() for e in req.entries]

        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Transcript_TreeSegmentation import (
            TreeSegmenter,
        )

        segmenter = await TreeSegmenter.create_async(configs=configs, entries=entries)
        transitions = segmenter.segment_meeting(K=req.K)
        segs = segmenter.get_segments()

        return TranscriptSegmentationResponse(
            transitions=transitions,
            transition_indices=segmenter.get_transition_indices(),
            segments=segs,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcript segmentation error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcript segmentation failed")
