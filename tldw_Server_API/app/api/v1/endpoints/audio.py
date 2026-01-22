# audio.py
# Description: This file contains the API endpoints for audio processing.
#
# Imports
import asyncio
import json
import os
import tempfile
import io
import base64
import time
import configparser
from types import SimpleNamespace
from functools import lru_cache
from pathlib import Path as PathLib
import sqlite3  # for DB-specific exception handling in limits endpoints
from typing import AsyncGenerator, Optional, Dict, Any, List, Callable, Awaitable
import numpy as np
import soundfile as sf

#
# Third-party libraries
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Header,
    File,
    Form,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    Path,
    Query,
)
from fastapi.responses import StreamingResponse, Response, JSONResponse
from starlette import status  # For status codes
from loguru import logger

#
# Local imports
from tldw_Server_API.app.api.v1.schemas.audio_schemas import (
    OpenAISpeechRequest,
    OpenAITranscriptionRequest,
    OpenAITranscriptionResponse,
    OpenAITranslationRequest,
    VoiceEncodeRequest,
    VoiceEncodeResponse,
    TranscriptSegmentationRequest,
    TranscriptSegmentationResponse,
    SpeechChatRequest,
    SpeechChatResponse,
)
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import get_api_keys, DEFAULT_LLM_PROVIDER
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.byok_runtime import (
    record_byok_missing_credentials,
    resolve_byok_credentials,
)
from tldw_Server_API.app.core.config import AUTH_BEARER_PREFIX
from tldw_Server_API.app.core.config import load_comprehensive_config

# Auth utils no longer used here; authentication is enforced via get_request_user dependency

# For WebSocket streaming transcription
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
    handle_unified_websocket,
    UnifiedStreamingConfig,
    UnifiedStreamingTranscriber,
    SileroTurnDetector,
    QuotaExceeded,
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
        heartbeat_jobs as heartbeat_jobs,
        active_streams_count as active_streams_count,
        get_daily_minutes_used as get_daily_minutes_used,
        get_user_tier as get_user_tier,
        get_job_heartbeat_interval_seconds as get_job_heartbeat_interval_seconds,
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


def _get_chat_history_max_messages() -> int:
    """
    Resolve the maximum number of chat history messages to retain
    for streaming audio chat sessions.

    Uses AUDIO_CHAT_HISTORY_MAX_MESSAGES env var when set, falling
    back to a sensible default of 40.
    """
    raw = os.getenv("AUDIO_CHAT_HISTORY_MAX_MESSAGES", "").strip()
    if not raw:
        return 40
    try:
        value = int(raw)
        return value if value > 0 else 40
    except (ValueError, TypeError) as e:
        logger.debug(f"AUDIO_CHAT_HISTORY_MAX_MESSAGES parse failed: {e}")
        return 40


CHAT_HISTORY_MAX_MESSAGES: int = _get_chat_history_max_messages()


def _debug_error_details_enabled() -> bool:
    """Return True when DEBUG_ERROR_DETAILS enables verbose error payloads."""
    return str(os.getenv("DEBUG_ERROR_DETAILS", "")).strip().lower() in {"1", "true", "yes", "on"}


def _maybe_debug_details(exc: Optional[Exception]) -> Optional[str]:
    """Return exception details when DEBUG_ERROR_DETAILS is enabled, else None."""
    if exc is None or not _debug_error_details_enabled():
        return None
    try:
        return str(exc)
    except Exception:
        return "Unprintable error"


def _http_error_detail(message: str, request_id: Optional[str], exc: Optional[Exception] = None) -> Dict[str, Any]:
    """Build an HTTP error payload with optional request_id and debug details."""
    payload: Dict[str, Any] = {"message": message}
    if request_id:
        payload["request_id"] = request_id
    details = _maybe_debug_details(exc)
    if details:
        payload["details"] = details
    return payload


def _ws_error_payload(
    message: str,
    *,
    request_id: Optional[str] = None,
    exc: Optional[Exception] = None,
    error_type: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a WebSocket error payload with optional debug details and extra fields."""
    payload: Dict[str, Any] = {"type": "error", "message": message}
    if error_type:
        payload["error_type"] = error_type
    if request_id:
        payload["request_id"] = request_id
    details = _maybe_debug_details(exc)
    if details:
        payload["details"] = details
    if extra:
        reserved = {"type", "message", "error_type", "request_id", "details"}
        payload.update({key: value for key, value in extra.items() if key not in reserved})
    return payload


async def _stream_tts_to_websocket(
    *,
    websocket: WebSocket,
    speech_req: OpenAISpeechRequest,
    tts_service: Any,
    provider: Optional[str],
    outer_stream: Optional[Any],
    reg: Any,
    route: str,
    component_label: str,
    voice_to_voice_start: Optional[float] = None,
    error_handler: Optional[Callable[[Exception], Awaitable[None]]] = None,
) -> None:
    """
    Shared helper to stream TTS audio chunks over a WebSocket with backpressure and metrics.

    This consolidates the producer/consumer queue pattern used by both the
    audio.chat.stream and audio.stream.tts WebSocket handlers.
    """
    queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=8)
    provider_label = (provider or getattr(speech_req, "model", None) or "default").lower()
    underrun_labels = {"provider": provider_label}
    error_labels = {"component": component_label, "provider": provider_label}

    async def _producer() -> None:
        try:
            generate_kwargs: Dict[str, Any] = {
                "provider": provider,
                "fallback": True,
                "voice_to_voice_route": route,
            }
            if voice_to_voice_start is not None:
                generate_kwargs["voice_to_voice_start"] = voice_to_voice_start

            async for chunk in tts_service.generate_speech(
                speech_req,
                **generate_kwargs,
            ):
                if not chunk:
                    continue
                try:
                    queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    try:
                        _ = queue.get_nowait()
                    except Exception as q_err:
                        logger.debug(f"{route} queue get_nowait failed: error={q_err}")
                    try:
                        queue.put_nowait(chunk)
                        reg.increment("audio_stream_underruns_total", 1, labels=underrun_labels)
                    except Exception as m_err:
                        logger.debug(f"{route} underrun metrics update failed: error={m_err}")
                        reg.increment("audio_stream_errors_total", 1, labels=error_labels)
        except Exception as exc:
            try:
                reg.increment("audio_stream_errors_total", 1, labels=error_labels)
            except Exception as m_err:
                logger.debug(f"{route} producer metrics update failed (outer): error={m_err}")
            if error_handler is not None:
                try:
                    await error_handler(exc)
                except Exception as send_exc:
                    logger.debug(f"{route} error handler failed: error={send_exc}")
        finally:
            try:
                await queue.put(None)
            except Exception as q_err:
                logger.debug(f"{route} queue sentinel enqueue failed: error={q_err}")

    async def _consumer() -> None:
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                try:
                    await websocket.send_bytes(item)
                    if outer_stream:
                        outer_stream.mark_activity()
                except Exception as exc:
                    try:
                        reg.increment("audio_stream_errors_total", 1, labels=error_labels)
                    except Exception as m_err:
                        logger.debug(f"{route} consumer metrics update failed: error={m_err}")
                    try:
                        await websocket.close(code=1011)
                    except Exception as close_exc:
                        logger.debug(f"{route} websocket close in consumer failed: error={close_exc}")
                    if error_handler is not None:
                        try:
                            await error_handler(exc)
                        except Exception as send_exc:
                            logger.debug(f"{route} consumer error handler failed: error={send_exc}")
                    break
        except Exception:
            try:
                reg.increment("audio_stream_errors_total", 1, labels=error_labels)
            except Exception as m_err:
                logger.debug(f"{route} consumer metrics update failed (outer): error={m_err}")

    producer_task = asyncio.create_task(_producer())
    consumer_task = asyncio.create_task(_consumer())

    try:
        _done, pending = await asyncio.wait(
            {producer_task, consumer_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except Exception as wait_exc:
                logger.debug(f"{route} wait for pending task failed after cancel: error={wait_exc}")
    finally:
        producer_task.cancel()
        consumer_task.cancel()

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
from tldw_Server_API.app.core.Chat.chat_service import (
    perform_chat_api_call_async as chat_api_call_async,
)
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.LLM_Calls.adapter_utils import (
    ensure_app_config,
    normalize_provider,
    resolve_provider_api_key_from_config,
)
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    get_usage_event_logger,
    UsageEventLogger,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, require_token_scope
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, get_ps_logger
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import (
    get_chacha_db_for_user,
)
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.Streaming import speech_chat_service

router = APIRouter(
    tags=["Audio"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limit exceeded"},
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


def _infer_tts_provider_from_model(model: Optional[str]) -> Optional[str]:
    """Best-effort mapping from model id to provider key for sanitization."""
    if not model:
        return None
    m = str(model).strip().lower()
    if m in {"tts-1", "tts-1-hd"}:
        return "openai"
    if m.startswith("kokoro"):
        return "kokoro"
    if m.startswith("higgs"):
        return "higgs"
    if m.startswith("dia"):
        return "dia"
    if m.startswith("chatterbox"):
        return "chatterbox"
    if m.startswith("vibevoice"):
        return "vibevoice"
    if m.startswith("neutts"):
        return "neutts"
    if m.startswith("eleven"):
        return "elevenlabs"
    if m.startswith("index_tts") or m.startswith("indextts"):
        return "index_tts"
    if m.startswith("supertonic2") or m.startswith("supertonic-2") or m.startswith("tts-supertonic2"):
        return "supertonic2"
    if m.startswith("supertonic") or m.startswith("tts-supertonic"):
        return "supertonic"
    return None


@lru_cache(maxsize=1)
def _valid_whisper_model_sizes() -> set[str]:
    """Cached lookup of known faster-whisper model sizes."""
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (  # type: ignore
            WhisperModel as _WhisperModel,
        )

        return set(getattr(_WhisperModel, "valid_model_sizes", []))
    except Exception:
        # If the import fails (e.g., dependencies missing), fall back to empty set
        return set()


def _map_openai_audio_model_to_whisper(model: Optional[str]) -> str:
    """Map OpenAI-style audio model ids to a faster-whisper model name.

    - Known internal faster-whisper model ids (e.g., 'large-v3', 'distil-large-v3')
      and Hugging Face ids are passed through unchanged.
    - OpenAI aliases such as 'whisper-1' map to a configurable default
      (currently 'large-v3' to preserve prior behavior).
    - All unknown values fall back to 'large-v3'.
    """
    default_model = "large-v3"
    if not model:
        return default_model

    raw = str(model).strip()
    m = raw.lower()

    valid_sizes = _valid_whisper_model_sizes()
    valid_sizes_lower = {s.lower() for s in valid_sizes}
    if not valid_sizes_lower:
        valid_sizes_lower = {
            "tiny",
            "tiny.en",
            "base",
            "base.en",
            "small",
            "small.en",
            "medium",
            "medium.en",
            "large-v1",
            "large-v2",
            "large-v3",
            "large",
        }

    # Pass through known internal sizes and HF ids
    if raw in valid_sizes or m in valid_sizes or "/" in raw:
        return raw

    # OpenAI-compatible aliases
    if m == "whisper-1":
        return default_model
    if m in {"whisper-large-v3-turbo", "whisper-large-v3-turbo-ct2", "large-v3-turbo"}:
        return "deepdml/faster-whisper-large-v3-turbo-ct2"
    if m.startswith("whisper-") and m.endswith("-ct2"):
        ct2_tail = m[len("whisper-"):-4]
        if ct2_tail in valid_sizes_lower:
            return ct2_tail

    # Fallback to default
    return default_model


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
from tldw_Server_API.app.core.TTS.tts_config import get_tts_config
from uuid import uuid4


async def get_tts_service() -> TTSServiceV2:
    """Get the V2 TTS service instance."""
    return await get_tts_service_v2()

def _raise_for_tts_error(exc: Exception, request_id: Optional[str]) -> None:
    if isinstance(exc, TTSValidationError):
        logger.warning(f"TTS validation error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_http_error_detail("TTS validation failed", request_id, exc=exc),
        )
    if isinstance(exc, TTSProviderNotConfiguredError):
        logger.error(f"TTS provider not configured: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_http_error_detail("TTS service unavailable", request_id, exc=exc),
        )
    if isinstance(exc, TTSAuthenticationError):
        logger.error(f"TTS authentication error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_http_error_detail("TTS provider authentication failed", request_id, exc=exc),
        )
    if isinstance(exc, TTSRateLimitError):
        logger.warning(f"TTS rate limit exceeded: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_http_error_detail(
                "TTS provider rate limit exceeded. Please try again later.", request_id, exc=exc
            ),
        )
    if isinstance(exc, TTSQuotaExceededError):
        logger.warning(f"TTS quota exceeded: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=_http_error_detail("TTS quota exceeded. Please review your plan or quota.", request_id, exc=exc),
        )
    if isinstance(exc, TTSError):
        logger.error(f"TTS error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_http_error_detail("TTS generation failed", request_id, exc=exc),
        )
    logger.error(f"Unexpected error during audio generation: {exc}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=_http_error_detail("An unexpected error occurred during audio generation", request_id, exc=exc),
    )


def _sanitize_speech_request(
    request_data: OpenAISpeechRequest,
    *,
    request_id: Optional[str],
) -> Optional[str]:
    """Validate and sanitize input text, returning provider hint."""
    try:
        tts_config = get_tts_config()
        validator = TTSInputValidator({"strict_validation": tts_config.strict_validation})

        provider_hint = _infer_tts_provider_from_model(getattr(request_data, "model", None))
        sanitized_text = validator.sanitize_text(request_data.input, provider=provider_hint)
        if not sanitized_text or len(sanitized_text.strip()) == 0:
            raise TTSValidationError(
                "Input text cannot be empty after sanitization",
                details={"original_length": len(request_data.input)},
            )
        request_data.input = sanitized_text
        return provider_hint
    except TTSValidationError as exc:
        logger.warning(f"TTS validation error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_http_error_detail("TTS validation failed", request_id, exc=exc),
        ) from exc


def _tts_fallback_resolver(name: str) -> Optional[str]:
    try:
        cfg = get_tts_config()
        provider_cfg = getattr(cfg, "providers", {}).get(name)
        api_key = getattr(provider_cfg, "api_key", None) if provider_cfg else None
        return api_key or None
    except (AttributeError, KeyError, TypeError) as exc:
        logger.debug(f"TTS fallback resolver failed for provider '{name}': {exc}")
        return None


async def _resolve_tts_byok(
    *,
    provider_hint: Optional[str],
    current_user: User,
    request: Request,
) -> tuple[Optional[int], Optional[Dict[str, Any]], Optional[Any]]:
    user_id_int: Optional[int] = None
    try:
        user_id_int = getattr(current_user, "id_int", None)
        if user_id_int is None:
            raw_id = getattr(current_user, "id", None)
            if raw_id is not None:
                user_id_int = int(raw_id)
    except (AttributeError, TypeError, ValueError) as exc:
        logger.debug(f"Failed to extract user_id from current_user: {exc}")
        user_id_int = None

    tts_overrides: Optional[Dict[str, Any]] = None
    byok_tts_resolution = None
    if provider_hint:
        byok_tts_resolution = await resolve_byok_credentials(
            provider_hint,
            user_id=user_id_int,
            request=request,
            fallback_resolver=_tts_fallback_resolver,
        )
        if byok_tts_resolution.uses_byok:
            tts_overrides = {"api_key": byok_tts_resolution.api_key}
            base_url = byok_tts_resolution.credential_fields.get("base_url")
            if isinstance(base_url, str) and base_url.strip():
                tts_overrides["base_url"] = base_url.strip()
        elif not byok_tts_resolution.api_key:
            if provider_hint in {"openai", "elevenlabs"}:
                record_byok_missing_credentials(provider_hint, operation="audio_tts")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error_code": "missing_provider_credentials",
                        "message": f"TTS provider '{provider_hint}' requires an API key.",
                    },
                )

    return user_id_int, tts_overrides, byok_tts_resolution


# --- End of Placeholder ---


@router.post(
    "/speech",
    summary="Generates audio from text input.",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_token_scope("any", require_if_present=True, endpoint_id="audio.speech", count_as="call")),
    ],
    responses={
        200: {
            "headers": {
                "X-TTS-Alignment": {
                    "description": "Base64url-encoded JSON alignment payload when available (non-streaming).",
                    "schema": {"type": "string"},
                },
                "X-TTS-Alignment-Format": {
                    "description": "Alignment header encoding format (currently json+base64).",
                    "schema": {"type": "string"},
                },
            }
        }
    },
)
async def create_speech(
    request_data: OpenAISpeechRequest,  # FastAPI will parse JSON body into this
    request: Request,  # Required for rate limiter and to check for client disconnects
    tts_service: TTSServiceV2 = Depends(get_tts_service),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Generates audio from the input text.

    Requires authentication via Bearer token in Authorization header.
    Rate limited to 10 requests per minute per IP address.

    Input is sanitized by `TTSInputValidator`, which normalizes Unicode,
    strips HTML, and removes or rejects potentially dangerous patterns
    (e.g., obvious SQL/command/FS injection attempts). In strict mode
    (the default), such patterns result in HTTP 400 errors; in relaxed
    mode (`strict_validation` set to false via TTS config), dangerous
    substrings are stripped and the request is processed if non-empty.

    Docs: `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md`,
    `Docs/STT-TTS/TTS-SETUP-GUIDE.md` (sanitization and error semantics).

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

    request_id = ensure_request_id(request)

    provider_hint = _sanitize_speech_request(request_data, request_id=request_id)

    tts_provider_hint = provider_hint
    user_id_int, tts_overrides, byok_tts_resolution = await _resolve_tts_byok(
        provider_hint=tts_provider_hint,
        current_user=current_user,
        request=request,
    )
    logger.info(
        f"Received speech request: model={request_data.model}, voice={request_data.voice}, format={request_data.response_format}, request_id={request_id}"
    )
    voice_to_voice_start: Optional[float] = None
    try:
        raw_v2v = request.headers.get("x-voice-to-voice-start") or request.headers.get("X-Voice-To-Voice-Start")
    except Exception:
        raw_v2v = None
    if raw_v2v:
        try:
            ts = float(raw_v2v)
            if ts > 0:
                voice_to_voice_start = ts
        except (TypeError, ValueError):
            logger.debug(f"Invalid X-Voice-To-Voice-Start header: {raw_v2v}")
    try:
        state_ts = getattr(request.state, "voice_to_voice_start", None)
        if voice_to_voice_start is None and isinstance(state_ts, (int, float)):
            voice_to_voice_start = float(state_ts)
    except Exception as exc:
        logger.debug(f"Failed to read voice_to_voice_start from request.state: {exc}")
    try:
        usage_log.log_event(
            "audio.tts",
            tags=[str(request_data.model or ""), str(request_data.voice or "")],
            metadata={"stream": bool(getattr(request_data, "stream", False)), "format": request_data.response_format},
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
        "pcm": "audio/L16; rate=24000; channels=1",  # Example for raw PCM
    }
    content_type = content_type_map.get(request_data.response_format)
    if not content_type:
        logger.warning(f"Unsupported response format: {request_data.response_format}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported response_format: {request_data.response_format}. Supported formats are: {', '.join(content_type_map.keys())}",
        )

    try:
        speech_iter = tts_service.generate_speech(
            request_data,
            provider=tts_provider_hint,
            fallback=True,
            provider_overrides=tts_overrides,
            voice_to_voice_start=voice_to_voice_start,
            voice_to_voice_route="audio.speech",
            user_id=user_id_int,
        )
    except Exception as exc:
        _raise_for_tts_error(exc, request_id)

    async def _pull_first_chunk() -> bytes:
        try:
            return await speech_iter.__anext__()
        except StopAsyncIteration:
            return b""
        except HTTPException:
            raise
        except Exception as exc:
            _raise_for_tts_error(exc, request_id)

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
            _raise_for_tts_error(exc, request_id)
        finally:
            if byok_tts_resolution is not None:
                try:
                    await byok_tts_resolution.touch_last_used()
                except Exception as exc:
                    logger.debug(f"Failed to update BYOK last_used timestamp: {exc}")

    if request_data.stream:
        first_chunk = await _pull_first_chunk()
        if not first_chunk:
            logger.error("Streaming generation resulted in empty audio data.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audio generation failed to produce data.",
            )
        return StreamingResponse(
            _stream_chunks(first_chunk),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename=speech.{request_data.response_format}",
                "X-Accel-Buffering": "no",  # Useful for Nginx
                "Cache-Control": "no-cache",
                "X-Request-Id": request_id,
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
        _raise_for_tts_error(exc, request_id)

    # Drop any internal boundary markers if present
    all_audio_bytes = all_audio_bytes.replace(b"--final_boundary_for_non_streamed--", b"")

    if not all_audio_bytes:
        logger.error("Non-streaming generation resulted in empty audio data.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Audio generation failed to produce data."
        )

    if byok_tts_resolution is not None:
        try:
            await byok_tts_resolution.touch_last_used()
        except Exception as exc:
            logger.debug(f"Failed to update BYOK last_used timestamp: {exc}")

    headers = {
        "Content-Disposition": f"attachment; filename=speech.{request_data.response_format}",
        "Cache-Control": "no-cache",
        "X-Request-Id": request_id,
    }
    try:
        metadata = getattr(request_data, "_tts_metadata", None)
        if isinstance(metadata, dict):
            alignment_payload = metadata.get("alignment")
        else:
            alignment_payload = None
    except Exception:
        alignment_payload = None
    if alignment_payload:
        try:
            alignment_json = json.dumps(alignment_payload, separators=(",", ":"), ensure_ascii=True)
            alignment_b64 = base64.urlsafe_b64encode(alignment_json.encode("utf-8")).decode("ascii")
            headers["X-TTS-Alignment"] = alignment_b64
            headers["X-TTS-Alignment-Format"] = "json+base64"
        except Exception as exc:
            logger.debug(f"Failed to encode alignment metadata header: {exc}")

    return Response(
        content=all_audio_bytes,
        media_type=content_type,
        headers=headers,
    )


@router.post(
    "/speech/metadata",
    summary="Returns alignment metadata for a TTS request.",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_token_scope("any", require_if_present=True, endpoint_id="audio.speech", count_as="call")),
    ],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "alignment": {
                            "engine": "kokoro",
                            "sample_rate": 24000,
                            "words": [
                                {"word": "Hello", "start_ms": 0, "end_ms": 400},
                                {"word": "world", "start_ms": 450, "end_ms": 900},
                            ],
                        }
                    }
                }
            }
        },
        204: {"description": "No alignment metadata available for this request."},
    },
)
async def create_speech_metadata(
    request_data: OpenAISpeechRequest,
    request: Request,
    tts_service: TTSServiceV2 = Depends(get_tts_service),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    request_id = ensure_request_id(request)
    provider_hint = _sanitize_speech_request(request_data, request_id=request_id)
    tts_provider_hint = provider_hint
    user_id_int, tts_overrides, byok_tts_resolution = await _resolve_tts_byok(
        provider_hint=tts_provider_hint,
        current_user=current_user,
        request=request,
    )

    try:
        usage_log.log_event(
            "audio.tts.metadata",
            tags=[str(request_data.model or ""), str(request_data.voice or "")],
            metadata={"stream": bool(getattr(request_data, "stream", False)), "format": request_data.response_format},
        )
    except Exception as exc:
        logger.debug(f"usage_log audio.tts.metadata failed: error={exc}")

    try:
        request_data.stream = False
    except Exception:
        pass

    try:
        speech_iter = tts_service.generate_speech(
            request_data,
            provider=tts_provider_hint,
            fallback=True,
            provider_overrides=tts_overrides,
            voice_to_voice_route="audio.speech.metadata",
            user_id=user_id_int,
        )
    except Exception as exc:
        _raise_for_tts_error(exc, request_id)

    try:
        async for _ in speech_iter:
            pass
    except Exception as exc:
        _raise_for_tts_error(exc, request_id)
    finally:
        if byok_tts_resolution is not None:
            try:
                await byok_tts_resolution.touch_last_used()
            except Exception as exc:
                logger.debug(f"Failed to update BYOK last_used timestamp: {exc}")

    metadata = getattr(request_data, "_tts_metadata", None)
    alignment_payload = None
    if isinstance(metadata, dict):
        alignment_payload = metadata.get("alignment")
    if not alignment_payload:
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"X-Request-Id": request_id})
    return JSONResponse(content={"alignment": alignment_payload}, headers={"X-Request-Id": request_id})


@router.post(
    "/transcriptions",
    summary="Transcribes audio into text (OpenAI Compatible)",
    dependencies=[
        Depends(check_rate_limit),
        Depends(
            require_token_scope("any", require_if_present=True, endpoint_id="audio.transcriptions", count_as="call")
        )
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
    response_format: str = Form(default="json", description="Format of the transcript output"),
    temperature: float = Form(default=0.0, ge=0.0, le=1.0, description="Sampling temperature"),
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

    Compatible with OpenAI's Audio API transcription endpoint.
    Supports multiple transcription models including Whisper, Parakeet, and Canary.

    Models:
    - whisper-1: Uses faster-whisper (default when config uses Whisper)
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
            interval = get_job_heartbeat_interval_seconds()
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
                    await heartbeat_jobs(user_id)
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
            detail=f"File size exceeds maximum of {int(max_file_size/1024/1024)}MB",
        )

    # Resolve default model from config when omitted.
    if not (model or "").strip():
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
            resolve_default_transcription_model,
        )

        model = resolve_default_transcription_model("whisper-1")

    # Before any heavy work, enforce concurrent jobs cap per user
    ok_job, msg_job = await can_start_job(current_user.id)
    if not ok_job:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg_job)
    try:
        job_heartbeat_task = await _maybe_start_job_heartbeat(current_user.id)
    except Exception:
        job_heartbeat_task = None

    # Record job start (best-effort)
    acquired_job_slot = False
    try:
        await increment_jobs_started(current_user.id)
        acquired_job_slot = True
    except EXPECTED_DB_EXC as e:
        logger.exception(f"Failed to increment jobs started: user_id={current_user.id}, error={e}; request_id={rid}")

    # Save uploaded file to temporary location and proceed with processing
    temp_audio_path = None
    canonical_path = None
    try:
        # Create temporary file with proper extension
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".wav"
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
            tmp_file.write(contents)
            temp_audio_path = tmp_file.name

        # Convert to canonical 16k mono WAV for consistent processing; base_dir constrains output location.
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
                convert_to_wav as _convert_to_wav,
                ConversionError,
            )
        except ImportError as e:
            logger.debug(f"convert_to_wav import failed; using original temp file: path={temp_audio_path}, error={e}")
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
                logger.debug(f"convert_to_wav failed; using original temp file: path={temp_audio_path}, error={e}")
                canonical_path = temp_audio_path

        if os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
            source_label = "converted" if canonical_path != temp_audio_path else "original"
            logger.debug(f"TEST_MODE: canonical audio path resolved: path={canonical_path}, source={source_label}")

        # Always recalculate base_dir from the path we'll actually use
        base_dir = PathLib(canonical_path).parent

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
                    granularity_tokens = {t.strip().lower() for t in s.split(",") if t.strip()}
        except Exception as e:
            # Non-fatal: default to {'segment'}
            logger.debug(f"Failed to parse timestamp_granularities; defaulting to 'segment': error={e}")
            granularity_tokens = {"segment"}
        if not granularity_tokens:
            granularity_tokens = {"segment"}

        # Normalize task for Whisper providers; other providers treat this as a no-op.
        task_normalized = (task or "transcribe").strip().lower()
        if task_normalized not in {"transcribe", "translate"}:
            task_normalized = "transcribe"

        # Determine provider from requested model name.
        # We reuse the core STT parser so that HTTP models like
        # "parakeet-mlx", "parakeet-onnx", "qwen2audio-*" route
        # consistently with the transcription library.
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
            transcribe_audio,
            speech_to_text as fw_speech_to_text,
            strip_whisper_metadata_header,
            is_transcription_error_message as _is_transcription_error_message,
            validate_whisper_model_identifier,
        )
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import (
            Audio_Files as audio_files,
        )

        # Use the shared STT provider registry so that REST STT and other
        # subsystems resolve providers/models consistently.
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
            # Mark slot as released so the outer finally does not double-release
            acquired_job_slot = False
            # Ensure any heartbeat loop is cancelled on early quota denial
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
        segments_for_timing: Optional[List[Dict[str, Any]]] = None
        whisper_model_name = _map_openai_audio_model_to_whisper(model)
        if provider == "faster-whisper":
            try:
                whisper_model_name = validate_whisper_model_identifier(whisper_model_name)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_http_error_detail("Invalid transcription model identifier", rid, exc=exc),
                ) from exc
        # Wrap the heavy work to ensure we always release the job slot
        try:
            if provider == "faster-whisper":
                # Preflight check for Whisper model readiness. When the
                # underlying faster-whisper model is not yet available
                # locally, surface a structured 503 instead of returning a
                # pseudo-transcript so HTTP clients do not persist "[MODEL STATUS]"
                # text as real content. The inner finally below will still
                # release the job slot.
                try:
                    model_status = audio_files.check_transcription_model_status(whisper_model_name)
                    if not model_status.get("available", False):
                        detail_payload: Dict[str, Any] = {
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
                    # Preserve the structured 503 (or any other HTTPException) path.
                    raise
                except Exception as preflight_exc:  # pragma: no cover - defensive
                    # If the preflight check itself fails, log and continue with
                    # normal transcription behavior rather than failing the call.
                    logger.debug(f"Whisper model preflight check failed; proceeding without it: {preflight_exc}")
                # For Whisper, support word-level timestamps, language detection,
                # and optional translate task.
                try:
                    # Determine how we pass language into STT:
                    #  - transcribe: honor explicit language when provided
                    #  - translate: let the backend auto-detect source language
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
                # Non-Whisper providers: delegate to adapter which wraps the
                # existing Parakeet/Canary/Qwen2Audio/external implementations.
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
                        base_dir=base_dir,
                    )
                    detected_language = artifact.get("language")
                    segments_for_timing = artifact.get("segments") or []
                    transcribed_text = artifact.get("text", "")
                except Exception as e:
                    logger.error(
                        f"Transcription failed for provider={provider}, model={model_for_provider}: {e}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=(
                            f"Transcription failed for provider '{provider}' "
                            f"and model '{model_for_provider}'"
                        ),
                    ) from e
        finally:
            # Make sure we always release job slot on any path
            try:
                if job_heartbeat_task:
                    job_heartbeat_task.cancel()
                    try:
                        await job_heartbeat_task
                    except asyncio.CancelledError:
                        pass
                if acquired_job_slot:
                    await finish_job(current_user.id)
            except EXPECTED_DB_EXC as e:
                logger.exception(
                    f"Failed to release job slot in finally: user_id={current_user.id}, error={e}; request_id={rid}"
                )

        # Check for errors in transcription
        _raise_on_transcription_error(transcribed_text)

        # Apply custom vocabulary post-replacements (all providers)
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary import (
                postprocess_text_if_enabled as _cv_post,
            )

            transcribed_text = _cv_post(transcribed_text)
        except Exception as exc:
            logger.debug(f"Custom vocabulary postprocessing failed; continuing without it: {exc}")

        # On success, record minutes used
        try:
            await add_daily_minutes(current_user.id, minutes_est)
        except EXPECTED_DB_EXC as e:
            logger.exception(f"Failed to record daily minutes: user_id={current_user.id}, error={e}; request_id={rid}")

        # Format response based on requested format
        if response_format == "text":
            return Response(content=transcribed_text, media_type="text/plain")

        elif response_format == "srt":
            _raise_on_transcription_error(transcribed_text)
            # Prefer real segment timings for Whisper; otherwise fall back to a
            # simple single-chunk SRT block.
            if provider == "faster-whisper" and segments_for_timing:
                lines: List[str] = []

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
                # Simple SRT format fallback when timing information is unavailable
                srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{transcribed_text}\n"
            return Response(content=srt_content, media_type="text/plain")

        elif response_format == "vtt":
            _raise_on_transcription_error(transcribed_text)
            # Prefer real segment timings for Whisper; otherwise use a simple
            # single-chunk VTT block.
            if provider == "faster-whisper" and segments_for_timing:
                lines_vtt: List[str] = ["WEBVTT", ""]

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
                # Simple VTT fallback when timing information is unavailable
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

            # Segments (prefer real segments when available, especially for Whisper)
            if "segment" in granularity_tokens:
                if provider == "faster-whisper" and segments_for_timing:
                    segs = []
                    for i, seg in enumerate(segments_for_timing):
                        if not isinstance(seg, dict):
                            continue
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
                    response_data["segments"] = [
                        {
                            "id": 0,
                            "seek": 0,
                            "start": 0.0,
                            "end": duration,
                            "text": transcribed_text,
                        }
                    ]

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
        # Clean up temporary file
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
    if not (model or "").strip():
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
            resolve_default_transcription_model,
        )

        model = resolve_default_transcription_model("whisper-1")

    try:
        usage_log.log_event(
            "audio.transcriptions",
            tags=[str(model or "")],
            metadata={"filename": getattr(file, "filename", None), "language": "en"},
        )
    except Exception as e:
        logger.debug(f"usage_log audio.transcriptions failed: error={e}")
    # For translation, we'll use the transcription endpoint with language detection
    # and then translate if needed (simplified implementation)
    # In a full implementation, you would use a translation model

    # Call transcription in translate mode. For Whisper providers this uses
    # the "translate" task (source-language auto-detect, English output).
    # For non-Whisper providers, the task hint is ignored and a normal
    # transcription is performed.
    return await create_transcription(
        request=request,
        file=file,
        model=model,
        language=None,  # Allow backend to auto-detect source language
        prompt=prompt,
        response_format=response_format,
        temperature=temperature,
        task="translate",
        timestamp_granularities="segment",
        current_user=current_user,
    )


@router.post(
    "/chat",
    response_model=SpeechChatResponse,
    summary="Non-streaming Speech-to-Speech chat (STT → LLM → TTS)",
    dependencies=[
        Depends(
            require_token_scope(
                "any",
                require_if_present=True,
                endpoint_id="audio.chat",
                count_as="call",
            )
        )
    ],
)
async def audio_chat_turn(
    request_data: SpeechChatRequest,
    request: Request,
    tts_service: TTSServiceV2 = Depends(get_tts_service),
    current_user: User = Depends(get_request_user),
    chat_db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
) -> SpeechChatResponse:
    """
    Execute a single non-streaming speech chat turn:

      - Accept base64-encoded user audio.
      - Run STT to obtain a transcript.
      - Call the LLM with recent conversation history.
      - Persist user/assistant messages into ChaChaNotes.
      - Run TTS on the assistant reply and return base64-encoded audio.

    This endpoint focuses on the v1 non-streaming path; streaming speech chat
    is handled by a separate WebSocket endpoint in v2.
    """
    rid = ensure_request_id(request)
    try:
        usage_log.log_event(
            "audio.chat",
            tags=[str(getattr(current_user, "id", ""))],
            metadata={
                "session_id": request_data.session_id or "",
                "input_audio_format": request_data.input_audio_format,
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"usage_log audio.chat failed: error={e}; request_id={rid}")

    acquired_stream = False
    user_id_for_usage = int(getattr(current_user, "id", 0) or 0)
    try:
        # Per-user concurrent chat guard (reuses audio stream limits)
        can_start, reason = await can_start_stream(user_id_for_usage)
        if not can_start:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=reason or "Concurrent audio chat limit reached",
            )

        acquired_stream = True

        try:
            return await speech_chat_service.run_speech_chat_turn(
                request_data=request_data,
                request=request,
                current_user=current_user,
                chat_db=chat_db,
                tts_service=tts_service,
            )
        finally:
            if acquired_stream:
                try:
                    await finish_stream(user_id_for_usage)
                except Exception as e:
                    logger.debug(f"finish_stream failed (audio chat): {e}")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Speech chat turn failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech chat pipeline failed",
        ) from e


# Add other OpenAI compatible endpoints like /models, /voices later
# For now, this is the core.


@router.post("/segment/transcript", summary="Segment a transcript into coherent blocks (TreeSeg)")
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
            "MIN_IMPROVEMENT_RATIO": getattr(req, "min_improvement_ratio", 0.0),
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcript segmentation failed")


@router.get("/health")
async def get_tts_health(request: Request, tts_service: TTSServiceV2 = Depends(get_tts_service)):
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
                "details": status.get("providers", {}),
            },
            "circuit_breakers": status.get("circuit_breakers", {}),
            "capabilities": capabilities,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add Kokoro adapter details if available
        try:
            from tldw_Server_API.app.core.TTS.adapter_registry import get_tts_factory, TTSProvider

            factory = await get_tts_factory()
            adapter = await factory.registry.get_adapter(TTSProvider.KOKORO)
            if adapter:
                backend = "onnx" if getattr(adapter, "use_onnx", True) else "pytorch"
                kokoro_info = {
                    "backend": backend,
                    "device": str(getattr(adapter, "device", "unknown")),
                    "model_path": getattr(adapter, "model_path", None),
                    "voices_json": getattr(adapter, "voices_json", None),
                }
                # Espeak library hint for phonemizer-backed flows
                try:
                    es_env = os.getenv("PHONEMIZER_ESPEAK_LIBRARY")
                    kokoro_info["espeak_lib_env"] = es_env
                    if es_env:
                        kokoro_info["espeak_lib_exists"] = bool(os.path.exists(es_env))
                    else:
                        kokoro_info["espeak_lib_exists"] = False
                except Exception as exc:
                    logger.debug(f"Kokoro health: espeak library introspection failed: {exc}")
                health["providers"]["kokoro"] = kokoro_info
        except Exception as e:
            logger.debug(f"Kokoro health enrichment failed: {e}")

        return health
    except Exception as e:
        logger.error(f"Error getting TTS health: {e}", exc_info=True)
        request_id = ensure_request_id(request)
        payload = _http_error_detail("TTS health check failed", request_id, exc=e)
        return {"status": "error", **payload, "timestamp": datetime.utcnow().isoformat()}


@router.get("/transcriptions/health", summary="Check STT transcription model health")
async def get_stt_health(
    request: Request,
    model: Optional[str] = Query(
        default=None,
        description=(
            "Transcription model to check (OpenAI-style id or internal STT model name). "
            "Defaults to the configured STT provider when omitted."
        ),
    ),
    warm: bool = Query(
        default=False,
        description="If true and the provider is Whisper, eagerly load the model to verify it can be initialized.",
    ),
):
    """
    Lightweight health/readiness endpoint for STT models.

    - Resolves the requested model to an internal STT provider and model id.
    - Uses `Audio_Files.check_transcription_model_status` to report availability
      and estimated download size.
    - When `warm=true` and the provider is Whisper, attempts to initialize the
      faster-whisper model via `get_whisper_model` so operators can exercise
      the cache and surface initialization errors before production traffic.
    """
    from datetime import datetime
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files as audio_files
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as stt_lib

    request_id = ensure_request_id(request)
    raw_model = (model or "").strip()
    if not raw_model:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
            resolve_default_transcription_model,
        )

        raw_model = resolve_default_transcription_model("whisper-1")
    # Determine provider using the same parser as the main STT pipeline.
    provider_raw, _, _ = stt_lib.parse_transcription_model(raw_model)

    # For Whisper providers, map OpenAI-style ids (e.g. "whisper-1") to an
    # internal faster-whisper model name so health checks align with /transcriptions.
    if provider_raw == "whisper":
        resolved_model = _map_openai_audio_model_to_whisper(raw_model)
        try:
            resolved_model = stt_lib.validate_whisper_model_identifier(resolved_model)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_http_error_detail("Invalid transcription model identifier", request_id, exc=exc),
            ) from exc
    else:
        resolved_model = raw_model

    # Base status from cached/downloaded model presence.
    try:
        status_info = audio_files.check_transcription_model_status(resolved_model)
    except Exception:
        logger.exception("STT health: check_transcription_model_status failed")
        status_info = {
            "available": False,
            "message": "Failed to check model status.",
            "model": resolved_model,
        }

    health: Dict[str, Any] = {
        "provider": provider_raw,
        "alias": raw_model,
        "model": status_info.get("model", resolved_model),
        "available": bool(status_info.get("available", False)),
        "message": status_info.get("message"),
        "estimated_size": status_info.get("estimated_size"),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Optional warmup: try to instantiate the Whisper model to ensure the
    # configured device/compute_type settings are compatible with this runtime.
    warm_info: Dict[str, Any] = {}
    if warm and provider_raw == "whisper":
        device = getattr(stt_lib, "processing_choice", "cpu")
        try:
            stt_lib.get_whisper_model(resolved_model, device, check_download_status=False)
            warm_info = {"ok": True, "device": device}
        except Exception:
            logger.exception(f"STT health warm-up failed for model={resolved_model}, device={device}")
            warm_info = {
                "ok": False,
                "device": device,
                "error": "Model initialization failed.",
            }

    if warm_info:
        health["warm"] = warm_info

    return health


@router.get("/providers")
async def list_tts_providers(request: Request, tts_service: TTSServiceV2 = Depends(get_tts_service)):
    """
    List all available TTS providers and their capabilities.
    """
    from datetime import datetime

    try:
        capabilities = await tts_service.get_capabilities()
        voices = await tts_service.list_voices()

        return {"providers": capabilities, "voices": voices, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error listing TTS providers: {e}", exc_info=True)
        request_id = ensure_request_id(request)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_http_error_detail("Failed to list providers", request_id, exc=e),
        ) from e


@router.get("/voices/catalog", summary="List available TTS voices across providers")
async def list_tts_voices(
    request: Request,
    provider: Optional[str] = Query(None, description="Optional provider filter, e.g., 'elevenlabs' or 'openai'"),
    tts_service: TTSServiceV2 = Depends(get_tts_service),
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
        logger.error(f"Error listing TTS voices: {e}", exc_info=True)
        request_id = ensure_request_id(request)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_http_error_detail("Failed to list voices", request_id, exc=e),
        ) from e


@router.post("/reset-metrics")
async def reset_tts_metrics(
    request: Request,
    provider: Optional[str] = None,
    tts_service: TTSServiceV2 = Depends(get_tts_service),
):
    """
    Reset TTS metrics.

    Args:
        provider: Optional provider name to reset metrics for. If not provided, resets all metrics.
    """
    try:
        if hasattr(tts_service, "metrics"):
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
        logger.error(f"Error resetting metrics: {e}", exc_info=True)
        request_id = ensure_request_id(request)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_http_error_detail("Failed to reset metrics", request_id, exc=e),
        )


######################################################################################################################
# WebSocket Router Creation
######################################################################################################################

# Create a separate router for WebSocket endpoints to avoid authentication conflicts
ws_router = APIRouter()


async def _audio_ws_authenticate(
    websocket: WebSocket,
    outer_stream: Optional[Any],
    *,
    endpoint_id: str,
    ws_path: str,
) -> tuple[bool, Optional[int]]:
    """
    Shared authentication helper for audio WebSocket endpoints.

    Returns (authenticated, user_id) where user_id is best-effort (JWT or API key owner).
    """
    jwt_user_id: Optional[int] = None

    def _policy_close_code() -> int:
        flag = str(os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    async def _stream_error(message: str, code: int = 4401) -> None:
        if outer_stream:
            try:
                await outer_stream.send_json({"type": "error", "message": message})
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to send websocket error payload: {exc}")
        try:
            await websocket.close(code=code)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to close websocket after auth error: {exc}")

    async def _enforce_jwt_limits(payload: dict[str, Any]) -> bool:
        """Enforce endpoint/path/quota limits for JWT-authenticated websocket sessions."""
        try:
            from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
            from tldw_Server_API.app.core.AuthNZ.quotas import increment_and_check_jwt_quota
        except Exception as exc:  # pragma: no cover - defensive import
            logger.warning(f"Failed to import JWT quota helpers: {exc}")
            return False

        if str(payload.get("role", "")).lower() != "admin":
            allowed_eps = payload.get("allowed_endpoints")
            if isinstance(allowed_eps, list) and allowed_eps:
                if endpoint_id not in [str(x) for x in allowed_eps]:
                    await _stream_error("Endpoint not permitted for token", code=4403)
                    return False
            ap = payload.get("allowed_paths")
            if isinstance(ap, list) and ap:
                if not any(str(ws_path).startswith(str(pfx)) for pfx in ap):
                    await _stream_error("Path not permitted for token", code=4403)
                    return False
            max_calls = payload.get("max_runs")
            if max_calls is None:
                max_calls = payload.get("max_calls")
            if isinstance(max_calls, int) and max_calls >= 0:
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
                    await _stream_error("Token quota exceeded", code=_policy_close_code())
                    return False
        return True

    async def _decode_and_validate_jwt_token(token: str) -> Optional[int]:
        """
        Decode a JWT, enforce blacklist + user existence + scope/quotas, and return the user id.

        Returns:
            int user id when valid; None when rejected (after emitting an error/close).
        """
        try:
            from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
            from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
            from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
            from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user_by_id

            jwt_service = get_jwt_service()
            payload = jwt_service.decode_access_token(token)
            uid = payload.get("user_id") or payload.get("sub")
            if isinstance(uid, str):
                uid = int(uid)
            if not uid:
                raise InvalidTokenError("missing user_id/sub claim")
            session_manager = await get_session_manager()
            if await session_manager.is_token_blacklisted(token, payload.get("jti")):
                raise InvalidTokenError("token revoked")
            user_row = await _get_user_by_id(int(uid))
            if not user_row:
                raise InvalidTokenError("user not found")
            if not await _enforce_jwt_limits(payload):
                return None
            return int(uid)
        except (InvalidTokenError, TokenExpiredError):
            await _stream_error("Invalid or expired token", code=4401)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"JWT authentication failed: {exc}")
            await _stream_error("Authentication failed", code=4401)
            return None

    if is_multi_user_mode():
        # Optional X-API-KEY path (virtual API keys)
        x_api_key = None
        try:
            x_api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to read X-API-KEY header: {exc}")
            x_api_key = None
        # Query-string token support (multi-user): allow `?token=` as an API key
        # source when no X-API-KEY header is present.
        if not x_api_key:
            try:
                query_token = websocket.query_params.get("token") if hasattr(websocket, "query_params") else None
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to read query token for API key auth: {exc}")
                query_token = None
            if query_token:
                x_api_key = query_token
        if x_api_key:
            try:
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
                from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
                from tldw_Server_API.app.core.AuthNZ.quotas import increment_and_check_api_key_quota

                api_mgr = await get_api_key_manager()
                client_ip = getattr(websocket.client, "host", None)
                info = await api_mgr.validate_api_key(api_key=x_api_key, ip_address=client_ip)
                if not info:
                    await _stream_error("Invalid API key", code=4401)
                    return False, None
                if str(info.get("scope", "")).lower() != "admin":
                    allowed_eps = info.get("llm_allowed_endpoints")
                    if isinstance(allowed_eps, str):
                        try:
                            allowed_eps = json.loads(allowed_eps)
                        except Exception:
                            allowed_eps = None
                    if isinstance(allowed_eps, list) and allowed_eps:
                        if endpoint_id not in [str(x) for x in allowed_eps]:
                            await _stream_error("Endpoint not permitted for API key", code=4403)
                            return False, None
                    meta = info.get("metadata")
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = None
                    if isinstance(meta, dict):
                        ap = meta.get("allowed_paths")
                        if isinstance(ap, list) and ap:
                            if not any(str(ws_path).startswith(str(pfx)) for pfx in ap):
                                await _stream_error("Path not permitted for API key", code=4403)
                                return False, None
                        quota = meta.get("max_runs")
                        if quota is None:
                            quota = meta.get("max_calls")
                        if isinstance(quota, int) and quota >= 0:
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
                                await _stream_error("API key quota exceeded", code=_policy_close_code())
                                return False, None
                uid = info.get("user_id")
                try:
                    jwt_user_id = int(uid) if uid is not None else None
                except Exception:
                    jwt_user_id = None
                return True, jwt_user_id
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"API key authentication failed: {exc}")
                await _stream_error("API key authentication failed", code=4401)
                return False, None

        # JWT path
        auth_header = websocket.headers.get("authorization")
        bearer = None
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                bearer = parts[1]
        if not bearer:
            # Fallback: support `?token=` as a JWT bearer source in multi-user mode.
            try:
                query_token = websocket.query_params.get("token") if hasattr(websocket, "query_params") else None
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to read query token for JWT auth: {exc}")
                query_token = None
            if query_token:
                bearer = query_token
        if bearer:
            try:
                user_id = await _decode_and_validate_jwt_token(bearer)
                if user_id is None:
                    return False, None
                jwt_user_id = user_id
                return True, jwt_user_id
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"JWT auth unexpected error: {exc}")
                return False, None

        # Message-based auth as a fallback
        try:
            first_message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            auth_data = json.loads(first_message)
            if auth_data.get("type") != "auth" or not auth_data.get("token"):
                await _stream_error("Authentication required: Authorization: Bearer <JWT> or auth message", code=4401)
                return False, None
            bearer = auth_data.get("token")
            user_id = await _decode_and_validate_jwt_token(bearer)
            if user_id is None:
                return False, None
            jwt_user_id = user_id
            return True, jwt_user_id
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Message-based auth failed: {exc}")
            await _stream_error("Authentication required", code=4401)
            return False, None

    # Single-user mode
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    expected_key = settings.SINGLE_USER_API_KEY
    client_ip = None
    try:
        client_ip = getattr(websocket.client, "host", None)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Failed to resolve client IP for single-user auth: {exc}")
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
                    if "/" in entry:
                        if pip in _ip.ip_network(entry, strict=False):
                            return True
                    else:
                        if str(pip) == entry:
                            return True
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"Failed to parse single-user allowed IP entry '{entry}': {exc}")
                    continue
            return False
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to evaluate single-user IP allowlist: {exc}")
            return False

    header_api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    header_bearer = None
    if auth_header and auth_header.lower().startswith("bearer "):
        header_bearer = auth_header.split(" ", 1)[1].strip()
    try:
        query_token = websocket.query_params.get("token") if hasattr(websocket, "query_params") else None
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Failed to read query token: {exc}")
        query_token = None

    if (
        (header_api_key and header_api_key == expected_key)
        or (header_bearer and header_bearer == expected_key)
        or query_token == expected_key
    ):
        if not _ip_allowed_single_user(client_ip):
            await _stream_error("IP not allowed", code=1008)
            return False, None
        return True, settings.SINGLE_USER_FIXED_ID if hasattr(settings, "SINGLE_USER_FIXED_ID") else None
    try:
        first_message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        auth_data = json.loads(first_message)
        if auth_data.get("type") != "auth" or auth_data.get("token") != expected_key:
            await _stream_error('Authentication required. Send {"type": "auth", "token": "YOUR_API_KEY"}')
            return False, None
        if not _ip_allowed_single_user(client_ip):
            await _stream_error("IP not allowed", code=1008)
            return False, None
        return True, settings.SINGLE_USER_FIXED_ID if hasattr(settings, "SINGLE_USER_FIXED_ID") else None
    except asyncio.TimeoutError:
        await _stream_error("Authentication timeout. Send auth message within 5 seconds.")
        return False, None
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Invalid authentication message for single-user API key: {exc}")
        await _stream_error("Invalid authentication message")
        return False, None


@ws_router.websocket("/stream/transcribe")
async def websocket_transcribe(
    websocket: WebSocket, token: Optional[str] = Query(None)  # Get token from query parameter
):
    """
    Handle a WebSocket connection to perform real-time streaming audio transcription.

    Accepts a WebSocket and an optional query token. Authentication is supported via:
    - Multi-user: X-API-KEY header, Authorization: Bearer <JWT>, `token` query parameter (API key or JWT), or an initial auth message.
    - Single-user: API key via header, `token` query parameter, or an initial auth message; an IP allowlist may be enforced.
    Supported incoming message types: "auth" (for token-based auth), "config" (streaming configuration), "audio" (base64-encoded audio chunks), and "commit" (finalize current utterance).
    Outgoing message types include partial updates ("partial"), interim/final transcriptions ("transcription"), the final transcript ("full_transcript"), and structured error frames ("error").
    Per-user limits are enforced (concurrent streams and daily minute quotas); when a quota is exceeded the server sends an "error" with "error_type": "quota_exceeded" and closes the connection with code 4003 (or 1008 when `AUDIO_WS_QUOTA_CLOSE_1008=1`).
    A server-side default streaming configuration is used if the client does not provide one before audio arrives.
    Parameters:
        websocket (WebSocket): The active WebSocket connection.
        token (Optional[str]): Optional API key or JWT token supplied via the query string for both multi-user and single-user authentication.
    """
    # Create a lightweight WebSocketStream for uniform metrics on outer error paths
    _outer_stream = None
    try:
        from tldw_Server_API.app.core.Streaming.streams import WebSocketStream as _WSStream

        _outer_stream = _WSStream(
            websocket,
            heartbeat_interval_s=0,
            idle_timeout_s=0,
            compat_error_type=True,
            labels={"component": "audio", "endpoint": "audio_unified_ws"},
        )
        await _outer_stream.start()
    except Exception:
        _outer_stream = None
    if _outer_stream is None:
        class _BareStream:
            def __init__(self, ws: WebSocket):
                self.ws = ws

            async def start(self) -> None:
                try:
                    already_accepted = False
                    try:
                        state = getattr(self.ws, "application_state", None)
                        if state is not None and str(state).upper().endswith("CONNECTED"):
                            already_accepted = True
                    except Exception:
                        already_accepted = False
                    if hasattr(self.ws, "accept") and not already_accepted:
                        await self.ws.accept()
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"_BareStream.start failed: {exc}")

            async def send_json(self, payload: Dict[str, Any]) -> None:
                try:
                    await self.ws.send_json(payload)
                except Exception as exc:
                    logger.debug(f"_BareStream.send_json failed: {exc}")

            async def error(self, code: str, message: str, *, data: Optional[Dict[str, Any]] = None) -> None:
                p = {"type": "error", "error_type": code, "message": message}
                if data is not None:
                    p["data"] = data
                await self.send_json(p)

            async def done(self) -> None:
                await self.send_json({"type": "done"})

            def mark_activity(self) -> None:
                return

            async def stop(self) -> None:
                return

        _outer_stream = _BareStream(websocket)

    # Correlate via request id (header or generated)
    try:
        _hdrs = websocket.headers or {}
        request_id = (
            _hdrs.get("x-request-id")
            or _hdrs.get("X-Request-Id")
            or (websocket.query_params.get("request_id") if hasattr(websocket, "query_params") else None)
            or str(uuid4())
        )
    except Exception:
        request_id = str(uuid4())
    try:
        logger.info(f"Audio WS connected: request_id={request_id}")
    except Exception as exc:
        logger.debug(f"Audio WS connection logging failed: {exc}")

    # Ops toggle for standardized close code on quota/rate limits (4003 → 1008)
    import os as _os

    def _policy_close_code() -> int:
        flag = str(_os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    # Authenticate (shared helper; parity with other audio WS endpoints)
    auth_ok, jwt_user_id = await _audio_ws_authenticate(
        websocket,
        _outer_stream,
        endpoint_id="audio.stream.transcribe",
        ws_path="/api/v1/audio/stream/transcribe",
    )
    if not auth_ok:
        return

    try:
        # Default configuration - prefer server config for variant/model
        # This ensures alignment with configured STT defaults even if the
        # client configuration message arrives late.
        default_model = "parakeet"
        default_variant = "standard"
        try:
            cfg = load_comprehensive_config()
            if cfg.has_section("STT-Settings"):
                # Nemo model variant (standard|onnx|mlx)
                default_variant = cfg.get("STT-Settings", "nemo_model_variant", fallback="standard").strip().lower()
        except Exception as e:
            logger.warning(f"Could not read STT-Settings from config: {e}")

        # If Nemo toolkit is unavailable in this environment, prefer Whisper
        # as the initial streaming model so we avoid repeated initialization
        # failures before falling back.
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (  # type: ignore
                is_nemo_available as _is_nemo_available,
            )

            nemo_ok = _is_nemo_available()
        except Exception:
            nemo_ok = False
        if not nemo_ok:
            default_model = "whisper"

        config = UnifiedStreamingConfig(
            model=default_model,
            model_variant=default_variant,
            sample_rate=16000,
            chunk_duration=2.0,
            overlap_duration=0.5,
            enable_partial=True,
            partial_interval=0.5,
            language="en",  # Default language for Canary
        )

        logger.info(
            f"WebSocket authenticated, calling handle_unified_websocket with default config: model={config.model}, variant={config.model_variant}"
        )

        # Enforce per-user streaming quotas and daily minutes during streaming
        # Resolve user id for quotas (JWT in multi-user; fixed id in single-user)
        if is_multi_user_mode() and jwt_user_id is not None:
            user_id_for_usage = int(jwt_user_id)
        else:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings

            _s = _get_settings()
            user_id_for_usage = getattr(_s, "SINGLE_USER_FIXED_ID", 1)

        acquired_stream = False

        ok_stream, msg_stream = await can_start_stream(user_id_for_usage)
        if not ok_stream:
            if _outer_stream:
                await _outer_stream.send_json({"type": "error", "message": msg_stream})
            await websocket.close()
            return
        acquired_stream = True

        # Resource Governor: acquire a 'streams' concurrency lease (policy resolved via route_map)
        # Track and enforce minutes chunk-by-chunk
        used_minutes = 0.0
        # Bounded fail-open budget in minutes if DB is unavailable while streaming
        FAIL_OPEN_CAP_MINUTES = _get_failopen_cap_minutes()
        failopen_remaining = FAIL_OPEN_CAP_MINUTES

        # Local snapshot of remaining minutes for this connection; when None,
        # the next chunk will trigger a DB refresh.
        remaining_minutes_snapshot: Optional[float] = None

        # Use shared exception class so inner handler can bubble it up
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
            QuotaExceeded as _QuotaExceeded,
        )

        async def _on_audio_quota(seconds: float, _sr: int) -> None:
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
            nonlocal used_minutes, failopen_remaining, remaining_minutes_snapshot
            minutes_chunk = float(seconds) / 60.0
            deducted = False
            allow = False
            # Fast-path local check: if we have a remaining snapshot and this
            # chunk would exceed it, raise immediately without a DB round-trip.
            if remaining_minutes_snapshot is not None and minutes_chunk > remaining_minutes_snapshot:
                raise _QuotaExceeded("daily_minutes")

            # Refresh remaining snapshot periodically by asking the DB for this
            # chunk; on success, we treat the returned "remaining_after" value
            # as the new snapshot.
            try:
                allow, remaining_after = await check_daily_minutes_allow(user_id_for_usage, minutes_chunk)
                if allow and remaining_after is not None:
                    remaining_minutes_snapshot = float(remaining_after)
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
                except Exception as m_err:
                    logger.debug(f"metrics increment failed (audio_failopen_db_check): error={m_err}")
                deducted = True
                if failopen_remaining <= 0:
                    try:
                        increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_check"})
                    except Exception as m_err:
                        logger.debug(f"metrics increment failed (audio_failopen_cap_db_check): error={m_err}")
                    raise _QuotaExceeded("daily_minutes") from None
            if not allow:
                # Raise structured signal to outer scope
                raise _QuotaExceeded("daily_minutes")
            used_minutes += minutes_chunk
            # Reduce the local snapshot so subsequent chunks can be checked
            # without hitting the DB until it is exhausted or refreshed on
            # the next successful check.
            if remaining_minutes_snapshot is not None:
                remaining_minutes_snapshot = max(0.0, remaining_minutes_snapshot - minutes_chunk)
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
                            "audio_failopen_minutes_total",
                            value=float(minutes_chunk),
                            labels={"reason": "db_record"},
                        )
                        increment_counter("audio_failopen_events_total", labels={"reason": "db_record"})
                    except Exception as m_err:
                        logger.debug(f"metrics increment failed (audio_failopen_db_record): error={m_err}")
                    if failopen_remaining <= 0:
                        try:
                            increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_record"})
                        except Exception as m_err:
                            logger.debug(f"metrics increment failed (audio_failopen_cap_db_record): error={m_err}")
                        raise _QuotaExceeded("daily_minutes") from None

        async def _on_heartbeat() -> None:
            """
            Send a heartbeat to update streaming quota/timestamp for the current user.

            Invokes the module-level `heartbeat_stream` callback with
            `user_id_for_usage` to record activity; any Redis-related
            exceptions are logged and suppressed.
            """
            try:
                await heartbeat_stream(user_id_for_usage)
            except EXPECTED_REDIS_EXC as _hb_e:
                logger.debug(f"Heartbeat failed for user_id={user_id_for_usage}: {_hb_e}")

        try:
            await handle_unified_websocket(
                websocket,
                config,
                on_audio_seconds=_on_audio_quota,
                on_heartbeat=_on_heartbeat,
            )
        except _QuotaExceeded as qe:
            try:
                if _outer_stream:
                    await _outer_stream.send_json(
                        {
                            "type": "error",
                            "error_type": "quota_exceeded",
                            "quota": qe.quota,
                            "message": "Streaming transcription quota exceeded (daily minutes)",
                        }
                    )
            except Exception as send_exc:
                logger.debug(f"WebSocket send_json quota error failed: error={send_exc}")
            try:
                await websocket.close(code=_policy_close_code(), reason="quota_exceeded")
            except Exception as close_exc:
                logger.debug(f"WebSocket close (quota case) failed: error={close_exc}")
        finally:
            if acquired_stream:
                try:
                    await finish_stream(user_id_for_usage)
                except EXPECTED_DB_EXC as e:
                    logger.debug(
                        f"Failed to release streaming quota slot (stream/transcribe): "
                        f"user_id={user_id_for_usage}, error={e}"
                    )

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
                    if _outer_stream:
                        await _outer_stream.send_json(
                            {
                                "type": "error",
                                "error_type": "quota_exceeded",
                                "quota": quota_name,
                                "message": "Streaming transcription quota exceeded",
                            }
                        )
                finally:
                    try:
                        await websocket.close(code=_policy_close_code(), reason="quota_exceeded")
                    except Exception as e:
                        logger.warning(f"WebSocket close after quota exceeded failed: error={e}")
                        try:
                            increment_counter(
                                "app_warning_events_total",
                                labels={"component": "audio", "event": "ws_close_quota_failed"},
                            )
                        except Exception as m_err:
                            logger.debug(f"metrics increment failed (audio ws_close_quota_failed): error={m_err}")
            else:
                # Let inner handler's error payload (if any) be the authoritative one.
                # Avoid sending a duplicate generic error frame that could race the client.
                pass
        except Exception as e:
            logger.warning(f"Streaming transcription outer handler swallowed error: {e}")
            try:
                increment_counter(
                    "app_warning_events_total", labels={"component": "audio", "event": "stream_outer_handler_error"}
                )
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


@ws_router.websocket("/chat/stream")
async def websocket_audio_chat_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(None),  # noqa: ARG001 - kept for parity with other WS endpoints
):
    """
    WebSocket v2 speech chat:
      - Partial STT with VAD auto-commit
      - Streaming LLM deltas
      - Streaming TTS audio back (binary frames)

    Authentication:
      - Multi-user: `X-API-KEY` header, `Authorization: Bearer <JWT>`, `token` query parameter (API key or JWT),
        or an initial auth message frame (JWT).
      - Single-user: API key via header, `token` query parameter, or an initial auth message; optional IP allowlist.
    """
    await websocket.accept()

    try:
        _raw_idle = os.getenv("AUDIO_WS_IDLE_TIMEOUT_S") or os.getenv("STREAM_IDLE_TIMEOUT_S")
        _idle_timeout = float(_raw_idle) if _raw_idle else None
    except Exception:
        _idle_timeout = None

    # Wrap websocket for consistent metrics/heartbeats; keep connection open across turns
    _outer_stream = None
    try:
        from tldw_Server_API.app.core.Streaming.streams import WebSocketStream as _WSStream

        _outer_stream = _WSStream(
            websocket,
            heartbeat_interval_s=None,
            compat_error_type=True,
            close_on_done=False,
            idle_timeout_s=_idle_timeout,
            labels={"component": "audio", "endpoint": "audio_chat_ws"},
        )
        await _outer_stream.start()
    except Exception:
        _outer_stream = None

    try:
        _hdrs = websocket.headers or {}
        request_id = (
            _hdrs.get("x-request-id")
            or _hdrs.get("X-Request-Id")
            or (websocket.query_params.get("request_id") if hasattr(websocket, "query_params") else None)
            or str(uuid4())
        )
    except Exception:
        request_id = str(uuid4())
    try:
        logger.info(f"Audio chat WS connected: request_id={request_id}")
    except Exception as exc:
        logger.debug(f"Audio chat WS connection logging failed: {exc}")

    reg = get_metrics_registry()

    def _policy_close_code() -> int:
        flag = str(os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    # Authenticate (parity with STT/WS TTS)
    auth_ok, jwt_user_id = await _audio_ws_authenticate(
        websocket,
        _outer_stream,
        endpoint_id="audio.chat.stream",
        ws_path="/api/v1/audio/chat/stream",
    )
    if not auth_ok:
        return

    # Determine quota user id
    if is_multi_user_mode() and jwt_user_id is not None:
        user_id_for_usage = int(jwt_user_id)
    else:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings

        _s = _get_settings()
        user_id_for_usage = getattr(_s, "SINGLE_USER_FIXED_ID", 1)

    acquired_stream = False

    try:
        # Concurrency guard
        try:
            ok_stream, msg_stream = await can_start_stream(user_id_for_usage)
            if not ok_stream:
                if _outer_stream:
                    await _outer_stream.send_json(
                        {
                            "type": "error",
                            "message": msg_stream or "Concurrent audio streams limit reached",
                            "error_type": "rate_limited",
                        }
                    )
                await websocket.close(code=_policy_close_code())
                return
            acquired_stream = True
        except Exception:
            if _outer_stream:
                await _outer_stream.send_json(
                    {
                        "type": "error",
                        "message": "Unable to evaluate audio stream quota or concurrency",
                        "error_type": "quota",
                    }
                )
            await websocket.close(code=_policy_close_code())
            return

        # Daily minute tracking (bounded fail-open like STT WS)
        used_minutes = 0.0
        FAIL_OPEN_CAP_MINUTES = _get_failopen_cap_minutes()
        failopen_remaining = FAIL_OPEN_CAP_MINUTES
        remaining_minutes_snapshot: Optional[float] = None

        async def _on_audio_quota(seconds: float, _sr: int) -> None:
            nonlocal used_minutes, failopen_remaining, remaining_minutes_snapshot
            minutes_chunk = float(seconds) / 60.0
            deducted = False
            allow = False

            if remaining_minutes_snapshot is not None and minutes_chunk > remaining_minutes_snapshot:
                raise QuotaExceeded("daily_minutes")

            try:
                allow, remaining_after = await check_daily_minutes_allow(user_id_for_usage, minutes_chunk)
                if allow and remaining_after is not None:
                    remaining_minutes_snapshot = float(remaining_after)
            except EXPECTED_DB_EXC as e:
                logger.warning(
                    f"check_daily_minutes_allow failed during streaming; temporarily allowing "
                    f"(bounded fail-open). user_id={user_id_for_usage}, error={e}"
                )
                allow = True
                failopen_remaining -= minutes_chunk
                try:
                    increment_counter(
                        "audio_failopen_minutes_total", value=float(minutes_chunk), labels={"reason": "db_check"}
                    )
                    increment_counter("audio_failopen_events_total", labels={"reason": "db_check"})
                except Exception as m_err:  # noqa: BLE001
                    logger.debug(f"metrics increment failed (audio_chat_failopen_db_check): error={m_err}")
                deducted = True
                if failopen_remaining <= 0:
                    try:
                        increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_check"})
                    except Exception as m_err:  # noqa: BLE001
                        logger.debug(
                            f"metrics increment failed (audio_chat_failopen_cap_db_check): error={m_err}"
                        )
                    raise QuotaExceeded("daily_minutes") from None

            if not allow:
                raise QuotaExceeded("daily_minutes") from None

            used_minutes += minutes_chunk
            if remaining_minutes_snapshot is not None:
                remaining_minutes_snapshot = max(0.0, remaining_minutes_snapshot - minutes_chunk)
            try:
                await add_daily_minutes(user_id_for_usage, minutes_chunk)
            except EXPECTED_DB_EXC as e:
                logger.warning(
                    f"Failed to record streaming minutes (bounded fail-open). user_id={user_id_for_usage}, error={e}"
                )
                if not deducted:
                    failopen_remaining -= minutes_chunk
                    try:
                        increment_counter(
                            "audio_failopen_minutes_total",
                            value=float(minutes_chunk),
                            labels={"reason": "db_record"},
                        )
                        increment_counter("audio_failopen_events_total", labels={"reason": "db_record"})
                    except Exception as m_err:
                        logger.debug(f"metrics increment failed (audio_chat_failopen_db_record): error={m_err}")
                    if failopen_remaining <= 0:
                        try:
                            increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_record"})
                        except Exception as m_err:
                            logger.debug(
                                f"metrics increment failed (audio_chat_failopen_cap_db_record): error={m_err}"
                            )
                        raise QuotaExceeded("daily_minutes") from None

        async def _on_heartbeat() -> None:
            try:
                await heartbeat_stream(user_id_for_usage)  # type: ignore[arg-type]
            except Exception as _hb_e:
                logger.debug(f"Heartbeat failed for user_id={user_id_for_usage}: {_hb_e}")

        # Parse initial config
        try:
            raw_cfg = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
            cfg_data = json.loads(raw_cfg)
        except Exception as exc:
            if _outer_stream:
                await _outer_stream.send_json(
                    _ws_error_payload(
                        "config frame required",
                        request_id=request_id,
                        exc=exc,
                        error_type="bad_request",
                    )
                )
            await websocket.close(code=4400)
            return

        if cfg_data.get("type") != "config":
            if _outer_stream:
                await _outer_stream.send_json(
                    {"type": "error", "message": "First frame must be type=config"}
                )
            await websocket.close(code=4400)
            return

        stt_cfg = cfg_data.get("stt") or cfg_data
        llm_cfg = cfg_data.get("llm") or {}
        tts_cfg = cfg_data.get("tts") or {}
        session_id = cfg_data.get("session_id")
        metadata = cfg_data.get("metadata") if isinstance(cfg_data.get("metadata"), dict) else None

        config = UnifiedStreamingConfig()
        try:
            config.model = stt_cfg.get("model", config.model)
            variant_override = stt_cfg.get("variant") or stt_cfg.get("model_variant")
            if variant_override:
                config.model_variant = variant_override
            config.sample_rate = stt_cfg.get("sample_rate", config.sample_rate)
            config.enable_partial = stt_cfg.get("enable_partial", config.enable_partial)
            config.enable_vad = bool(stt_cfg.get("enable_vad", config.enable_vad))
            config.vad_threshold = float(stt_cfg.get("vad_threshold", config.vad_threshold))
            config.vad_min_silence_ms = int(stt_cfg.get("min_silence_ms", config.vad_min_silence_ms))
            config.vad_turn_stop_secs = float(stt_cfg.get("turn_stop_secs", config.vad_turn_stop_secs))
            if "min_utterance_secs" in stt_cfg:
                config.vad_min_utterance_secs = float(stt_cfg.get("min_utterance_secs"))
            if "min_partial_duration" in stt_cfg:
                try:
                    config.min_partial_duration = max(0.0, float(stt_cfg.get("min_partial_duration")))
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"Invalid min_partial_duration value in audio chat config: {exc}")
            if "language" in stt_cfg:
                config.language = stt_cfg.get("language")
        except Exception as cfg_exc:
            logger.debug(f"Failed to parse streaming STT config: {cfg_exc}")

        llm_provider = (llm_cfg.get("provider") or llm_cfg.get("api_provider") or DEFAULT_LLM_PROVIDER).lower()
        llm_model = llm_cfg.get("model") or os.getenv("AUDIO_CHAT_DEFAULT_LLM_MODEL") or "gpt-3.5-turbo"
        llm_temperature = llm_cfg.get("temperature")
        llm_max_tokens = llm_cfg.get("max_tokens")
        llm_system_prompt = llm_cfg.get("system_prompt") or llm_cfg.get("system")
        llm_extra_params = llm_cfg.get("extra_params") if isinstance(llm_cfg.get("extra_params"), dict) else None

        try:
            tts_speed_raw = tts_cfg.get("speed", 1.0)
            tts_speed = float(tts_speed_raw)
        except Exception:
            tts_speed = 1.0
        response_format = tts_cfg.get("format") or tts_cfg.get("response_format") or "pcm"
        tts_model = tts_cfg.get("model", "kokoro")
        tts_voice = tts_cfg.get("voice", "af_heart")
        tts_provider = tts_cfg.get("provider")
        tts_extra_params = tts_cfg.get("extra_params") if isinstance(tts_cfg.get("extra_params"), dict) else None

        # Initialize STT transcriber + VAD gate
        try:
            transcriber = UnifiedStreamingTranscriber(config)
            transcriber.initialize()
        except Exception as exc:
            logger.error(f"Streaming transcriber init failed: {exc}", exc_info=True)
            if _outer_stream:
                data_payload = {
                    "model": config.model,
                    "variant": getattr(config, "model_variant", None),
                    "request_id": request_id,
                }
                details = _maybe_debug_details(exc)
                if details:
                    data_payload["details"] = details
                await _outer_stream.error(
                    "model_unavailable",
                    "Failed to initialize streaming transcriber",
                    data=data_payload,
                )
            return

        turn_detector: Optional[SileroTurnDetector] = None
        vad_warning_sent = False

        async def _send_vad_warning(message: str, details: Optional[str]) -> None:
            payload: Dict[str, Any] = {
                "type": "warning",
                "warning_type": "vad_unavailable",
                "message": message,
                "details": details,
            }
            try:
                if _outer_stream:
                    await _outer_stream.send_json(payload)
                else:
                    await websocket.send_json(payload)
            except Exception as send_exc:
                logger.debug(f"audio.chat.stream VAD warning send failed: {send_exc}")

        if config.enable_vad:
            try:
                turn_detector = SileroTurnDetector(
                    sample_rate=config.sample_rate,
                    enabled=True,
                    vad_threshold=config.vad_threshold,
                    min_silence_ms=config.vad_min_silence_ms,
                    turn_stop_secs=config.vad_turn_stop_secs,
                    min_utterance_secs=config.vad_min_utterance_secs,
                )
                if not turn_detector.available:
                    vad_warning_sent = True
                    await _send_vad_warning(
                        "Silero VAD unavailable; auto-commit disabled",
                        turn_detector.unavailable_reason,
                    )
                    turn_detector = None
            except Exception as vad_exc:
                logger.debug(f"VAD init failed: {vad_exc}")
                turn_detector = None

        chat_history: List[Dict[str, Any]] = []
        if session_id:
            try:
                chat_history.append({"role": "system", "content": f"session:{session_id}"})
            except Exception:
                chat_history = []

        def _action_hint() -> Optional[str]:
            try:
                if metadata and isinstance(metadata, dict) and metadata.get("action"):
                    return str(metadata.get("action"))
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to read action hint from metadata: {exc}")
            try:
                if llm_extra_params and isinstance(llm_extra_params, dict) and llm_extra_params.get("action"):
                    return str(llm_extra_params.get("action"))
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to read action hint from llm_extra_params: {exc}")
            return None

        async def _maybe_run_action(transcript_text: str) -> Optional[Dict[str, Any]]:
            action_name = _action_hint()
            if not action_name:
                return None
            try:
                enabled = getattr(speech_chat_service, "_actions_enabled", lambda: False)()
            except Exception:
                enabled = False
            if not enabled:
                return None

            user_obj = SimpleNamespace(id=user_id_for_usage)
            try:
                return await speech_chat_service._execute_action(action_name, transcript_text, user_obj)
            except Exception as exc:
                logger.warning(f"Streaming action execution failed: action={action_name}, error={exc}")
                payload = {
                    "action": action_name,
                    "status": "error",
                    "message": "Action execution failed",
                    "user_id": getattr(user_obj, "id", None),
                }
                details = _maybe_debug_details(exc)
                if details:
                    payload["details"] = details
                return payload

        processing_turn = False

        async def _iter_stream_lines(stream_obj):
            if hasattr(stream_obj, "__aiter__"):
                async for line in stream_obj:
                    yield line
            else:
                for line in stream_obj:
                    yield line

        async def _stream_llm(transcript_text: str) -> tuple[str, Optional[str], Optional[Dict[str, Any]]]:
            nonlocal chat_history
            def _fallback_resolver(name: str) -> Optional[str]:
                try:
                    return get_api_keys().get(name)
                except (KeyError, FileNotFoundError, OSError, ValueError, configparser.Error) as exc:
                    logger.debug(f"LLM fallback resolver failed for provider '{name}': {exc}")
                    return None

            user_id_int = int(user_id_for_usage) if user_id_for_usage else None
            byok_resolution = await resolve_byok_credentials(
                llm_provider,
                user_id=user_id_int,
                request=websocket,
                fallback_resolver=_fallback_resolver,
            )
            app_config = ensure_app_config(byok_resolution.app_config)
            provider_api_key = byok_resolution.api_key or resolve_provider_api_key_from_config(
                llm_provider,
                app_config,
            )
            if not provider_api_key:
                if _outer_stream:
                    await _outer_stream.send_json(
                        {
                            "type": "error",
                            "error_type": "missing_provider_credentials",
                            "message": "No API key available for provider",
                            "provider": llm_provider,
                        }
                    )
                return "", "missing_provider_credentials", None
            messages_payload = list(chat_history)
            messages_payload.append({"role": "user", "content": transcript_text})
            try:
                adapter = get_registry().get_adapter(normalize_provider(llm_provider))
                if adapter is None:
                    llm_stream = await chat_api_call_async(
                        api_endpoint=llm_provider,
                        messages_payload=messages_payload,
                        api_key=provider_api_key,
                        temp=llm_temperature,
                        model=llm_model,
                        max_tokens=llm_max_tokens,
                        streaming=True,
                        system_message=llm_system_prompt,
                        user_identifier=str(user_id_for_usage),
                        extra_body=llm_extra_params,
                        app_config=app_config,
                    )
                else:
                    request_payload = {
                        "messages": messages_payload,
                        "system_message": llm_system_prompt,
                        "model": llm_model,
                        "api_key": provider_api_key,
                        "temperature": llm_temperature,
                        "max_tokens": llm_max_tokens,
                        "stream": True,
                        "user": str(user_id_for_usage),
                        "app_config": app_config,
                    }
                    if llm_extra_params:
                        for key, value in llm_extra_params.items():
                            if request_payload.get(key) is None:
                                request_payload[key] = value
                    stream_candidate = adapter.astream(request_payload)
                    if asyncio.iscoroutine(stream_candidate):
                        try:
                            llm_stream = await stream_candidate
                        except NotImplementedError:
                            llm_stream = await chat_api_call_async(
                                api_endpoint=llm_provider,
                                messages_payload=messages_payload,
                                api_key=provider_api_key,
                                temp=llm_temperature,
                                model=llm_model,
                                max_tokens=llm_max_tokens,
                                streaming=True,
                                system_message=llm_system_prompt,
                                user_identifier=str(user_id_for_usage),
                                extra_body=llm_extra_params,
                                app_config=app_config,
                            )
                    else:
                        llm_stream = stream_candidate
            except Exception as exc:
                logger.error(f"LLM stream failed: {exc}", exc_info=True)
                if _outer_stream:
                    await _outer_stream.send_json(
                        _ws_error_payload(
                            "LLM call failed",
                            request_id=request_id,
                            exc=exc,
                            error_type="llm_error",
                        )
                    )
                return "", None, None

            deltas: List[str] = []
            finish_reason: Optional[str] = None
            usage_payload: Optional[Dict[str, Any]] = None

            async for raw_line in _iter_stream_lines(llm_stream):
                try:
                    line_str = (
                        raw_line.decode("utf-8", errors="ignore")
                        if isinstance(raw_line, (bytes, bytearray))
                        else str(raw_line)
                    )
                except Exception:
                    continue
                if not line_str:
                    continue
                stripped = line_str.strip()
                if stripped.lower() == "data: [done]" or stripped.lower() == "[done]":
                    break
                if stripped.lower().endswith("[done]"):
                    break
                payload_str = stripped
                if payload_str.startswith("data:"):
                    payload_str = payload_str[len("data:") :].strip()
                try:
                    payload = json.loads(payload_str)
                except Exception:
                    continue
                if "error" in payload:
                    if _outer_stream:
                        await _outer_stream.send_json(
                            {
                                "type": "error",
                                "error_type": "llm_error",
                                "message": payload.get("error"),
                            }
                        )
                    continue
                choices = payload.get("choices") or []
                for choice in choices:
                    delta = choice.get("delta") or choice.get("message") or {}
                    if isinstance(delta, dict):
                        content = delta.get("content") or delta.get("text")
                    else:
                        content = None
                    if content:
                        deltas.append(content)
                        if _outer_stream:
                            await _outer_stream.send_json({"type": "llm_delta", "delta": content})
                    if choice.get("finish_reason"):
                        finish_reason = choice.get("finish_reason")
                if payload.get("usage"):
                    usage_payload = payload.get("usage")

            assistant_text = "".join(deltas).strip()
            if _outer_stream:
                await _outer_stream.send_json(
                    {
                        "type": "llm_message",
                        "text": assistant_text,
                        "finish_reason": finish_reason,
                        "usage": usage_payload,
                    }
                )
            chat_history.append({"role": "user", "content": transcript_text})
            if assistant_text:
                chat_history.append({"role": "assistant", "content": assistant_text})
            if len(chat_history) > CHAT_HISTORY_MAX_MESSAGES:
                chat_history = chat_history[-CHAT_HISTORY_MAX_MESSAGES:]
            try:
                await byok_resolution.touch_last_used()
            except Exception as exc:
                logger.debug(f"Failed to update BYOK last_used timestamp for LLM: {exc}")
            return assistant_text, finish_reason, usage_payload

        async def _stream_tts(text: str, voice_to_voice_start: float) -> None:
            if not text:
                if _outer_stream:
                    await _outer_stream.send_json(
                        {
                            "type": "error",
                            "error_type": "empty_assistant",
                            "message": "Assistant reply empty",
                        }
                    )
                return
            allowed_formats = {"mp3", "opus", "aac", "flac", "wav", "pcm"}
            if response_format not in allowed_formats:
                if _outer_stream:
                    await _outer_stream.send_json(
                        {
                            "type": "error",
                            "error_type": "bad_request",
                            "message": f"Unsupported format '{response_format}'",
                        }
                    )
                return

            speech_req = OpenAISpeechRequest(
                model=tts_model,
                input=text,
                voice=tts_voice,
                response_format=response_format,
                speed=tts_speed,
                stream=True,
                extra_params=tts_extra_params,
            )

            tts_service = await get_tts_service()

            if _outer_stream:
                try:
                    await _outer_stream.send_json(
                        {
                            "type": "tts_start",
                            "format": response_format,
                            "provider": tts_provider or "auto",
                            "voice": tts_voice,
                        }
                    )
                except Exception as send_exc:
                    logger.debug(f"audio.chat.stream tts_start send failed: error={send_exc}")

            try:
                async def _error_handler(exc: Exception) -> None:
                    if _outer_stream:
                        try:
                            logger.error(f"audio.chat.stream TTS generation failed: {exc}", exc_info=True)
                            await _outer_stream.send_json(
                                _ws_error_payload(
                                    "TTS generation failed",
                                    request_id=request_id,
                                    exc=exc,
                                    error_type="tts_error",
                                )
                            )
                        except Exception as send_exc:
                            logger.debug(
                                f"audio.chat.stream producer error frame send failed: error={send_exc}"
                            )

                await _stream_tts_to_websocket(
                    websocket=websocket,
                    speech_req=speech_req,
                    tts_service=tts_service,
                    provider=tts_provider,
                    outer_stream=_outer_stream,
                    reg=reg,
                    route="audio.chat.stream",
                    component_label="audio_chat_ws",
                    voice_to_voice_start=voice_to_voice_start,
                    error_handler=_error_handler,
                )
            finally:
                if _outer_stream:
                    try:
                        await _outer_stream.send_json({"type": "tts_done"})
                    except Exception as send_exc:
                        logger.debug(
                            f"audio.chat.stream tts_done frame send failed: error={send_exc}"
                        )

        async def _finalize_turn(commit_at: float, *, auto: bool = False) -> None:
            nonlocal processing_turn
            if processing_turn:
                return
            processing_turn = True
            try:
                transcript_text = transcriber.get_full_transcript()
                final_emit_at = time.time()
                payload = {
                    "type": "full_transcript",
                    "text": transcript_text,
                    "timestamp": final_emit_at,
                    "voice_to_voice_start": final_emit_at,
                }
                if auto:
                    payload["auto_commit"] = True
                if _outer_stream:
                    await _outer_stream.send_json(payload)

                # Metric for commit->final emit latency
                try:
                    reg.observe(
                        "stt_final_latency_seconds",
                        max(0.0, final_emit_at - float(commit_at or final_emit_at)),
                        labels={
                            "model": getattr(config, "model", "parakeet"),
                            "variant": getattr(config, "model_variant", "standard"),
                            "endpoint": "audio.chat.stream",
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "metrics observe failed "
                        "(stt_final_latency_seconds, endpoint=audio.chat.stream): %s",
                        exc,
                    )

                assistant_text, finish_reason, usage_payload = await _stream_llm(transcript_text)
                action_result = await _maybe_run_action(transcript_text)
                if _outer_stream:
                    await _outer_stream.send_json(
                        {
                            "type": "assistant_summary",
                            "finish_reason": finish_reason,
                            "usage": usage_payload,
                            "action": action_result,
                        }
                    )
                if action_result:
                    try:
                        chat_history.append({"role": "tool", "content": json.dumps(action_result)})
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(f"Failed to append action_result to chat_history: {exc}")
                    if _outer_stream:
                        await _outer_stream.send_json({"type": "action_result", **action_result})
                await _stream_tts(assistant_text, final_emit_at)
            finally:
                try:
                    transcriber.reset()
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"audio.chat.stream transcriber.reset() failed in finalize_turn: {exc}")
                processing_turn = False

        try:
            while True:
                raw_msg = await websocket.receive_text()
                try:
                    if _outer_stream:
                        _outer_stream.mark_activity()
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"audio.chat.stream outer_stream.mark_activity failed: {exc}")
                try:
                    data = json.loads(raw_msg)
                except Exception:
                    if _outer_stream:
                        await _outer_stream.send_json(
                            {"type": "error", "error_type": "bad_request", "message": "Invalid JSON"}
                        )
                    continue

                msg_type = data.get("type")
                if msg_type == "audio":
                    audio_base64 = data.get("data", "")
                    try:
                        audio_bytes = base64.b64decode(audio_base64)
                    except Exception:
                        if _outer_stream:
                            await _outer_stream.send_json(
                                {
                                    "type": "error",
                                    "error_type": "bad_request",
                                    "message": "Invalid base64 audio frame",
                                }
                            )
                        continue

                    auto_commit_triggered = False
                    if turn_detector:
                        auto_commit_triggered = turn_detector.observe(audio_bytes)
                        if not turn_detector.available and not vad_warning_sent:
                            vad_warning_sent = True
                            await _send_vad_warning(
                                "Silero VAD disabled; continuing without auto-commit",
                                turn_detector.unavailable_reason,
                            )
                            turn_detector = None

                    try:
                        seconds = bytes_to_seconds(len(audio_bytes), int(config.sample_rate or 16000))
                    except Exception:
                        seconds = float(len(audio_bytes)) / float(
                            4 * max(1, int(config.sample_rate or 16000))
                        )
                    try:
                        await _on_audio_quota(seconds, int(config.sample_rate or 16000))
                    except QuotaExceeded as qe:
                        if _outer_stream:
                            try:
                                await _outer_stream.send_json(
                                    {
                                        "type": "error",
                                        "error_type": "quota_exceeded",
                                        "quota": getattr(qe, "quota", "daily_minutes"),
                                        "message": "Streaming quota exceeded",
                                    }
                                )
                            except Exception as send_exc:
                                logger.debug(
                                    f"WebSocket send_json quota error failed (audio.chat.stream): error={send_exc}"
                                )
                        try:
                            await websocket.close(code=_policy_close_code(), reason="quota_exceeded")
                        except Exception as close_exc:
                            logger.debug(
                                f"WebSocket close (quota case) failed (audio.chat.stream): error={close_exc}"
                            )
                        break

                    try:
                        await _on_heartbeat()
                    except Exception as hb_exc:
                        logger.debug(f"audio.chat.stream heartbeat failed: error={hb_exc}")

                    result = await transcriber.process_audio_chunk(audio_bytes)
                    if result:
                        # Drop audio blob if present
                        result.pop("_audio_chunk", None)
                        if _outer_stream:
                            await _outer_stream.send_json(result)
                    if auto_commit_triggered:
                        await _finalize_turn(
                            commit_at=getattr(turn_detector, "last_trigger_at", None)
                            if turn_detector
                            else time.time(),
                            auto=True,
                        )

                elif msg_type == "commit":
                    await _finalize_turn(time.time(), auto=False)
                elif msg_type == "reset":
                    try:
                        transcriber.reset()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(f"audio.chat.stream transcriber.reset() failed on reset message: {exc}")
                    if _outer_stream:
                        await _outer_stream.send_json({"type": "status", "state": "reset"})
                elif msg_type == "stop":
                    if _outer_stream:
                        await _outer_stream.done()
                    break
                else:
                    if _outer_stream:
                        await _outer_stream.send_json(
                            {"type": "warning", "message": f"Unknown message type {msg_type}"}
                        )

        except WebSocketDisconnect:
            logger.info("Audio chat WS disconnected")
        except Exception as exc:
            logger.error(f"Audio chat WS error: {exc}", exc_info=True)
            try:
                if _outer_stream:
                    await _outer_stream.send_json(
                        _ws_error_payload(
                            "Internal error",
                            request_id=request_id,
                            exc=exc,
                            error_type="internal_error",
                        )
                    )
            except Exception as send_exc:  # noqa: BLE001
                logger.debug(f"audio.chat.stream failed to send internal_error frame: {send_exc}")
    finally:
        if acquired_stream:
            try:
                await finish_stream(user_id_for_usage)
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    f"Failed to release streaming quota slot (audio.chat.stream): "
                    f"user_id={user_id_for_usage}, error={exc}"
                )
        try:
            if _outer_stream:
                await _outer_stream.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"audio.chat.stream outer_stream.stop failed: {exc}")
        try:
            await websocket.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"audio.chat.stream websocket close failed in cleanup: {exc}")


@ws_router.websocket("/stream/tts")
async def websocket_tts(
    websocket: WebSocket,
    token: Optional[str] = Query(None),  # noqa: ARG001 - kept for parity with transcribe endpoint
):
    """
    WebSocket TTS streaming endpoint: accepts a prompt frame and streams audio bytes.

    Authentication mirrors `_audio_ws_authenticate`:
    - Multi-user: `X-API-KEY` header, `Authorization: Bearer <JWT>`, or `token` query parameter (API key or JWT).
    - Single-user: fixed API key via header, `token` query parameter, or initial auth message; optional IP allowlist.
    """
    await websocket.accept()

    try:
        _raw_idle = os.getenv("AUDIO_WS_IDLE_TIMEOUT_S") or os.getenv("STREAM_IDLE_TIMEOUT_S")
        _idle_timeout = float(_raw_idle) if _raw_idle else None
    except Exception:
        _idle_timeout = None

    # Wrap websocket for consistent metrics/heartbeats
    _outer_stream = None
    try:
        from tldw_Server_API.app.core.Streaming.streams import WebSocketStream as _WSStream

        _outer_stream = _WSStream(
            websocket,
            heartbeat_interval_s=None,
            compat_error_type=True,
            close_on_done=True,
            idle_timeout_s=_idle_timeout,
            labels={"component": "audio", "endpoint": "audio_tts_ws"},
        )
        await _outer_stream.start()
    except Exception:
        _outer_stream = None

    # Correlate via request id
    try:
        _hdrs = websocket.headers or {}
        request_id = (
            _hdrs.get("x-request-id")
            or _hdrs.get("X-Request-Id")
            or (websocket.query_params.get("request_id") if hasattr(websocket, "query_params") else None)
            or str(uuid4())
        )
    except Exception:
        request_id = str(uuid4())
    try:
        logger.info(f"TTS WS connected: request_id={request_id}")
    except Exception as exc:
        logger.debug(f"TTS WS connection logging failed: {exc}")

    def _policy_close_code() -> int:
        flag = str(os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    # Authenticate (parity with STT WS)
    auth_ok, jwt_user_id = await _audio_ws_authenticate(
        websocket,
        _outer_stream,
        endpoint_id="audio.stream.tts",
        ws_path="/api/v1/audio/stream/tts",
    )
    if not auth_ok:
        return

    # Determine quota user id
    if is_multi_user_mode() and jwt_user_id is not None:
        user_id_for_usage = int(jwt_user_id)
    else:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings

        _s = _get_settings()
        user_id_for_usage = getattr(_s, "SINGLE_USER_FIXED_ID", 1)

    acquired_stream = False

    try:
        # Concurrency guard
        try:
            ok_stream, msg_stream = await can_start_stream(user_id_for_usage)
            if not ok_stream:
                if _outer_stream:
                    await _outer_stream.send_json(
                        {"type": "error", "message": msg_stream or "Concurrent audio streams limit reached"}
                    )
                await websocket.close(code=_policy_close_code())
                return
            acquired_stream = True
        except Exception:
            if _outer_stream:
                await _outer_stream.send_json(
                    {"type": "error", "message": "Unable to evaluate audio stream quota or concurrency"}
                )
            await websocket.close(code=_policy_close_code())
            return

        # Parse prompt frame
        try:
            prompt_message = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            prompt_data = json.loads(prompt_message)
        except Exception as exc:
            if _outer_stream:
                try:
                    data_payload = {"request_id": request_id}
                    details = _maybe_debug_details(exc)
                    if details:
                        data_payload["details"] = details
                    await _outer_stream.error(
                        "bad_request",
                        "Prompt frame required",
                        data=data_payload if data_payload else None,
                    )
                except Exception as send_exc:
                    logger.debug(f"TTS WS error frame send failed: {send_exc}")
            await websocket.close(code=4400)
            return

        if (prompt_data.get("type") or "prompt") not in {"prompt", "config"}:
            if _outer_stream:
                await _outer_stream.error("bad_request", "First frame must be type=prompt")
            await websocket.close(code=4400)
            return

        text = prompt_data.get("text") or prompt_data.get("input")
        if not text:
            if _outer_stream:
                await _outer_stream.error("bad_request", "Prompt text is required")
            await websocket.close(code=4400)
            return

        # Build TTS request
        response_format = prompt_data.get("format") or prompt_data.get("response_format") or "pcm"
        allowed_formats = {"mp3", "opus", "aac", "flac", "wav", "pcm"}
        if response_format not in allowed_formats:
            if _outer_stream:
                await _outer_stream.error("bad_request", f"Unsupported format '{response_format}'")
            await websocket.close(code=4400)
            return

        try:
            speed_val = float(prompt_data.get("speed", 1.0))
        except Exception:
            speed_val = 1.0

        extra_params = prompt_data.get("extra_params")
        if extra_params is not None and not isinstance(extra_params, dict):
            extra_params = None

        speech_req = OpenAISpeechRequest(
            model=prompt_data.get("model", "kokoro"),
            input=text,
            voice=prompt_data.get("voice", "af_heart"),
            response_format=response_format,
            speed=speed_val,
            stream=True,
            lang_code=prompt_data.get("lang") or prompt_data.get("lang_code"),
            extra_params=extra_params,
        )

        provider_hint = prompt_data.get("provider")
        reg = get_metrics_registry()
        tts_service = await get_tts_service()

        async def _ws_tts_error_handler(exc: Exception) -> None:
            if not _outer_stream:
                return
            logger.error(f"audio.stream.tts TTS generation failed: {exc}", exc_info=True)
            data_payload = {"request_id": request_id}
            details = _maybe_debug_details(exc)
            if details:
                data_payload["details"] = details
            await _outer_stream.error(
                "internal_error",
                "TTS generation failed",
                data=data_payload if data_payload else None,
            )

        # Delegate to the shared streaming helper; it manages its own
        # producer/consumer tasks and error handling.
        await _stream_tts_to_websocket(
            websocket=websocket,
            speech_req=speech_req,
            tts_service=tts_service,
            provider=provider_hint,
            outer_stream=_outer_stream,
            reg=reg,
            route="audio.stream.tts",
            component_label="audio_tts_ws",
            error_handler=_ws_tts_error_handler if _outer_stream else None,
        )
    finally:
        if acquired_stream:
            try:
                await finish_stream(user_id_for_usage)
            except EXPECTED_DB_EXC as e:
                logger.debug(
                    f"Failed to release streaming quota slot (audio.stream.tts): "
                    f"user_id={user_id_for_usage}, error={e}"
                )
        try:
            if _outer_stream:
                await _outer_stream.done()
        except Exception as outer_exc:
            try:
                await websocket.close()
            except Exception as close_exc:
                logger.debug(
                    f"audio.stream.tts websocket close failed after _outer_stream.done error: "
                    f"outer_error={outer_exc}, close_error={close_exc}"
                )


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
                transcribe_with_parakeet_mlx,
            )

            available_models.append("parakeet-mlx")
        except ImportError:
            pass

        # Check for standard variant (NeMo)
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
                load_parakeet_model,
            )

            available_models.append("parakeet-standard")
        except ImportError:
            pass

        # Check for ONNX variant
        try:
            import onnxruntime
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_ONNX import (
                load_parakeet_onnx_model,
            )

            available_models.append("parakeet-onnx")
        except ImportError:
            pass

        return JSONResponse(
            {
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
                    "audio_persistence": True,
                },
            }
        )

    except Exception as e:
        import traceback

        logger.error(f"Error checking streaming status: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "An internal error occurred. Please try again later."},
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
    return JSONResponse(
        {
            "user_id": current_user.id,
            "tier": tier,
            "limits": limits,
            "used_today_minutes": used_minutes,
            "remaining_minutes": remaining_minutes,
            "active_streams": active_streams,
            "can_start_stream": can_start,
        }
    )


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
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
            UnifiedStreamingTranscriber,
            UnifiedStreamingConfig,
        )
        import base64

        # Try to initialize transcriber
        config = UnifiedStreamingConfig(model="parakeet", model_variant="mlx")
        transcriber = UnifiedStreamingTranscriber(config)
        transcriber.initialize()

        # Generate test audio
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = (0.5 * np.sin(440 * 2 * np.pi * t)).astype(np.float32)
        encoded = base64.b64encode(audio.tobytes()).decode("utf-8")

        # Try processing
        result = await transcriber.process_audio_chunk(base64.b64decode(encoded))

        return JSONResponse(
            {
                "status": "success",
                "test_passed": True,
                "message": "Streaming transcription is working",
                "test_result": result if result else "Buffer accumulating",
            }
        )

    except Exception as e:
        logger.error(f"Streaming test failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "test_passed": False,
                "message": "An internal error occurred during the streaming test. Please contact support if the problem persists.",
            },
        )


#######################################################################################################################
#
# Voice Management Endpoints
#


@router.post("/voices/upload", summary="Upload a custom voice sample")
async def upload_voice(
    request: Request,
    file: UploadFile = File(..., description="Voice sample audio file (WAV, MP3, FLAC, OGG)"),
    name: str = Form(..., description="Name for the voice"),
    description: Optional[str] = Form(None, description="Description of the voice"),
    provider: str = Form(default="vibevoice", description="Target TTS provider"),
    reference_text: Optional[str] = Form(
        default=None,
        description="Optional transcript of the reference audio for cloning providers",
    ),
    current_user: User = Depends(get_request_user),
):
    """
    Upload a custom voice sample for use with TTS.

    Supports voice cloning for compatible providers:
    - VibeVoice: Any duration (1-shot cloning)
    - Higgs: 3-10 seconds recommended
    - Chatterbox: 5-20 seconds recommended
    - NeuTTS: 3-15 seconds recommended (reference text required for encoding)

    The voice will be processed and optimized for the specified provider.
    """
    request_id = ensure_request_id(request)
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import (
            get_voice_manager,
            VoiceUploadRequest,
            VoiceProcessingError,
            VoiceQuotaExceededError,
        )

        # Get voice manager
        voice_manager = get_voice_manager()

        # Read file content
        file_content = await file.read()

        # Create upload request
        upload_request = VoiceUploadRequest(
            name=name,
            description=description,
            provider=provider,
            reference_text=reference_text,
        )

        # Process upload
        result = await voice_manager.upload_voice(
            user_id=current_user.id, file_content=file_content, filename=file.filename, request=upload_request
        )

        return result.model_dump()

    except ImportError:
        # Placeholder response when voice management is not available
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Custom voice upload is not available in this build"
        )
    except VoiceQuotaExceededError as e:
        logger.warning(f"Voice quota exceeded: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_http_error_detail("Voice quota exceeded", request_id, exc=e),
        ) from e
    except VoiceProcessingError as e:
        logger.warning(f"Voice processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_http_error_detail("Voice processing failed", request_id, exc=e),
        ) from e
    except Exception as e:
        logger.error(f"Voice upload error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload voice sample")


@router.post("/voices/encode", summary="Encode stored voice reference for a provider")
async def encode_voice_reference(
    payload: VoiceEncodeRequest,
    current_user: User = Depends(get_request_user),
):
    """
    Encode provider-specific artifacts for a stored voice reference.

    This stores artifacts (e.g., NeuTTS ref_codes) alongside the uploaded voice
    so callers can use `custom:{voice_id}` without re-uploading reference audio.
    """
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import (
            get_voice_manager,
            VoiceProcessingError,
        )

        voice_manager = get_voice_manager()
        result = await voice_manager.encode_voice_reference(
            user_id=current_user.id,
            voice_id=payload.voice_id,
            provider=payload.provider,
            reference_text=payload.reference_text,
            force=payload.force,
        )
        return VoiceEncodeResponse(**result.model_dump())
    except VoiceProcessingError as e:
        logger.warning(f"Voice encoding failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Voice encode error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to encode voice reference")


@router.get("/voices", summary="List user's custom voices")
async def list_voices(request: Request, current_user: User = Depends(get_request_user)):
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

        return {"voices": [voice.model_dump() for voice in voices], "count": len(voices)}

    except ImportError:
        # Placeholder response when voice management is not available
        return {"voices": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list voices")


@router.get("/voices/{voice_id}", summary="Get voice details")
async def get_voice_details(
    request: Request, voice_id: str = Path(..., description="Voice ID"), current_user: User = Depends(get_request_user)
):
    """
    Get detailed information about a specific voice.
    """
    try:
        from tldw_Server_API.app.core.TTS.voice_manager import get_voice_manager

        voice_manager = get_voice_manager()
        voice = await voice_manager.registry.get_voice(current_user.id, voice_id)

        if not voice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice not found")

        return voice.model_dump()

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Custom voice management not available")
    except Exception as e:
        logger.error(f"Error getting voice details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get voice details")


@router.delete("/voices/{voice_id}", summary="Delete a custom voice")
async def delete_voice(
    request: Request,
    voice_id: str = Path(..., description="Voice ID to delete"),
    current_user: User = Depends(get_request_user),
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice not found")

        return {"message": "Voice deleted successfully", "voice_id": voice_id}

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Custom voice management not available")
    except Exception as e:
        logger.error(f"Error deleting voice: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete voice")


@router.post("/voices/{voice_id}/preview", summary="Generate voice preview")
async def preview_voice(
    request: Request,
    voice_id: str = Path(..., description="Voice ID to preview"),
    text: str = Form(default="Hello, this is a preview of your custom voice.", description="Text to speak"),
    current_user: User = Depends(get_request_user),
    tts_service: TTSServiceV2 = Depends(get_tts_service),
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice not found")

        # Limit preview text length
        if len(text) > 100:
            text = text[:100]

        # Create TTS request with custom voice and stream generator directly
        preview_request = OpenAISpeechRequest(
            model=voice.provider, input=text, voice=f"custom:{voice_id}", response_format="mp3", stream=True
        )

        audio_stream = tts_service.generate_speech(
            preview_request,
            provider=None,
            fallback=True,
            user_id=current_user.id,
        )

        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={"Content-Disposition": f"inline; filename=preview_{voice_id}.mp3", "X-Voice-Name": voice.name},
        )

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Custom voice preview not available")
    except Exception as e:
        logger.error(f"Voice preview error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate voice preview"
        )


#
# End of audio.py
#######################################################################################################################
