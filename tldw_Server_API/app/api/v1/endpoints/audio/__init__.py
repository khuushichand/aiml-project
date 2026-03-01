"""Audio endpoints package.

Explicit, lightweight exports for endpoint helpers and shim patch points.
Heavy endpoint aggregation (``audio.audio``) is intentionally not imported
at module import time.
"""

import asyncio as asyncio

import soundfile as sf

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import (
    get_chacha_db_for_user_id,
)
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    check_rate_limit,
)
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import get_api_keys
from tldw_Server_API.app.core.Audio.streaming_service import (
    _audio_ws_authenticate,
    _stream_tts_to_websocket,
)
from tldw_Server_API.app.core.Audio.tokenizer_service import (
    _get_qwen3_tokenizer_settings,
    _load_qwen3_tokenizer,
)
from tldw_Server_API.app.core.Audio.tts_service import (
    _sanitize_speech_request,
    _tts_fallback_resolver,
)
from tldw_Server_API.app.core.AuthNZ.byok_runtime import resolve_byok_credentials
from tldw_Server_API.app.core.Chat.chat_helpers import (
    get_or_create_character_context,
    get_or_create_conversation,
)
from tldw_Server_API.app.core.Chat.chat_service import (
    perform_chat_api_call_async as chat_api_call_async,
)
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
from tldw_Server_API.app.core.Storage.generated_file_helpers import (
    save_and_register_tts_audio,
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    active_streams_count,
    add_daily_minutes,
    bytes_to_seconds,
    can_start_job,
    can_start_stream,
    check_daily_minutes_allow,
    finish_job,
    finish_stream,
    get_daily_minutes_used,
    get_job_heartbeat_interval_seconds,
    get_limits_for_user,
    get_user_tier,
    heartbeat_jobs,
    heartbeat_stream,
    increment_jobs_started,
)
from tldw_Server_API.app.core.config import load_comprehensive_config

from . import audio_tts as audio_tts

# Endpoint helpers that tests patch at package scope.
create_speech = audio_tts.create_speech
get_tts_service = audio_tts.get_tts_service


async def websocket_audio_chat_stream(*args, **kwargs):
    from .audio_streaming import websocket_audio_chat_stream as _impl

    return await _impl(*args, **kwargs)


async def websocket_tts(*args, **kwargs):
    from .audio_streaming import websocket_tts as _impl

    return await _impl(*args, **kwargs)


async def websocket_tts_realtime(*args, **kwargs):
    from .audio_streaming import websocket_tts_realtime as _impl

    return await _impl(*args, **kwargs)


async def websocket_transcribe(*args, **kwargs):
    from .audio_streaming import websocket_transcribe as _impl

    return await _impl(*args, **kwargs)


async def _resolve_tts_byok(*args, **kwargs):
    """Lazy wrapper preserving the historical package-level patch point."""
    from .audio import _resolve_tts_byok as _impl

    return await _impl(*args, **kwargs)


def UnifiedStreamingTranscriber(*args, **kwargs):
    """Lazy constructor wrapper to avoid importing streaming backends eagerly."""
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        UnifiedStreamingTranscriber as _impl,
    )

    return _impl(*args, **kwargs)


def SileroTurnDetector(*args, **kwargs):
    """Lazy constructor wrapper to avoid importing streaming backends eagerly."""
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        SileroTurnDetector as _impl,
    )

    return _impl(*args, **kwargs)


__all__ = sorted(
    name
    for name in globals()
    if not name.startswith("_")
    or name
    in {
        "_audio_ws_authenticate",
        "_get_qwen3_tokenizer_settings",
        "_load_qwen3_tokenizer",
        "_resolve_tts_byok",
        "_sanitize_speech_request",
        "_stream_tts_to_websocket",
        "_tts_fallback_resolver",
    }
)
