# audio.py
# Description: Aggregate audio endpoints and WebSocket routes.
import asyncio as asyncio
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from starlette import status

from . import (
    audio_health,
    audio_history,
    audio_streaming,
    audio_tokenizer,
    audio_transcriptions,
    audio_tts,
    audio_voices,
)

router = APIRouter(
    tags=["Audio"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limit exceeded"},
    },
)

# Include HTTP routers
router.include_router(audio_tts.router)
router.include_router(audio_history.router)
router.include_router(audio_tokenizer.router)
router.include_router(audio_transcriptions.router)
router.include_router(audio_streaming.router)
router.include_router(audio_health.router)
router.include_router(audio_voices.router)

# Expose WebSocket router
ws_router = audio_streaming.ws_router

# Re-export selected endpoint callables for tests/backwards-compat imports
create_speech = audio_tts.create_speech
create_speech_metadata = audio_tts.create_speech_metadata
list_tts_providers = audio_tts.list_tts_providers
list_tts_voices = audio_tts.list_tts_voices
reset_tts_metrics = audio_tts.reset_tts_metrics
encode_audio_tokenizer = audio_tokenizer.encode_audio_tokenizer
decode_audio_tokenizer = audio_tokenizer.decode_audio_tokenizer
create_transcription = audio_transcriptions.create_transcription
create_translation = audio_transcriptions.create_translation
segment_transcript = audio_transcriptions.segment_transcript
audio_chat_turn = audio_streaming.audio_chat_turn
streaming_status = audio_streaming.streaming_status
streaming_limits = audio_streaming.streaming_limits
test_streaming = audio_streaming.test_streaming
get_tts_health = audio_health.get_tts_health
get_stt_health = audio_health.get_stt_health
upload_voice = audio_voices.upload_voice
encode_voice_reference = audio_voices.encode_voice_reference
list_voices = audio_voices.list_voices
get_voice_details = audio_voices.get_voice_details
delete_voice = audio_voices.delete_voice
preview_voice = audio_voices.preview_voice

# Dependency helpers (for FastAPI overrides in tests)
get_tts_service = audio_tts.get_tts_service

# Shared helper re-exports used in tests
from tldw_Server_API.app.core.Audio.tts_service import (
    _tts_fallback_resolver,
)
from tldw_Server_API.app.core.AuthNZ.byok_runtime import (
    record_byok_missing_credentials,
    resolve_byok_credentials,
)
from tldw_Server_API.app.core.config import load_comprehensive_config as _load_comprehensive_config

# Re-export config loader for tests to monkeypatch
load_comprehensive_config = _load_comprehensive_config


async def _resolve_tts_byok(
    *,
    provider_hint: Optional[str],
    current_user,
    request,
):
    """Wrapper to preserve audio.py patch points for BYOK resolution."""
    user_id_int = None
    try:
        user_id_int = getattr(current_user, "id_int", None)
        if user_id_int is None:
            raw_id = getattr(current_user, "id", None)
            if raw_id is not None:
                user_id_int = int(raw_id)
    except (AttributeError, TypeError, ValueError) as exc:
        logger.debug(f"Failed to extract user_id from current_user: {exc}")
        user_id_int = None

    tts_overrides = None
    byok_tts_resolution = None
    if provider_hint:
        resolver = resolve_byok_credentials
        try:
            from tldw_Server_API.app.api.v1.endpoints import audio as _audio_pkg

            resolver = getattr(_audio_pkg, "resolve_byok_credentials", resolve_byok_credentials)
        except Exception:
            resolver = resolve_byok_credentials
        byok_tts_resolution = await resolver(
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


def _get_failopen_cap_minutes() -> float:
    """Return per-connection fail-open cap in minutes for streaming quotas.

    Resolution order:
      1) Env var AUDIO_FAILOPEN_CAP_MINUTES (>0)
      2) Config [Audio-Quota] failopen_cap_minutes (>0)
      3) Config [Audio] failopen_cap_minutes (>0)
      4) Default 5.0
    """
    v = os.getenv("AUDIO_FAILOPEN_CAP_MINUTES")
    if v is not None:
        try:
            f = float(v)
            if f > 0:
                return f
        except (ValueError, TypeError) as exc:
            logger.debug(f"AUDIO_FAILOPEN_CAP_MINUTES parse failed: {exc}")
    try:
        try:
            from tldw_Server_API.app.api.v1.endpoints import audio as _audio_pkg

            cfg_loader = getattr(_audio_pkg, "load_comprehensive_config", load_comprehensive_config)
        except Exception:
            cfg_loader = load_comprehensive_config
        cfg = cfg_loader()
        if cfg is not None:
            if cfg.has_section("Audio-Quota"):
                try:
                    f = float(cfg.get("Audio-Quota", "failopen_cap_minutes", fallback=""))
                    if f > 0:
                        return f
                except (ValueError, TypeError) as exc:
                    logger.debug(f"[Audio-Quota].failopen_cap_minutes parse failed: {exc}")
            if cfg.has_section("Audio"):
                try:
                    f = float(cfg.get("Audio", "failopen_cap_minutes", fallback=""))
                    if f > 0:
                        return f
                except (ValueError, TypeError) as exc:
                    logger.debug(f"[Audio].failopen_cap_minutes parse failed: {exc}")
    except Exception as exc:
        logger.debug(f"Config read for failopen cap failed: {exc}")
    return 5.0


# Re-export streaming helpers/classes for tests to monkeypatch
websocket_audio_chat_stream = audio_streaming.websocket_audio_chat_stream
websocket_tts = audio_streaming.websocket_tts
websocket_tts_realtime = audio_streaming.websocket_tts_realtime
websocket_transcribe = audio_streaming.websocket_transcribe

_audio_ws_authenticate = audio_streaming._audio_ws_authenticate
_stream_tts_to_websocket = audio_streaming._stream_tts_to_websocket
CHAT_HISTORY_MAX_MESSAGES = audio_streaming.CHAT_HISTORY_MAX_MESSAGES

get_api_keys = audio_streaming.get_api_keys
chat_api_call_async = audio_streaming.chat_api_call_async
get_metrics_registry = audio_streaming.get_metrics_registry
UnifiedStreamingTranscriber = audio_streaming.UnifiedStreamingTranscriber
SileroTurnDetector = audio_streaming.SileroTurnDetector

# Re-export quota helpers for tests/monkeypatching
from tldw_Server_API.app.core.Usage.audio_quota import (
    add_daily_minutes as add_daily_minutes,
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    bytes_to_seconds as bytes_to_seconds,
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    can_start_stream as can_start_stream,
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    check_daily_minutes_allow as check_daily_minutes_allow,
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    finish_stream as finish_stream,
)

# Optional helpers for status/limits and TTL heartbeat
try:
    from tldw_Server_API.app.core.Usage.audio_quota import (
        active_streams_count as active_streams_count,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        get_daily_minutes_used as get_daily_minutes_used,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        get_job_heartbeat_interval_seconds as get_job_heartbeat_interval_seconds,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        get_user_tier as get_user_tier,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        heartbeat_jobs as heartbeat_jobs,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        heartbeat_stream as heartbeat_stream,
    )
except ImportError as e:
    logger.debug(f"audio_quota optional helpers not available: {e}")

# Expose job quota helpers at module scope for tests to monkeypatch
try:
    from tldw_Server_API.app.core.Usage.audio_quota import (
        can_start_job as can_start_job,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        finish_job as finish_job,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        get_limits_for_user as get_limits_for_user,
    )
    from tldw_Server_API.app.core.Usage.audio_quota import (
        increment_jobs_started as increment_jobs_started,
    )
except ImportError as e:
    logger.debug(f"audio_quota job helpers not available: {e}")
