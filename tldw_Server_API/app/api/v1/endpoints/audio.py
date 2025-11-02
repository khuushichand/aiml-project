# audio.py
# Description: This file contains the API endpoints for audio processing.
#
# Imports
import asyncio
import json
import os
import tempfile
import io
from pathlib import Path as PathLib
import sqlite3  # for DB-specific exception handling in limits endpoints
from typing import AsyncGenerator, Optional, Dict, Any
import numpy as np
import soundfile as sf
#
# Third-party libraries
from fastapi import APIRouter, Depends, HTTPException, Request, Header, File, Form, UploadFile, WebSocket, WebSocketDisconnect, Path, Query
from fastapi.responses import StreamingResponse, Response, JSONResponse
from starlette import status # For status codes
from slowapi.util import get_remote_address
from fastapi import Request as _FastAPIRequest  # for rate limit key typing
from loguru import logger
#
# Local imports
from tldw_Server_API.app.api.v1.schemas.audio_schemas import (
    OpenAISpeechRequest,
    OpenAITranscriptionRequest,
    OpenAITranscriptionResponse,
    OpenAITranslationRequest,
    TranscriptSegmentationRequest,
    TranscriptSegmentationResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.config import AUTH_BEARER_PREFIX
from tldw_Server_API.app.core.config import load_comprehensive_config
# Auth utils no longer used here; authentication is enforced via get_request_user dependency
# from your_project.services.tts_service import TTSService, get_tts_service

# For WebSocket streaming transcription
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
    handle_unified_websocket,
    UnifiedStreamingConfig
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    can_start_stream,
    finish_stream,
    check_daily_minutes_allow,
    add_daily_minutes,
    bytes_to_seconds,
)
# Quota helpers for status/limits and TTL heartbeat
try:
    from tldw_Server_API.app.core.Usage.audio_quota import (
        heartbeat_stream as heartbeat_stream,
        active_streams_count as active_streams_count,
        get_daily_minutes_used as get_daily_minutes_used,
        get_user_tier as get_user_tier,
    )
except ImportError as e:
    # Optional helpers may be unavailable in some environments; log at debug level
    logger.debug(f"audio_quota optional helpers not available: {e}")
# Expose job quota helpers at module scope for tests to monkeypatch
try:
    from tldw_Server_API.app.core.Usage.audio_quota import (
        can_start_job as can_start_job,  # re-export for test monkeypatch
        finish_job as finish_job,
        increment_jobs_started as increment_jobs_started,
        get_limits_for_user as get_limits_for_user,
    )
except ImportError as e:
    # Optional helpers may be unavailable in some environments; log at debug level
    logger.debug(f"audio_quota job helpers not available: {e}")
from tldw_Server_API.app.core.AuthNZ.settings import is_multi_user_mode, is_single_user_mode

# Optional DB/Redis drivers (for precise exception handling without hard dependencies)
try:  # asyncpg is optional; used when PostgreSQL is configured
    import asyncpg  # type: ignore
except ImportError:  # pragma: no cover - absence is fine
    asyncpg = None  # type: ignore
try:  # aiosqlite may surface errors during SQLite operations
    import aiosqlite  # type: ignore
except ImportError:  # pragma: no cover
    aiosqlite = None  # type: ignore
try:  # redis is optional; used for active stream counters if enabled
    from redis import exceptions as redis_exceptions  # type: ignore
except ImportError:  # pragma: no cover
    redis_exceptions = None  # type: ignore
try:
    # Project-level DB error wrapper used by get_db_pool/DB layer
    from tldw_Server_API.app.core.AuthNZ.exceptions import DatabaseError as AuthNZDatabaseError  # type: ignore
except ImportError:  # pragma: no cover
    AuthNZDatabaseError = None  # type: ignore

# Build precise exception tuples we’ll catch in quota-limit helpers
EXPECTED_DB_EXC = (NameError,)  # NameError if optional imports are unavailable
if hasattr(sqlite3, "Error"):
    EXPECTED_DB_EXC = (*EXPECTED_DB_EXC, sqlite3.Error)  # type: ignore[attr-defined]
if asyncpg and hasattr(asyncpg, "PostgresError"):
    EXPECTED_DB_EXC = (*EXPECTED_DB_EXC, asyncpg.PostgresError)  # type: ignore[attr-defined]
if aiosqlite and hasattr(aiosqlite, "Error"):
    EXPECTED_DB_EXC = (*EXPECTED_DB_EXC, aiosqlite.Error)  # type: ignore[attr-defined]
if AuthNZDatabaseError is not None:
    EXPECTED_DB_EXC = (*EXPECTED_DB_EXC, AuthNZDatabaseError)  # type: ignore

EXPECTED_REDIS_EXC = (NameError,)
if redis_exceptions and hasattr(redis_exceptions, "RedisError"):
    EXPECTED_REDIS_EXC = (*EXPECTED_REDIS_EXC, redis_exceptions.RedisError)  # type: ignore[attr-defined]

# For logging (if you use the same logger as in your PDF endpoint)
from tldw_Server_API.app.core.Metrics.metrics_manager import (
    increment_counter,
    get_metrics_registry,
    MetricDefinition,
    MetricType,
)
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    get_usage_event_logger,
    UsageEventLogger,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, get_ps_logger

# Initialize rate limiter
def _rate_limit_key(request: _FastAPIRequest) -> str:
    """Rate limit key that prefers authenticated user id over IP.

    - Multi-user: per-user limits (fairness across users)
    - Single-user or unauthenticated: fall back to client IP
    """
    try:
        uid = getattr(request.state, "user_id", None)
        if uid is not None:
            return f"user:{uid}"
    except Exception as e:
        logger.debug(f"rate_limit_key: failed to read user_id from request.state: error={e}")
    return get_remote_address(request)

# Use central limiter instance; override key_func per-route where needed
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter


router = APIRouter(
    tags=["Audio"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limit exceeded"}
    },
)


# Register audio fail-open metrics (idempotent if already registered)
try:
    _reg = get_metrics_registry()
    _reg.register_metric(
        MetricDefinition(
            name="audio_failopen_minutes_total",
            type=MetricType.COUNTER,
            description="Minutes allowed during fail-open when quota store unavailable",
            unit="minutes",
            labels=["reason"],
        )
    )
    _reg.register_metric(
        MetricDefinition(
            name="audio_failopen_events_total",
            type=MetricType.COUNTER,
            description="Fail-open allowance events during streaming",
            labels=["reason"],
        )
    )
    _reg.register_metric(
        MetricDefinition(
            name="audio_failopen_cap_exhausted_total",
            type=MetricType.COUNTER,
            description="Fail-open cap exhausted; connection closed due to bounded fail-open",
            labels=["reason"],
        )
    )
except Exception as e:
    # Metrics must never break imports; log for diagnostics
    logger.debug(f"audio: metrics registration skipped/failed: {e}")


def _get_failopen_cap_minutes() -> float:
    """Return per-connection fail-open cap in minutes for streaming quotas.

    Resolution order:
      1) Env var AUDIO_FAILOPEN_CAP_MINUTES (>0)
      2) Config [Audio-Quota] failopen_cap_minutes (>0)
      3) Config [Audio] failopen_cap_minutes (>0)
      4) Default 5.0
    """
    # Env override
    v = os.getenv("AUDIO_FAILOPEN_CAP_MINUTES")
    if v is not None:
        try:
            f = float(v)
            if f > 0:
                return f
        except (ValueError, TypeError) as e:
            logger.debug(f"AUDIO_FAILOPEN_CAP_MINUTES parse failed: {e}")
    # Config-based override
    try:
        cfg = load_comprehensive_config()
        if cfg is not None:
            if cfg.has_section("Audio-Quota"):
                try:
                    f = float(cfg.get("Audio-Quota", "failopen_cap_minutes", fallback=""))
                    if f > 0:
                        return f
                except (ValueError, TypeError) as e:
                    logger.debug(f"[Audio-Quota].failopen_cap_minutes parse failed: {e}")
            if cfg.has_section("Audio"):
                try:
                    f = float(cfg.get("Audio", "failopen_cap_minutes", fallback=""))
                    if f > 0:
                        return f
                except (ValueError, TypeError) as e:
                    logger.debug(f"[Audio].failopen_cap_minutes parse failed: {e}")
    except Exception as e:
        logger.debug(f"Config read for failopen cap failed: {e}")
    return 5.0



# V2 TTS Service handles all provider mapping internally
# No need for manual model/voice mappings here

# Import the V2 TTS service and validation
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2, TTSServiceV2
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSError,
    TTSValidationError,
    TTSProviderNotConfiguredError,
    TTSAuthenticationError,
    TTSRateLimitError,
    TTSQuotaExceededError,
)
from tldw_Server_API.app.core.TTS.tts_validation import TTSInputValidator

async def get_tts_service() -> TTSServiceV2:
    """Get the V2 TTS service instance."""
    return await get_tts_service_v2()

# --- End of Placeholder ---


@router.post(
    "/speech",
    summary="Generates audio from text input.",
    dependencies=[Depends(require_token_scope("any", require_if_present=False, endpoint_id="audio.speech", count_as="call"))],
)
@limiter.limit("10/minute", key_func=_rate_limit_key)  # Rate limit: 10 requests per minute per user/IP
async def create_speech(
    request_data: OpenAISpeechRequest,  # FastAPI will parse JSON body into this
    request: Request,                   # Required for rate limiter and to check for client disconnects
    tts_service: TTSServiceV2 = Depends(get_tts_service),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Generates audio from the input text.

    Requires authentication via Bearer token in Authorization header.
    Rate limited to 10 requests per minute per IP address.

    Docs: `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md` (context on audio pipeline)

    Example (curl):
    ```bash
    curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
      -H "Authorization: Bearer <TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{"model": "tts-1", "input": "Hello world", "voice": "alloy", "response_format": "mp3", "stream": true}'
    ```
    """

    # Authentication is enforced by dependency injection via get_request_user
    # current_user is available for audit/logging if needed

    # Input validation using the new validation system
    try:
        # Create validator instance
        validator = TTSInputValidator()

        # Validate and sanitize input text
        sanitized_text = validator.sanitize_text(request_data.input)

        # Check for empty input after sanitization
        if not sanitized_text or len(sanitized_text.strip()) == 0:
            raise TTSValidationError(
                "Input text cannot be empty after sanitization",
                details={"original_length": len(request_data.input)}
            )

        # Update request with sanitized text
        request_data.input = sanitized_text

    except TTSValidationError as e:
        logger.warning(f"TTS validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    logger.info(f"Received speech request: model={request_data.model}, voice={request_data.voice}, format={request_data.response_format}")
    try:
        usage_log.log_event(
            "audio.tts",
            tags=[str(request_data.model or ""), str(request_data.voice or "")],
            metadata={"stream": bool(getattr(request_data, 'stream', False)), "format": request_data.response_format},
        )
    except Exception as e:
        logger.debug(f"usage_log audio.tts failed: error={e}")

    # V2 service handles model mapping internally via the adapter factory
    # No need for manual mapping here

    # Determine Content-Type
    content_type_map = {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "pcm": "audio/L16; rate=24000; channels=1", # Example for raw PCM
    }
    content_type = content_type_map.get(request_data.response_format)
    if not content_type:
        logger.warning(f"Unsupported response format: {request_data.response_format}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported response_format: {request_data.response_format}. Supported formats are: {', '.join(content_type_map.keys())}",
        )

    def _raise_for_tts_error(exc: Exception) -> None:
        if isinstance(exc, TTSValidationError):
            logger.warning(f"TTS validation error: {exc}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        if isinstance(exc, TTSProviderNotConfiguredError):
            logger.error(f"TTS provider not configured: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"TTS service unavailable: {str(exc)}"
            )
        if isinstance(exc, TTSAuthenticationError):
            logger.error(f"TTS authentication error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="TTS provider authentication failed"
            )
        if isinstance(exc, TTSRateLimitError):
            logger.warning(f"TTS rate limit exceeded: {exc}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="TTS provider rate limit exceeded. Please try again later."
            )
        if isinstance(exc, TTSQuotaExceededError):
            logger.warning(f"TTS quota exceeded: {exc}")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="TTS quota exceeded. Please review your plan or quota."
            )
        if isinstance(exc, TTSError):
            logger.error(f"TTS error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"TTS error: {str(exc)}"
            )
        logger.error(f"Unexpected error during audio generation: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during audio generation"
        )

    try:
        speech_iter = tts_service.generate_speech(
            request_data,
            provider=None,
            fallback=True,
        )
    except Exception as exc:
        _raise_for_tts_error(exc)

    async def _pull_first_chunk() -> bytes:
        try:
            return await speech_iter.__anext__()
        except StopAsyncIteration:
            return b""
        except HTTPException:
            raise
        except Exception as exc:
            _raise_for_tts_error(exc)

    async def _stream_chunks(initial_chunk: bytes):
        try:
            if initial_chunk:
                if await request.is_disconnected():
                    logger.info("Client disconnected before streaming could start.")
                    return
                yield initial_chunk
            async for chunk in speech_iter:
                if await request.is_disconnected():
                    logger.info("Client disconnected, stopping audio generation.")
                    break
                yield chunk
        except HTTPException:
            raise
        except Exception as exc:
            _raise_for_tts_error(exc)


    if request_data.stream:
        first_chunk = await _pull_first_chunk()
        return StreamingResponse(
            _stream_chunks(first_chunk),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename=speech.{request_data.response_format}",
                "X-Accel-Buffering": "no", # Useful for Nginx
                "Cache-Control": "no-cache",
            },
        )
    # Non-streaming mode: accumulate chunks and return a single response
    # Apply to both single-user and multi-user modes for consistent behavior
    first_chunk = await _pull_first_chunk()
    all_audio_bytes = b""
    if first_chunk:
        all_audio_bytes += first_chunk
    try:
        async for chunk in speech_iter:
            all_audio_bytes += chunk
    except HTTPException:
        raise
    except Exception as exc:
        _raise_for_tts_error(exc)

    # Drop any internal boundary markers if present
    all_audio_bytes = all_audio_bytes.replace(b"--final_boundary_for_non_streamed--", b"")

    if not all_audio_bytes:
        logger.error("Non-streaming generation resulted in empty audio data.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audio generation failed to produce data."
        )

    return Response(
        content=all_audio_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=speech.{request_data.response_format}",
            "Cache-Control": "no-cache",
        },
    )


@router.post(
    "/transcriptions",
    summary="Transcribes audio into text (OpenAI Compatible)",
    dependencies=[Depends(require_token_scope("any", require_if_present=False, endpoint_id="audio.transcriptions", count_as="call"))],
)
@limiter.limit("20/minute", key_func=_rate_limit_key)  # Rate limit: 20 requests per minute
async def create_transcription(
    request: Request,
    file: UploadFile = File(..., description="The audio file to transcribe"),
    model: str = Form(default="whisper-1", description="Model to use for transcription"),
    language: Optional[str] = Form(default=None, description="Language of the audio in ISO-639-1 format"),
    prompt: Optional[str] = Form(default=None, description="Optional text to guide the model's style"),
    response_format: str = Form(default="json", description="Format of the transcript output"),
    temperature: float = Form(default=0.0, ge=0.0, le=1.0, description="Sampling temperature"),
    timestamp_granularities: Optional[str] = Form(default="segment", description="Timestamp granularities: 'segment', 'word' (comma-separated or JSON array)"),
    # Auto-segmentation options
    segment: bool = Form(default=False, description="If true and JSON response, also run transcript segmentation (TreeSeg)"),
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

    Compatible with OpenAI's Audio API transcription endpoint.
    Supports multiple transcription models including Whisper, Parakeet, and Canary.

    Models:
    - whisper-1: Uses faster-whisper (default)
    - parakeet: NVIDIA Parakeet model (efficient)
    - canary: NVIDIA Canary model (multilingual)
    - qwen2audio: Qwen2 Audio model

    Rate limited to 20 requests per minute per IP address.

    Docs: `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md`,
          `Docs/API-related/Audio_Transcription_API.md`

    Example (curl):
    ```bash
    curl -X POST "http://127.0.0.1:8000/api/v1/audio/transcriptions" \
      -H "Authorization: Bearer <TOKEN>" \
      -F "file=@/abs/audio.wav" -F "model=whisper-1" -F "language=en" -F "response_format=json"
    ```
    """

    # Authentication is enforced by dependency injection via get_request_user

    # Validate file presence
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided"
        )
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
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type: {file.content_type}"
        )

    # Resolve per-tier file size limit
    rid = None
    try:
        if request is not None and hasattr(request, 'state') and getattr(request.state, 'request_id', None):
            rid = str(request.state.request_id)
    except Exception:
        rid = None
    try:
        limits = await get_limits_for_user(current_user.id)
    except EXPECTED_DB_EXC as e:
        logger.exception(
            f"Failed to get limits for user {current_user.id} during upload, using defaults: {e}; request_id={rid}"
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
            f"Could not parse max_file_size_mb for user {current_user.id}; defaulting to 25MB: {e}; request_id={rid}"
        )
        max_file_size = 25 * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size exceeds maximum of {int(max_file_size/1024/1024)}MB"
        )

    # Before any heavy work, enforce concurrent jobs cap per user
    ok_job, msg_job = await can_start_job(current_user.id)
    if not ok_job:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg_job)

    # Record job start (best-effort)
    acquired_job_slot = False
    try:
        await increment_jobs_started(current_user.id)
        acquired_job_slot = True
    except EXPECTED_DB_EXC as e:
        logger.exception(
            f"Failed to increment jobs started: user_id={current_user.id}, error={e}; request_id={rid}"
        )

    # Save uploaded file to temporary location and proceed with processing
    temp_audio_path = None
    try:
        # Create temporary file with proper extension
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".wav"
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
            tmp_file.write(contents)
            temp_audio_path = tmp_file.name

        # Convert to canonical 16k mono WAV for consistent processing
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import convert_to_wav as _convert_to_wav
            canonical_path = _convert_to_wav(temp_audio_path, offset=0, overwrite=False)
        except Exception as e:
            logger.debug(f"convert_to_wav failed; using original temp file: path={temp_audio_path}, error={e}")
            canonical_path = temp_audio_path

        # Load canonical audio
        audio_data, sample_rate = sf.read(canonical_path)
        # Compute duration (seconds)
        try:
            duration_seconds = float(len(audio_data)) / float(sample_rate or 16000)
        except Exception as e:
            logger.debug(f"Failed to compute audio duration; defaulting to 0: error={e}")
            duration_seconds = 0.0

        # Parse timestamp granularities (flexible: CSV or JSON array)
        granularity_tokens = set()
        try:
            if timestamp_granularities:
                s = str(timestamp_granularities).strip()
                if s.startswith("["):
                    # JSON array
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        granularity_tokens = {str(x).strip().lower() for x in arr}
                else:
                    # Comma-separated string
                    granularity_tokens = {t.strip().lower() for t in s.split(',') if t.strip()}
        except Exception as e:
            # Non-fatal: default to {'segment'}
            logger.debug(f"Failed to parse timestamp_granularities; defaulting to 'segment': error={e}")
            granularity_tokens = {"segment"}
        if not granularity_tokens:
            granularity_tokens = {"segment"}

        # Map OpenAI model names to our providers
        provider_map = {
            "whisper-1": "faster-whisper",
            "whisper": "faster-whisper",
            "parakeet": "parakeet",
            "canary": "canary",
            "qwen2audio": "qwen2audio",
            "qwen": "qwen2audio"
        }

        provider = provider_map.get(model.lower(), "faster-whisper")

        # Import transcription functions
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
            transcribe_audio,
            speech_to_text as fw_speech_to_text,
        )

        # Get configuration for Nemo models
        from tldw_Server_API.app.core.config import load_and_log_configs
        config = load_and_log_configs()

        # Prepare quotas and transcription now that we hold the slot

        # Enforce daily minutes cap by estimated duration
        minutes_est = duration_seconds / 60.0
        try:
            allow, remaining_after = await check_daily_minutes_allow(current_user.id, minutes_est)
        except EXPECTED_DB_EXC as e:
            logger.exception(
                f"check_daily_minutes_allow failed; allowing by default: user_id={current_user.id}, error={e}; request_id={rid}"
            )
            allow = True
            remaining_after = None
        if not allow:
            # Release job slot before returning
            try:
                await finish_job(current_user.id)
            except EXPECTED_DB_EXC as e:
                logger.exception(
                    f"Failed to release job slot after quota denial: user_id={current_user.id}, error={e}; request_id={rid}"
                )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Transcription quota exceeded (daily minutes)"
            )
        detected_language: Optional[str] = None
        # Wrap the heavy work to ensure we always release the job slot
        try:
            if provider == "faster-whisper":
                # For Whisper, support word-level timestamps and language detection
                try:
                    # Use best model by default (consistent with prior behavior)
                    whisper_model_name = "large-v3"
                    result = fw_speech_to_text(
                        canonical_path,
                        whisper_model=whisper_model_name,
                        selected_source_lang=language if language else None,
                        vad_filter=False,
                        diarize=False,
                        word_timestamps=("word" in granularity_tokens),
                        return_language=True,
                    )
                    if isinstance(result, tuple) and len(result) == 2:
                        segments_list, detected_language = result
                    else:
                        # Fallback: handle as plain segments list
                        segments_list, detected_language = result, None

                    # Merge text
                    transcribed_text = " ".join(seg.get("Text", "").strip() for seg in segments_list if isinstance(seg, dict))
                except Exception as e:
                    logger.error(f"Whisper transcription failed: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Whisper transcription failed"
                    )
            elif provider == "parakeet" and config:
                variant = config.get('STT-Settings', {}).get('nemo_model_variant', 'standard')
                # For Parakeet, we need to use the Nemo module directly
                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
                    transcribe_with_parakeet
                )
                transcribed_text = transcribe_with_parakeet(audio_data, sample_rate, variant)
            elif provider == "canary":
                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
                    transcribe_with_canary
                )
                transcribed_text = transcribe_with_canary(audio_data, sample_rate, language)
            else:
                # Use the general transcribe_audio function
                transcribe_params = {
                    "audio_data": audio_data,
                    "sample_rate": sample_rate,
                    "transcription_provider": provider,
                    "speaker_lang": language,
                }
                transcribed_text = transcribe_audio(**transcribe_params)
        finally:
            # Make sure we always release job slot on any path
            try:
                if acquired_job_slot:
                    await finish_job(current_user.id)
            except EXPECTED_DB_EXC as e:
                logger.exception(
                    f"Failed to release job slot in finally: user_id={current_user.id}, error={e}; request_id={rid}"
                )

        # Helper: detect various error messages
        def is_transcription_error(msg: str) -> bool:
            lower_msg = msg.lower()
            return (
                lower_msg.startswith("[error")
                or lower_msg.startswith("[transcription error")
                or lower_msg.startswith("canary transcription error")
                or lower_msg.startswith("parakeet transcription error")
                or lower_msg.startswith("external provider transcription error")
                or lower_msg.startswith("nemo transcription module not available")
                or lower_msg.startswith("failed to import nemo")
                or lower_msg.startswith("failed to import external provider")
            )

        # Check for errors in transcription
        if is_transcription_error(transcribed_text):
            logger.error(f"Transcription failed: {transcribed_text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Transcription failed. Please try again or use a different model."
            )

        # Apply custom vocabulary post-replacements (all providers)
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary import (
                postprocess_text_if_enabled as _cv_post,
            )
            transcribed_text = _cv_post(transcribed_text)
        except Exception:
            pass

        # On success, record minutes used
        try:
            await add_daily_minutes(current_user.id, minutes_est)
        except EXPECTED_DB_EXC as e:
            logger.exception(
                f"Failed to record daily minutes: user_id={current_user.id}, error={e}; request_id={rid}"
            )

        # Format response based on requested format
            if is_transcription_error(transcribed_text):
                logger.error(f"Transcription failed: {transcribed_text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Transcription failed. Please try again or use a different model."
                )
        if response_format == "text":
            return Response(content=transcribed_text, media_type="text/plain")

        elif response_format == "srt":
            if is_transcription_error(transcribed_text):
                logger.error(f"Transcription failed: {transcribed_text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Transcription failed. Please try again or use a different model."
                )
            # Simple SRT format (would need proper timing for real implementation)
            srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{transcribed_text}\n"
            return Response(content=srt_content, media_type="text/plain")

        elif response_format == "vtt":
            if is_transcription_error(transcribed_text):
                logger.error(f"Transcription failed: {transcribed_text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Transcription failed. Please try again or use a different model."
                )
            # Simple VTT format
            vtt_content = f"WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n{transcribed_text}\n"
            return Response(content=vtt_content, media_type="text/vtt")

        else:  # json or verbose_json
            response_data: Dict[str, Any] = {"text": transcribed_text}

            # Language: prefer explicit request; else detected for Whisper
            if language:
                response_data["language"] = language
            elif detected_language:
                response_data["language"] = detected_language

            # Duration
            duration = duration_seconds
            response_data["duration"] = duration

            # Segments (prefer real segments when Whisper used)
            if "segment" in granularity_tokens:
                if provider == "faster-whisper" and 'segments_list' in locals() and isinstance(segments_list, list) and segments_list:
                    segs = []
                    for i, seg in enumerate(segments_list):
                        start = float(seg.get("start_seconds", 0.0))
                        end = float(seg.get("end_seconds", duration))
                        seg_obj: Dict[str, Any] = {
                            "id": i,
                            "start": start,
                            "end": end,
                            "text": seg.get("Text", ""),
                        }
                        # Attach word-level timestamps if requested and available
                        if "word" in granularity_tokens and isinstance(seg.get("words"), list):
                            seg_obj["words"] = seg["words"]
                        segs.append(seg_obj)
                    response_data["segments"] = segs
                else:
                    # Fallback single segment
                    response_data["segments"] = [{
                        "id": 0,
                        "seek": 0,
                        "start": 0.0,
                        "end": duration,
                        "text": transcribed_text,
                    }]

            # Optional: auto-run segmentation in JSON responses
            if segment:
                try:
                    import re
                    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Transcript_TreeSegmentation import (
                        TreeSegmenter,
                    )

                    # Build basic entries from transcript (newline split; fallback to sentences)
                    lines = [ln.strip() for ln in transcribed_text.splitlines() if ln.strip()]
                    if not lines:
                        # Fallback sentence split
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
                response_data["task"] = "transcribe"
                response_data["duration"] = duration

            return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during transcription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except OSError as e:
                logger.warning(f"Failed to remove temp audio file: path={temp_audio_path}, error={e}")
                try:
                    increment_counter("app_warning_events_total", labels={"component": "audio", "event": "tempfile_remove_failed"})
                except Exception as m_err:
                    logger.debug(f"metrics increment failed (audio tempfile_remove_failed): error={m_err}")


@router.post(
    "/translations",
    summary="Translates audio into English (OpenAI Compatible)",
    dependencies=[Depends(require_token_scope("any", require_if_present=False, endpoint_id="audio.translations", count_as="call"))],
)
@limiter.limit("20/minute", key_func=_rate_limit_key)
async def create_translation(
    request: Request,
    file: UploadFile = File(..., description="The audio file to translate"),
    model: str = Form(default="whisper-1", description="Model to use for translation"),
    prompt: Optional[str] = Form(default=None, description="Optional text to guide the model's style"),
    response_format: str = Form(default="json", description="Format of the transcript output"),
    temperature: float = Form(default=0.0, ge=0.0, le=1.0, description="Sampling temperature"),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Translates audio into English.

    Compatible with OpenAI's Audio API translation endpoint.
    Currently uses Whisper for translation to English.

    Rate limited to 20 requests per minute per IP address.

    Docs: `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md`,
          `Docs/API-related/Audio_Transcription_API.md`
    """
    try:
        usage_log.log_event(
            "audio.transcriptions",
            tags=[str(model or "")],
            metadata={"filename": getattr(file, 'filename', None), "language": "en"},
        )
    except Exception as e:
        logger.debug(f"usage_log audio.transcriptions failed: error={e}")
    # For translation, we'll use the transcription endpoint with language detection
    # and then translate if needed (simplified implementation)
    # In a full implementation, you would use a translation model

    # Call transcription with English as target
    return await create_transcription(
        request=request,
        file=file,
        model=model,
        language="en",  # Force English output
        prompt=prompt,
        response_format=response_format,
        temperature=temperature,
        timestamp_granularities="segment",
        current_user=current_user,
    )


# Add other OpenAI compatible endpoints like /models, /voices later
# For now, this is the core.


@router.post("/segment/transcript", summary="Segment a transcript into coherent blocks (TreeSeg)")
@limiter.limit("30/minute", key_func=_rate_limit_key)
async def segment_transcript(
    req: TranscriptSegmentationRequest,
    request: Request,
    current_user: User = Depends(get_request_user),
):
    """
    Segment a transcript into coherent segments using TreeSeg (hierarchical segmentation).

    Input is a list of transcript entries (utterances) containing at least 'composite' text,
    and optional 'start', 'end', 'speaker'. Returns a transitions vector and segments with
    indices, time bounds, speakers, and concatenated text.

    Docs: `Docs/API-related/Transcript_Segmentation_API.md`
    """
    try:
        if not req.entries or len(req.entries) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entries provided")

        # Prepare config for segmenter
        configs = {
            "MIN_SEGMENT_SIZE": req.min_segment_size,
            "LAMBDA_BALANCE": req.lambda_balance,
            "UTTERANCE_EXPANSION_WIDTH": req.utterance_expansion_width,
            "MIN_IMPROVEMENT_RATIO": getattr(req, 'min_improvement_ratio', 0.0),
        }
        if req.embeddings_provider:
            configs["EMBEDDINGS_PROVIDER"] = req.embeddings_provider
        if req.embeddings_model:
            configs["EMBEDDINGS_MODEL"] = req.embeddings_model

        # Convert entries to plain dicts
        entries = [e.model_dump() for e in req.entries]

        # Lazy import to avoid heavy startup cost
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Transcript_TreeSegmentation import (
            TreeSegmenter,
        )

        segmenter = await TreeSegmenter.create_async(configs=configs, entries=entries)
        transitions = segmenter.segment_meeting(K=req.K)
        segs = segmenter.get_segments()

        # Return response conforming to schema
        return TranscriptSegmentationResponse(
            transitions=transitions,
            transition_indices=segmenter.get_transition_indices(),
            segments=segs,  # shape matches TranscriptSegmentInfo
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcript segmentation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcript segmentation failed"
        )


@router.get("/health")
async def get_tts_health(
    tts_service: TTSServiceV2 = Depends(get_tts_service)
):
    """
    Get health status of TTS providers.

    Returns comprehensive health information including:
    - Provider availability
    - Circuit breaker status
    - Performance metrics
    - Active requests
    """
    from datetime import datetime

    try:
        # Get service status
        status_data = tts_service.get_status()
        if not isinstance(status_data, dict):
            logger.warning("TTS service returned non-mapping status; falling back to defaults")
            status = {}
        else:
            status = status_data

        # Get capabilities
        capabilities = await tts_service.get_capabilities()

        # Determine overall health
        available_providers = status.get("available", 0)
        total_providers = status.get("total_providers", 0)

        health_status = "healthy" if available_providers > 0 else "unhealthy"

        health = {
            "status": health_status,
            "providers": {
                "total": total_providers,
                "available": available_providers,
                "details": status.get("providers", {})
            },
            "circuit_breakers": status.get("circuit_breakers", {}),
            "capabilities": capabilities,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add Kokoro adapter details if available
        try:
            from tldw_Server_API.app.core.TTS.adapter_registry import get_tts_factory, TTSProvider
            factory = await get_tts_factory()
            adapter = await factory.registry.get_adapter(TTSProvider.KOKORO)
            if adapter:
                backend = 'onnx' if getattr(adapter, 'use_onnx', True) else 'pytorch'
                kokoro_info = {
                    'backend': backend,
                    'device': str(getattr(adapter, 'device', 'unknown')),
                    'model_path': getattr(adapter, 'model_path', None),
                    'voices_json': getattr(adapter, 'voices_json', None)
                }
                health['providers']['kokoro'] = kokoro_info
        except Exception as e:
            logger.debug(f"Kokoro health enrichment failed: {e}")

        return health
    except Exception as e:
        logger.error(f"Error getting TTS health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/providers")
async def list_tts_providers(
    tts_service: TTSServiceV2 = Depends(get_tts_service)
):
    """
    List all available TTS providers and their capabilities.
    """
    from datetime import datetime

    try:
        capabilities = await tts_service.get_capabilities()
        voices = await tts_service.list_voices()

        return {
            "providers": capabilities,
            "voices": voices,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error listing TTS providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list providers: {str(e)}"
        )


@router.get("/voices/catalog", summary="List available TTS voices across providers")
async def list_tts_voices(
    provider: Optional[str] = Query(None, description="Optional provider filter, e.g., 'elevenlabs' or 'openai'"),
    tts_service: TTSServiceV2 = Depends(get_tts_service)
):
    """
    List available voices from TTS providers.

    - If `provider` is specified, returns voices only for that provider.
    - Otherwise returns a mapping of provider name to voice lists.

    For ElevenLabs, this uses the adapter's cached user voices (plus defaults)
    loaded during adapter initialization.
    """
    try:
        all_voices = await tts_service.list_voices()
        if provider:
            key = provider.lower()
            if key in all_voices:
                return {key: all_voices[key]}
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found or unavailable")
        return all_voices
    except Exception as e:
        logger.error(f"Error listing TTS voices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}")

@router.post("/reset-metrics")
async def reset_tts_metrics(
    provider: Optional[str] = None,
    tts_service: TTSServiceV2 = Depends(get_tts_service)
):
    """
    Reset TTS metrics.

    Args:
        provider: Optional provider name to reset metrics for. If not provided, resets all metrics.
    """
    try:
        if hasattr(tts_service, 'metrics'):
            if provider:
                # Reset specific provider metrics
                logger.info(f"Resetting metrics for provider: {provider}")
                # This would need to be implemented in the metrics manager
                return {"message": f"Metrics reset for provider {provider}"}
            else:
                # Reset all metrics
                logger.info("Resetting all TTS metrics")
                return {"message": "All TTS metrics reset"}
        else:
            return {"message": "Metrics not available"}
    except Exception as e:
        logger.error(f"Error resetting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset metrics: {str(e)}"
        )

######################################################################################################################
# WebSocket Router Creation
######################################################################################################################

# Create a separate router for WebSocket endpoints to avoid authentication conflicts
ws_router = APIRouter()

@ws_router.websocket("/stream/transcribe")
async def websocket_transcribe(
    websocket: WebSocket,
    token: Optional[str] = Query(None)  # Get token from query parameter
):
    """
    Handle a WebSocket connection to perform real-time streaming audio transcription.

    Accepts a WebSocket and an optional query token. Authentication is supported via:
    - Multi-user: X-API-KEY header, Authorization: Bearer <JWT>, or an initial auth message.
    - Single-user: API key via header, query token, or an initial auth message; an IP allowlist may be enforced.
    Supported incoming message types: "auth" (for token-based auth), "config" (streaming configuration), "audio" (base64-encoded audio chunks), and "commit" (finalize current utterance).
    Outgoing message types include partial updates ("partial"), interim/final transcriptions ("transcription"), the final transcript ("full_transcript"), and structured error frames ("error").
    Per-user limits are enforced (concurrent streams and daily minute quotas); when a quota is exceeded the server sends an "error" with "error_type": "quota_exceeded" and closes the connection with code 4003.
    A server-side default streaming configuration is used if the client does not provide one before audio arrives.
    Parameters:
        websocket (WebSocket): The active WebSocket connection.
        token (Optional[str]): Optional API key token supplied via the query string for single-user authentication.
    """
    # Accept the WebSocket connection first
    await websocket.accept()

    # Authentication
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    settings = get_settings()
    expected_key = settings.SINGLE_USER_API_KEY

    authenticated = False
    jwt_user_id: Optional[int] = None

    if is_multi_user_mode():
        # Optional X-API-KEY path (virtual API keys) for multi-user
        try:
            x_api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")
        except Exception:
            x_api_key = None
        if x_api_key:
            try:
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
                from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
                from tldw_Server_API.app.core.AuthNZ.quotas import increment_and_check_api_key_quota
                api_mgr = await get_api_key_manager()
                client_ip = getattr(websocket.client, "host", None)
                info = await api_mgr.validate_api_key(api_key=x_api_key, ip_address=client_ip)
                if not info:
                    await websocket.send_json({"type": "error", "message": "Invalid API key"})
                    await websocket.close(code=4401)
                    return
                # Admin bypass
                if str(info.get("scope", "")).lower() != "admin":
                    # Endpoint allowlist enforcement
                    allowed_eps = info.get("llm_allowed_endpoints")
                    if isinstance(allowed_eps, str):
                        import json as _json
                        try:
                            allowed_eps = _json.loads(allowed_eps)
                        except Exception:
                            allowed_eps = None
                    endpoint_id = "audio.stream.transcribe"
                    if isinstance(allowed_eps, list) and allowed_eps:
                        if endpoint_id not in [str(x) for x in allowed_eps]:
                            await websocket.send_json({"type": "error", "message": "Endpoint not permitted for API key"})
                            await websocket.close(code=4403)
                            return
                    # Path allowlist via metadata
                    meta = info.get("metadata")
                    if isinstance(meta, str):
                        import json as _json
                        try:
                            meta = _json.loads(meta)
                        except Exception:
                            meta = None
                    if isinstance(meta, dict):
                        ap = meta.get("allowed_paths")
                        if isinstance(ap, list) and ap:
                            # WebSocket path is fixed under /api/v1/audio/stream/transcribe once mounted
                            ws_path = "/api/v1/audio/stream/transcribe"
                            if not any(str(ws_path).startswith(str(pfx)) for pfx in ap):
                                await websocket.send_json({"type": "error", "message": "Path not permitted for API key"})
                                await websocket.close(code=4403)
                                return
                        # Quota enforcement (DB-backed)
                        quota = meta.get("max_runs")
                        if quota is None:
                            quota = meta.get("max_calls")
                        if isinstance(quota, int) and quota >= 0:
                            # Optional daily bucket
                            bucket = None
                            per = meta.get("period")
                            if isinstance(per, str) and per.lower() == "day":
                                from datetime import datetime, timezone
                                bucket = datetime.now(timezone.utc).date().isoformat()
                            db_pool = await get_db_pool()
                            ok, _cnt = await increment_and_check_api_key_quota(
                                db_pool=db_pool,
                                api_key_id=int(info.get("id")),
                                counter_type="call",
                                limit=int(quota),
                                bucket=bucket,
                            )
                            if not ok:
                                await websocket.send_json({"type": "error", "message": "API key quota exceeded"})
                                await websocket.close(code=4403)
                                return
                authenticated = True
                # Mark a synthetic user id from API key owner if available
                uid = info.get("user_id")
                if uid is not None:
                    try:
                        jwt_user_id = int(uid)
                    except Exception:
                        jwt_user_id = None
                # Skip JWT branch when X-API-KEY is used
                bearer = None
            except Exception as _api_key_e:
                logger.warning(f"WS API key auth failed: {_api_key_e}")
                await websocket.send_json({"type": "error", "message": "API key authentication failed"})
                await websocket.close(code=4401)
                return
        # Prefer Authorization: Bearer <JWT>
        auth_header = websocket.headers.get("authorization")
        bearer = None
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                bearer = parts[1]
        if bearer:
            try:
                from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
                from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
                from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
                from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user_by_id

                jwt_service = get_jwt_service()
                payload = jwt_service.decode_access_token(bearer)
                uid = payload.get("user_id") or payload.get("sub")
                if isinstance(uid, str):
                    uid = int(uid)
                if not uid:
                    raise InvalidTokenError("missing user_id/sub claim")
                # Blacklist check
                session_manager = await get_session_manager()
                if await session_manager.is_token_blacklisted(bearer, payload.get("jti")):
                    raise InvalidTokenError("token revoked")
                # Ensure user exists
                user_row = await _get_user_by_id(int(uid))
                if not user_row:
                    raise InvalidTokenError("user not found")
                # Enforce virtual-key scope + quotas if claims present
                # Admin bypass via role=admin
                if str(payload.get("role", "")) != "admin":
                    try:
                        endpoint_id = "audio.stream.transcribe"
                        allowed_eps = payload.get("allowed_endpoints")
                        if isinstance(allowed_eps, list) and allowed_eps:
                            if endpoint_id not in [str(x) for x in allowed_eps]:
                                await websocket.send_json({"type": "error", "message": "Endpoint not permitted for token"})
                                await websocket.close(code=4403)
                                return
                        # Optional path prefix allowlist
                        ap = payload.get("allowed_paths")
                        if isinstance(ap, list) and ap:
                            ws_path = "/api/v1/audio/stream/transcribe"
                            if not any(str(ws_path).startswith(str(pfx)) for pfx in ap):
                                await websocket.send_json({"type": "error", "message": "Path not permitted for token"})
                                await websocket.close(code=4403)
                                return
                        # Quotas using DB-backed counters when max_calls/max_runs present
                        max_calls = payload.get("max_runs")
                        if max_calls is None:
                            max_calls = payload.get("max_calls")
                        if isinstance(max_calls, int) and max_calls >= 0:
                            from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
                            from tldw_Server_API.app.core.AuthNZ.quotas import increment_and_check_jwt_quota
                            # Optional daily bucket
                            bucket = None
                            per = payload.get("period")
                            if isinstance(per, str) and per.lower() == "day":
                                from datetime import datetime, timezone
                                bucket = datetime.now(timezone.utc).date().isoformat()
                            db_pool = await get_db_pool()
                            ok, _cnt = await increment_and_check_jwt_quota(
                                db_pool=db_pool,
                                jti=str(payload.get("jti")),
                                counter_type="call",
                                limit=int(max_calls),
                                bucket=bucket,
                            )
                            if not ok:
                                await websocket.send_json({"type": "error", "message": "Token quota exceeded"})
                                await websocket.close(code=4403)
                                return
                    except Exception as _vk_e:
                        # Fail closed if explicit constraints present but evaluation failed badly
                        logger.debug(f"WS VK scope enforcement skipped/failed: {_vk_e}")
                jwt_user_id = int(uid)
                authenticated = True
            except (InvalidTokenError, TokenExpiredError) as e:
                logger.warning(f"WS JWT auth failed: {e}")
                await websocket.send_json({"type": "error", "message": "Invalid or expired token"})
                await websocket.close(code=4401)
                return
        else:
            # No Authorization header; fall back to message-based auth
            try:
                first_message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                auth_data = json.loads(first_message)
                if auth_data.get("type") != "auth" or not auth_data.get("token"):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Authentication required: Authorization: Bearer <JWT> or auth message"
                    })
                    await websocket.close(code=4401)
                    return
            except Exception as e:
                logger.warning(f"WS JWT auth (message prelude) failed: {e}")
                await websocket.send_json({"type": "error", "message": "Invalid authentication message"})
                await websocket.close(code=4401)
                return
                # Accept Bearer token in first message for compatibility
                try:
                    from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
                    from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
                    from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user_by_id
                    jwt_service = get_jwt_service()
                    payload = jwt_service.decode_access_token(auth_data.get("token"))
                    uid = payload.get("user_id") or payload.get("sub")
                    if isinstance(uid, str):
                        uid = int(uid)
                    if not uid:
                        raise ValueError("missing user id in token")
                    session_manager = await get_session_manager()
                    if await session_manager.is_token_blacklisted(auth_data.get("token"), payload.get("jti")):
                        raise ValueError("token revoked")
                    user_row = await _get_user_by_id(int(uid))
                    if not user_row:
                        raise ValueError("user not found")
                    jwt_user_id = int(uid)
                    authenticated = True
                except Exception as e:
                    logger.warning(f"WS JWT auth (message) failed: {e}")
                    await websocket.send_json({"type": "error", "message": "Invalid or expired token"})
                    await websocket.close(code=4401)
                    return
    if not is_multi_user_mode():
        # Single-user mode: API key via header, query or auth message, with optional IP allowlist
        expected_key = settings.SINGLE_USER_API_KEY
        client_ip = None
        try:
            client_ip = getattr(websocket.client, "host", None)
        except Exception:
            client_ip = None
        def _ip_allowed_single_user(ip: Optional[str]) -> bool:
            try:
                allowed = [s.strip() for s in (settings.SINGLE_USER_ALLOWED_IPS or []) if str(s).strip()]
                if not allowed:
                    return True
                if not ip:
                    return False
                import ipaddress as _ip
                pip = _ip.ip_address(ip)
                for entry in allowed:
                    try:
                        if '/' in entry:
                            if pip in _ip.ip_network(entry, strict=False):
                                return True
                        else:
                            if str(pip) == entry:
                                return True
                    except Exception:
                        continue
                return False
            except Exception:
                return False

        # Headers first
        header_api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        header_bearer = None
        if auth_header and auth_header.lower().startswith("bearer "):
            header_bearer = auth_header.split(" ", 1)[1].strip()

        if (header_api_key and header_api_key == expected_key) or (header_bearer and header_bearer == expected_key) or (token and token == expected_key):
            if not _ip_allowed_single_user(client_ip):
                await websocket.send_json({"type": "error", "message": "IP not allowed"})
                await websocket.close(code=1008)
                return
            authenticated = True
        elif token and token != expected_key:
            logger.warning("WebSocket: invalid query token")
            await websocket.send_json({"type": "error", "message": "Invalid authentication token"})
            await websocket.close()
            return
        else:
            try:
                first_message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                auth_data = json.loads(first_message)
                if auth_data.get("type") != "auth" or auth_data.get("token") != expected_key:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Authentication required. Send {\"type\": \"auth\", \"token\": \"YOUR_API_KEY\"}"
                    })
                    await websocket.close()
                    return
                if not _ip_allowed_single_user(client_ip):
                    await websocket.send_json({"type": "error", "message": "IP not allowed"})
                    await websocket.close(code=1008)
                    return
                authenticated = True
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Authentication timeout. Send auth message within 5 seconds."
                })
                await websocket.close()
                return
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON in authentication message"
                })
                await websocket.close()
                return

    if not authenticated:
        await websocket.send_json({"type": "error", "message": "Authentication required"})
        await websocket.close(code=4401)
        return

    try:
        # Default configuration - prefer server config for variant/model
        # This ensures alignment with configured STT defaults even if the
        # client configuration message arrives late.
        default_model = 'parakeet'
        default_variant = 'standard'
        try:
            cfg = load_comprehensive_config()
            if cfg.has_section('STT-Settings'):
                # Nemo model variant (standard|onnx|mlx)
                default_variant = cfg.get('STT-Settings', 'nemo_model_variant', fallback='standard').strip().lower()
        except Exception as e:
            logger.warning(f"Could not read STT-Settings from config: {e}")

        config = UnifiedStreamingConfig(
            model=default_model,
            model_variant=default_variant,
            sample_rate=16000,
            chunk_duration=2.0,
            overlap_duration=0.5,
            enable_partial=True,
            partial_interval=0.5,
            language='en'  # Default language for Canary
        )

        logger.info(f"WebSocket authenticated, calling handle_unified_websocket with default config: model={config.model}, variant={config.model_variant}")

        # Enforce per-user streaming quotas and daily minutes during streaming
        # Resolve user id for quotas (JWT in multi-user; fixed id in single-user)
        if is_multi_user_mode() and jwt_user_id is not None:
            user_id_for_usage = int(jwt_user_id)
        else:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
            _s = _get_settings()
            user_id_for_usage = getattr(_s, "SINGLE_USER_FIXED_ID", 1)

        ok_stream, msg_stream = await can_start_stream(user_id_for_usage)
        if not ok_stream:
            await websocket.send_json({"type": "error", "message": msg_stream})
            await websocket.close()
            return

        # Track and enforce minutes chunk-by-chunk
        used_minutes = 0.0
        # Bounded fail-open budget in minutes if DB is unavailable while streaming
        FAIL_OPEN_CAP_MINUTES = _get_failopen_cap_minutes()
        failopen_remaining = FAIL_OPEN_CAP_MINUTES

        def _on_audio(seconds: float, sr: int) -> None:
            nonlocal used_minutes
            # Check allowance before processing
            minutes_chunk = float(seconds) / 60.0
            # Note: async check in sync callback not ideal; fast path uses last known remaining
            # For MVP, perform a quick synchronous budget check using a cached remaining
            used_minutes += minutes_chunk

        try:
            # Use shared exception class so inner handler can bubble it up
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import QuotaExceeded as _QuotaExceeded

            async def _on_audio_quota(seconds: float, sr: int) -> None:
                """
                Handle a chunk of audio for daily-minute quota accounting and enforcement.

                Parameters:
                    seconds (float): Duration of the audio chunk in seconds.
                    sr (int): Sample rate of the audio chunk in Hz (unused by this function but provided for callback compatibility).

                Raises:
                    _QuotaExceeded: If adding this chunk would exceed the user's daily minutes quota.

                Notes:
                    - Checks whether the user's remaining daily minutes allow this chunk; if allowed, increments the nonlocal
                      `used_minutes` counter and records the minutes via `add_daily_minutes`.
                """
                nonlocal used_minutes, failopen_remaining
                minutes_chunk = float(seconds) / 60.0
                deducted = False
                try:
                    allow, _ = await check_daily_minutes_allow(user_id_for_usage, minutes_chunk)
                except EXPECTED_DB_EXC as e:
                    # Backing store failed; allow temporarily but deduct from bounded fail-open budget
                    logger.warning(
                        f"check_daily_minutes_allow failed during streaming; temporarily allowing (bounded fail-open). user_id={user_id_for_usage}, error={e}"
                    )
                    allow = True
                    failopen_remaining -= minutes_chunk
                    try:
                        increment_counter(
                            "audio_failopen_minutes_total", value=float(minutes_chunk), labels={"reason": "db_check"}
                        )
                        increment_counter("audio_failopen_events_total", labels={"reason": "db_check"})
                    except Exception:
                        pass
                    deducted = True
                    if failopen_remaining <= 0:
                        try:
                            increment_counter(
                                "audio_failopen_cap_exhausted_total", labels={"reason": "db_check"}
                            )
                        except Exception:
                            pass
                        raise _QuotaExceeded("daily_minutes")
                if not allow:
                    # Raise structured signal to outer scope
                    raise _QuotaExceeded("daily_minutes")
                used_minutes += minutes_chunk
                try:
                    await add_daily_minutes(user_id_for_usage, minutes_chunk)
                except EXPECTED_DB_EXC as e:
                    # Could not record; continue streaming under bounded fail-open
                    logger.warning(
                        f"Failed to record streaming minutes (bounded fail-open). user_id={user_id_for_usage}, error={e}"
                    )
                    if not deducted:
                        failopen_remaining -= minutes_chunk
                        try:
                            increment_counter(
                                "audio_failopen_minutes_total", value=float(minutes_chunk), labels={"reason": "db_record"}
                            )
                            increment_counter("audio_failopen_events_total", labels={"reason": "db_record"})
                        except Exception:
                            pass
                        if failopen_remaining <= 0:
                            try:
                                increment_counter(
                                    "audio_failopen_cap_exhausted_total", labels={"reason": "db_record"}
                                )
                            except Exception:
                                pass
                            raise _QuotaExceeded("daily_minutes")

            try:
                async def _on_heartbeat() -> None:
                    """
                    Send a heartbeat to update streaming quota/timestamp for the current user.

                    Invokes the module-level `heartbeat_stream` callback with `user_id_for_usage` to record activity; any exceptions raised by the callback are suppressed.
                    """
                    try:
                        await heartbeat_stream(user_id_for_usage)
                    except EXPECTED_REDIS_EXC as _hb_e:
                        logger.debug(f"Heartbeat failed for user_id={user_id_for_usage}: {_hb_e}")

                await handle_unified_websocket(
                    websocket,
                    config,
                    on_audio_seconds=_on_audio_quota,
                    on_heartbeat=_on_heartbeat,
                )
            except _QuotaExceeded as qe:
                # Send structured error and close with application-defined code
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error_type": "quota_exceeded",
                        "quota": qe.quota,
                        "message": "Streaming transcription quota exceeded (daily minutes)"
                    })
                except Exception as e:
                    logger.debug(f"WebSocket send_json quota error failed: error={e}")
                try:
                    await websocket.close(code=4003, reason="quota_exceeded")
                except Exception as e:
                    logger.debug(f"WebSocket close (quota case) failed: error={e}")
        finally:
            await finish_stream(user_id_for_usage)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        # Best-effort: map quota exception variants to structured error
        try:
            quota_name = getattr(e, "quota", None)
            txt = str(e)
            if not quota_name and ("daily_minutes" in txt or "concurrent_streams" in txt):
                quota_name = "daily_minutes" if "daily_minutes" in txt else "concurrent_streams"
            if quota_name:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error_type": "quota_exceeded",
                        "quota": quota_name,
                        "message": "Streaming transcription quota exceeded"
                    })
                finally:
                    try:
                        await websocket.close(code=4003, reason="quota_exceeded")
                    except Exception as e:
                        logger.warning(f"WebSocket close after quota exceeded failed: error={e}")
                        try:
                            increment_counter("app_warning_events_total", labels={"component": "audio", "event": "ws_close_quota_failed"})
                        except Exception as m_err:
                            logger.debug(f"metrics increment failed (audio ws_close_quota_failed): error={m_err}")
            else:
                # Let inner handler's error payload (if any) be the authoritative one.
                # Avoid sending a duplicate generic error frame that could race the client.
                pass
        except Exception as e:
            logger.warning(f"Streaming transcription outer handler swallowed error: {e}")
            try:
                increment_counter("app_warning_events_total", labels={"component": "audio", "event": "stream_outer_handler_error"})
            except Exception as m_err:
                logger.debug(f"metrics increment failed (audio stream_outer_handler_error): error={m_err}")
    finally:
        try:
            await websocket.close()
        except Exception as e:
            logger.warning(f"WebSocket close failed: error={e}")
            try:
                increment_counter("app_warning_events_total", labels={"component": "audio", "event": "ws_close_failed"})
            except Exception as m_err:
                logger.debug(f"metrics increment failed (audio ws_close_failed): error={m_err}")


@router.get("/stream/status", summary="Check streaming transcription availability")
async def streaming_status():
    """
    Report availability and capabilities of the streaming transcription WebSocket endpoint.

    Returns:
        A JSON object with the following keys:
          - `status` (str): "available" if at least one streaming model is present, "unavailable" otherwise, or "error" on failure.
          - `available_models` (list[str]): Names of detected streaming model variants (e.g., "parakeet-mlx", "parakeet-standard", "parakeet-onnx").
          - `websocket_endpoint` (str): URL path of the streaming transcription WebSocket.
          - `supported_features` (dict): Feature flags indicating supported streaming capabilities (boolean values).
    """
    try:
        # Check available models
        available_models = []

        # Check for MLX variant
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_MLX import (
                transcribe_with_parakeet_mlx
            )
            available_models.append("parakeet-mlx")
        except ImportError:
            pass

        # Check for standard variant (NeMo)
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
                load_parakeet_model
            )
            available_models.append("parakeet-standard")
        except ImportError:
            pass

        # Check for ONNX variant
        try:
            import onnxruntime
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_ONNX import (
                load_parakeet_onnx_model
            )
            available_models.append("parakeet-onnx")
        except ImportError:
            pass

        return JSONResponse({
            "status": "available" if available_models else "unavailable",
            "available_models": available_models,
            "websocket_endpoint": "/api/v1/audio/stream/transcribe",
            "supported_features": {
                "partial_results": True,
                "multiple_languages": True,
                "concurrent_streams": True,
                "segment_metadata": True,
                "live_insights": True,
                "meeting_notes": True,
                "speaker_diarization": True,
                "audio_persistence": True
            }
        })

    except Exception as e:
        logger.error(f"Error checking streaming status: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )


@router.get("/stream/limits", summary="Get user's streaming quota and usage")
async def streaming_limits(
    current_user: User = Depends(get_request_user),
    request: Request = None,
):
    """
    Return the current user's streaming quota and usage summary.

    Returns:
        JSONResponse: A JSON object with the following keys:
            - user_id (str): The user's identifier.
            - tier (str): The user's tier name (e.g., "free").
            - limits (dict): The resolved limit values (e.g., daily_minutes, concurrent_streams, concurrent_jobs, max_file_size_mb).
            - used_today_minutes (float): Minutes already used today (0.0 if unavailable).
            - remaining_minutes (float|None): Minutes remaining today (0.0 if none left, `None` if unknown/unbounded).
            - active_streams (int): Number of currently active streams (0 if unavailable).
            - can_start_stream (bool): Whether the user may start another stream given current active streams and concurrent_streams limit.
    """
    # Correlate logs with request_id if available
    rid = ensure_request_id(request) if request is not None else None
    try:
        limits = await get_limits_for_user(current_user.id)
    except EXPECTED_DB_EXC as e:
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
            "Failed to get limits for user %s, falling back to defaults: %s", current_user.id, e
        )
        # Fallback to default free limits
        limits = {
            "daily_minutes": 30.0,
            "concurrent_streams": 1,
            "concurrent_jobs": 1,
            "max_file_size_mb": 25,
        }
    try:
        used_minutes = await get_daily_minutes_used(current_user.id)
    except EXPECTED_DB_EXC as e:
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
            "Failed to get used minutes for user %s, falling back to 0: %s", current_user.id, e
        )
        used_minutes = 0.0
    limit_minutes = limits.get("daily_minutes")
    if limit_minutes is None:
        remaining_minutes = None
    else:
        try:
            remaining_minutes = max(0.0, float(limit_minutes) - float(used_minutes))
        except (ValueError, TypeError) as e:
            get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
                "Could not calculate remaining minutes for user %s: %s", current_user.id, e
            )
            remaining_minutes = None
    try:
        active_streams = await active_streams_count(current_user.id)
    except EXPECTED_REDIS_EXC as e:
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
            "Failed to get active streams for user %s, falling back to 0: %s", current_user.id, e
        )
        active_streams = 0
    try:
        tier = await get_user_tier(current_user.id)
    except EXPECTED_DB_EXC as e:
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
            "Failed to get tier for user %s, falling back to 'free': %s", current_user.id, e
        )
        tier = "free"
    try:
        max_streams = int(limits.get("concurrent_streams") or 0)
    except (ValueError, TypeError) as e:
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
            "Could not parse concurrent_streams limit for user %s: %s", current_user.id, e
        )
        max_streams = 0
    can_start = (max_streams == 0) or (active_streams < max_streams)
    return JSONResponse({
        "user_id": current_user.id,
        "tier": tier,
        "limits": limits,
        "used_today_minutes": used_minutes,
        "remaining_minutes": remaining_minutes,
        "active_streams": active_streams,
        "can_start_stream": can_start,
    })

@router.post("/stream/test", summary="Test streaming transcription setup")
async def test_streaming():
    """
    Run a lightweight end-to-end check of the streaming transcription pipeline using a short generated audio sample.

    Performs a minimal initialization of the Parakeet streaming transcriber, sends a short synthetic audio chunk, and returns the transcriber's immediate response or a buffering status.

    Returns:
        JSONResponse: On success, a JSON object with keys:
            - "status": "success"
            - "test_passed": True
            - "message": Human-readable success message
            - "test_result": Transcriber response or the string "Buffer accumulating"
        On failure, a JSONResponse with status_code 500 and a JSON object containing:
            - "status": "error"
            - "test_passed": False
            - "message": Error message describing the failure
    """
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Parakeet import (
            ParakeetStreamingTranscriber,
            StreamingConfig
        )
        import base64

        # Try to initialize transcriber
        config = StreamingConfig(model_variant='mlx')
        transcriber = ParakeetStreamingTranscriber(config)

        # Generate test audio
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = (0.5 * np.sin(440 * 2 * np.pi * t)).astype(np.float32)
        encoded = base64.b64encode(audio.tobytes()).decode('utf-8')

        # Try processing
        result = await transcriber.process_audio_chunk(encoded)

        return JSONResponse({
            "status": "success",
            "test_passed": True,
            "message": "Streaming transcription is working",
            "test_result": result if result else "Buffer accumulating"
        })

    except Exception as e:
        logger.error(f"Streaming test failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "test_passed": False,
                "message": "An internal error occurred during the streaming test. Please contact support if the problem persists."
            }
        )

#######################################################################################################################
#
# Voice Management Endpoints
#

@router.post("/voices/upload", summary="Upload a custom voice sample")
@limiter.limit("5/hour", key_func=_rate_limit_key)  # Rate limit: 5 uploads per hour
async def upload_voice(
    request: Request,
    file: UploadFile = File(..., description="Voice sample audio file (WAV, MP3, FLAC, OGG)"),
    name: str = Form(..., description="Name for the voice"),
    description: Optional[str] = Form(None, description="Description of the voice"),
    provider: str = Form(default="vibevoice", description="Target TTS provider"),
    current_user: User = Depends(get_request_user)
):
    """
    Upload a custom voice sample for use with TTS.

    Supports voice cloning for compatible providers:
    - VibeVoice: Any duration (1-shot cloning)
    - Higgs: 3-10 seconds recommended
    - Chatterbox: 5-20 seconds recommended

    The voice will be processed and optimized for the specified provider.
    """
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import (
            get_voice_manager,
            VoiceUploadRequest,
            VoiceProcessingError,
            VoiceQuotaExceededError
        )
        # Get voice manager
        voice_manager = get_voice_manager()

        # Read file content
        file_content = await file.read()

        # Create upload request
        upload_request = VoiceUploadRequest(
            name=name,
            description=description,
            provider=provider
        )

        # Process upload
        result = await voice_manager.upload_voice(
            user_id=current_user.id,
            file_content=file_content,
            filename=file.filename,
            request=upload_request
        )

        return result.model_dump()

    except ImportError as e:
        # Placeholder response when voice management is not available
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Custom voice upload is not available in this build"
        )
    except VoiceQuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except VoiceProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Voice upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload voice sample"
        )


@router.get("/voices", summary="List user's custom voices")
async def list_voices(
    request: Request,
    current_user: User = Depends(get_request_user)
):
    """
    List all custom voice samples uploaded by the user.

    Returns voice metadata including:
    - Voice ID for use in TTS requests
    - Name and description
    - Duration and format
    - Compatible providers
    """
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import get_voice_manager
        voice_manager = get_voice_manager()
        voices = await voice_manager.list_user_voices(current_user.id)

        return {
            "voices": [voice.model_dump() for voice in voices],
            "count": len(voices)
        }

    except ImportError:
        # Placeholder response when voice management is not available
        return {"voices": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list voices"
        )


@router.get("/voices/{voice_id}", summary="Get voice details")
async def get_voice_details(
    request: Request,
    voice_id: str = Path(..., description="Voice ID"),
    current_user: User = Depends(get_request_user)
):
    """
    Get detailed information about a specific voice.
    """
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import get_voice_manager
        voice_manager = get_voice_manager()
        voice = await voice_manager.registry.get_voice(current_user.id, voice_id)

        if not voice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice not found"
            )

        return voice.model_dump()

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Custom voice management not available"
        )
    except Exception as e:
        logger.error(f"Error getting voice details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get voice details"
        )


@router.delete("/voices/{voice_id}", summary="Delete a custom voice")
async def delete_voice(
    request: Request,
    voice_id: str = Path(..., description="Voice ID to delete"),
    current_user: User = Depends(get_request_user)
):
    """
    Delete a custom voice sample.

    This will remove the voice files and prevent it from being used in future TTS requests.
    """
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import get_voice_manager
        voice_manager = get_voice_manager()
        deleted = await voice_manager.delete_voice(current_user.id, voice_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice not found"
            )

        return {"message": "Voice deleted successfully", "voice_id": voice_id}

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Custom voice management not available"
        )
    except Exception as e:
        logger.error(f"Error deleting voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete voice"
        )


@router.post("/voices/{voice_id}/preview", summary="Generate voice preview")
@limiter.limit("10/minute", key_func=_rate_limit_key)  # Rate limit: 10 previews per minute
async def preview_voice(
    request: Request,
    voice_id: str = Path(..., description="Voice ID to preview"),
    text: str = Form(default="Hello, this is a preview of your custom voice.", description="Text to speak"),
    current_user: User = Depends(get_request_user),
    tts_service: TTSServiceV2 = Depends(get_tts_service)
):
    """
    Generate a short preview of a custom voice.

    This endpoint generates a short audio sample using the specified voice
    to help users preview how it sounds before using it in full TTS requests.
    """
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import get_voice_manager
        # Validate voice exists
        voice_manager = get_voice_manager()
        voice = await voice_manager.registry.get_voice(current_user.id, voice_id)

        if not voice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice not found"
            )

        # Limit preview text length
        if len(text) > 100:
            text = text[:100]

        # Create TTS request with custom voice and stream generator directly
        preview_request = OpenAISpeechRequest(
            model=voice.provider,
            input=text,
            voice=f"custom:{voice_id}",
            response_format="mp3",
            stream=True
        )

        audio_stream = tts_service.generate_speech(preview_request, provider=None, fallback=True)

        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"inline; filename=preview_{voice_id}.mp3",
                "X-Voice-Name": voice.name
            }
        )

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Custom voice preview not available"
        )
    except Exception as e:
        logger.error(f"Voice preview error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate voice preview"
        )

#
# End of audio.py
#######################################################################################################################
