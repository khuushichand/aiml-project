# audio_streaming.py
# Description: Audio streaming endpoints (HTTP + WebSocket) and non-streaming chat.
import asyncio
import base64
import configparser
import contextlib
import json
import os
import time
from types import SimpleNamespace
from typing import Any, Optional
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import UsageEventLogger, get_usage_event_logger
from tldw_Server_API.app.api.v1.endpoints.audio.audio_tts import get_tts_service
from tldw_Server_API.app.api.v1.schemas.audio_schemas import (
    OpenAISpeechRequest,
    SpeechChatRequest,
    SpeechChatResponse,
    StreamingLimitsResponse,
    StreamingStatusResponse,
    StreamingTestResponse,
)
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import DEFAULT_LLM_PROVIDER, get_api_keys
from tldw_Server_API.app.core.Audio.error_payloads import _maybe_debug_details, _ws_error_payload
from tldw_Server_API.app.core.Audio.quota_helpers import EXPECTED_DB_EXC, EXPECTED_REDIS_EXC, _get_failopen_cap_minutes
from tldw_Server_API.app.core.Audio.streaming_service import (
    CHAT_HISTORY_MAX_MESSAGES,
    _audio_ws_authenticate,
    _stream_tts_to_websocket,
)
from tldw_Server_API.app.core.AuthNZ.byok_runtime import resolve_byok_credentials
from tldw_Server_API.app.core.AuthNZ.settings import is_multi_user_mode
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async as chat_api_call_async
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
    QuotaExceeded,
    SileroTurnDetector,
    UnifiedStreamingConfig,
    UnifiedStreamingTranscriber,
    handle_unified_websocket,
)
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.LLM_Calls.adapter_utils import (
    ensure_app_config,
    normalize_provider,
    resolve_provider_api_key_from_config,
)
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, get_ps_logger
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry, increment_counter
from tldw_Server_API.app.core.Streaming import speech_chat_service
from tldw_Server_API.app.core.TTS.realtime_session import RealtimeSessionConfig
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2

_AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    asyncio.TimeoutError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    IndexError,
    KeyError,
    LookupError,
    NameError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    configparser.Error,
    json.JSONDecodeError,
    HTTPException,
    WebSocketDisconnect,
    QuotaExceeded,
    *EXPECTED_DB_EXC,
    *EXPECTED_REDIS_EXC,
)

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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        pass
    try:
        from tldw_Server_API.app.api.v1.endpoints.audio import audio as audio_mod

        if hasattr(audio_mod, name):
            return getattr(audio_mod, name)
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        pass
    if not hasattr(audio_shim, name):
        raise NameError(name)
    return getattr(audio_shim, name)


def _shim_asyncio():
    try:
        return _audio_shim_attr("asyncio")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        return asyncio


async def _shim_audio_ws_authenticate(*args, **kwargs):
    try:
        fn = _audio_shim_attr("_audio_ws_authenticate")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        fn = _audio_ws_authenticate
    return await fn(*args, **kwargs)


def _shim_get_metrics_registry():
    try:
        fn = _audio_shim_attr("get_metrics_registry")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        fn = get_metrics_registry
    return fn()


def _shim_get_api_keys():
    try:
        fn = _audio_shim_attr("get_api_keys")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        fn = get_api_keys
    return fn()


async def _shim_chat_api_call_async(**kwargs):
    try:
        fn = _audio_shim_attr("chat_api_call_async")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        fn = chat_api_call_async
    return await fn(**kwargs)


def _shim_transcriber_cls():
    try:
        return _audio_shim_attr("UnifiedStreamingTranscriber")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        return UnifiedStreamingTranscriber


def _shim_silero_cls():
    try:
        return _audio_shim_attr("SileroTurnDetector")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        return SileroTurnDetector


async def _shim_get_tts_service():
    try:
        fn = _audio_shim_attr("get_tts_service")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        fn = get_tts_service
    return await fn()


async def _can_start_stream(user_id: int):
    return await _audio_shim_attr("can_start_stream")(user_id)


async def _finish_stream(user_id: int):
    return await _audio_shim_attr("finish_stream")(user_id)


async def _check_daily_minutes_allow(user_id: int, minutes: float):
    return await _audio_shim_attr("check_daily_minutes_allow")(user_id, minutes)


async def _add_daily_minutes(user_id: int, minutes: float):
    return await _audio_shim_attr("add_daily_minutes")(user_id, minutes)


def _bytes_to_seconds(size_bytes: int, sample_rate: int) -> float:
    return _audio_shim_attr("bytes_to_seconds")(size_bytes, sample_rate)


async def _heartbeat_stream(user_id: int):
    return await _audio_shim_attr("heartbeat_stream")(user_id)


async def _active_streams_count(user_id: int):
    return await _audio_shim_attr("active_streams_count")(user_id)


async def _get_daily_minutes_used(user_id: int):
    return await _audio_shim_attr("get_daily_minutes_used")(user_id)


async def _get_user_tier(user_id: int):
    return await _audio_shim_attr("get_user_tier")(user_id)


async def _get_limits_for_user(user_id: int):
    return await _audio_shim_attr("get_limits_for_user")(user_id)


async def _increment_jobs_started(user_id: int):
    return await _audio_shim_attr("increment_jobs_started")(user_id)


async def _finish_job(user_id: int):
    return await _audio_shim_attr("finish_job")(user_id)


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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:  # noqa: BLE001
        logger.debug(f"usage_log audio.chat failed: error={e}; request_id={rid}")

    acquired_stream = False
    user_id_for_usage = int(getattr(current_user, "id", 0) or 0)
    try:
        # Per-user concurrent chat guard (reuses audio stream limits)
        can_start, reason = await _can_start_stream(user_id_for_usage)
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
                    await _finish_stream(user_id_for_usage)
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:
                    logger.debug(f"_finish_stream failed (audio chat): {e}")
    except HTTPException:
        raise
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:  # noqa: BLE001
        logger.error(f"Speech chat turn failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech chat pipeline failed",
        ) from e

######################################################################################################################

# Create a separate router for WebSocket endpoints to avoid authentication conflicts
ws_router = APIRouter()


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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
                        already_accepted = False
                    if hasattr(self.ws, "accept") and not already_accepted:
                        await self.ws.accept()
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                    logger.debug(f"_BareStream.start failed: {exc}")

            async def send_json(self, payload: dict[str, Any]) -> None:
                try:
                    await self.ws.send_json(payload)
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
                    logger.debug(f"_BareStream.send_json failed: {exc}")

            async def error(self, code: str, message: str, *, data: Optional[dict[str, Any]] = None) -> None:
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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        request_id = str(uuid4())
    try:
        logger.info(f"Audio WS connected: request_id={request_id}")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"Audio WS connection logging failed: {exc}")

    # Ops toggle for standardized close code on quota/rate limits (4003 → 1008)
    import os as _os

    def _policy_close_code() -> int:
        flag = str(_os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    # Authenticate (shared helper; parity with other audio WS endpoints)
    auth_ok, jwt_user_id = await _shim_audio_ws_authenticate(
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
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Could not read STT-Settings from config: {e}")

        # If Nemo toolkit is unavailable in this environment, prefer Whisper
        # as the initial streaming model so we avoid repeated initialization
        # failures before falling back.
        try:
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (  # type: ignore
                is_nemo_available as _is_nemo_available,
            )

            nemo_ok = _is_nemo_available()
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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

        ok_stream, msg_stream = await _can_start_stream(user_id_for_usage)
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
                  `used_minutes` counter and records the minutes via `_add_daily_minutes`.
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
                allow, remaining_after = await _check_daily_minutes_allow(user_id_for_usage, minutes_chunk)
                if allow and remaining_after is not None:
                    remaining_minutes_snapshot = float(remaining_after)
            except EXPECTED_DB_EXC as e:
                # Backing store failed; allow temporarily but deduct from bounded fail-open budget
                logger.warning(
                    f"_check_daily_minutes_allow failed during streaming; temporarily allowing (bounded fail-open). user_id={user_id_for_usage}, error={e}"
                )
                allow = True
                failopen_remaining -= minutes_chunk
                try:
                    increment_counter(
                        "audio_failopen_minutes_total", value=float(minutes_chunk), labels={"reason": "db_check"}
                    )
                    increment_counter("audio_failopen_events_total", labels={"reason": "db_check"})
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
                    logger.debug(f"metrics increment failed (audio_failopen_db_check): error={m_err}")
                deducted = True
                if failopen_remaining <= 0:
                    try:
                        increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_check"})
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
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
                await _add_daily_minutes(user_id_for_usage, minutes_chunk)
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
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
                        logger.debug(f"metrics increment failed (audio_failopen_db_record): error={m_err}")
                    if failopen_remaining <= 0:
                        try:
                            increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_record"})
                        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
                            logger.debug(f"metrics increment failed (audio_failopen_cap_db_record): error={m_err}")
                        raise _QuotaExceeded("daily_minutes") from None

        async def _on_heartbeat() -> None:
            """
            Send a heartbeat to update streaming quota/timestamp for the current user.

            Invokes the module-level `_heartbeat_stream` callback with
            `user_id_for_usage` to record activity; any Redis-related
            exceptions are logged and suppressed.
            """
            try:
                await _heartbeat_stream(user_id_for_usage)
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
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:
                logger.debug(f"WebSocket send_json quota error failed: error={send_exc}")
            try:
                await websocket.close(code=_policy_close_code(), reason="quota_exceeded")
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as close_exc:
                logger.debug(f"WebSocket close (quota case) failed: error={close_exc}")
        finally:
            if acquired_stream:
                try:
                    await _finish_stream(user_id_for_usage)
                except EXPECTED_DB_EXC as e:
                    logger.debug(
                        f"Failed to release streaming quota slot (stream/transcribe): "
                        f"user_id={user_id_for_usage}, error={e}"
                    )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:
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
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:
                        logger.warning(f"WebSocket close after quota exceeded failed: error={e}")
                        try:
                            increment_counter(
                                "app_warning_events_total",
                                labels={"component": "audio", "event": "ws_close_quota_failed"},
                            )
                        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
                            logger.debug(f"metrics increment failed (audio ws_close_quota_failed): error={m_err}")
            else:
                # Let inner handler's error payload (if any) be the authoritative one.
                # Avoid sending a duplicate generic error frame that could race the client.
                pass
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Streaming transcription outer handler swallowed error: {e}")
            try:
                increment_counter(
                    "app_warning_events_total", labels={"component": "audio", "event": "stream_outer_handler_error"}
                )
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
                logger.debug(f"metrics increment failed (audio stream_outer_handler_error): error={m_err}")
    finally:
        try:
            await websocket.close()
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"WebSocket close failed: error={e}")
            try:
                increment_counter("app_warning_events_total", labels={"component": "audio", "event": "ws_close_failed"})
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        _idle_timeout = None

    aio = _shim_asyncio()
    wait_for = getattr(aio, "wait_for", asyncio.wait_for)
    iscoroutine = getattr(aio, "iscoroutine", asyncio.iscoroutine)

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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        _outer_stream = None

    try:
        _hdrs = websocket.headers or {}
        request_id = (
            _hdrs.get("x-request-id")
            or _hdrs.get("X-Request-Id")
            or (websocket.query_params.get("request_id") if hasattr(websocket, "query_params") else None)
            or str(uuid4())
        )
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        request_id = str(uuid4())
    try:
        logger.info(f"Audio chat WS connected: request_id={request_id}")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"Audio chat WS connection logging failed: {exc}")

    reg = _shim_get_metrics_registry()

    def _policy_close_code() -> int:
        flag = str(os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    # Authenticate (parity with STT/WS TTS)
    auth_ok, jwt_user_id = await _shim_audio_ws_authenticate(
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
            ok_stream, msg_stream = await _can_start_stream(user_id_for_usage)
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
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
                allow, remaining_after = await _check_daily_minutes_allow(user_id_for_usage, minutes_chunk)
                if allow and remaining_after is not None:
                    remaining_minutes_snapshot = float(remaining_after)
            except EXPECTED_DB_EXC as e:
                logger.warning(
                    f"_check_daily_minutes_allow failed during streaming; temporarily allowing "
                    f"(bounded fail-open). user_id={user_id_for_usage}, error={e}"
                )
                allow = True
                failopen_remaining -= minutes_chunk
                try:
                    increment_counter(
                        "audio_failopen_minutes_total", value=float(minutes_chunk), labels={"reason": "db_check"}
                    )
                    increment_counter("audio_failopen_events_total", labels={"reason": "db_check"})
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:  # noqa: BLE001
                    logger.debug(f"metrics increment failed (audio_chat_failopen_db_check): error={m_err}")
                deducted = True
                if failopen_remaining <= 0:
                    try:
                        increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_check"})
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:  # noqa: BLE001
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
                await _add_daily_minutes(user_id_for_usage, minutes_chunk)
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
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
                        logger.debug(f"metrics increment failed (audio_chat_failopen_db_record): error={m_err}")
                    if failopen_remaining <= 0:
                        try:
                            increment_counter("audio_failopen_cap_exhausted_total", labels={"reason": "db_record"})
                        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as m_err:
                            logger.debug(
                                f"metrics increment failed (audio_chat_failopen_cap_db_record): error={m_err}"
                            )
                        raise QuotaExceeded("daily_minutes") from None

        async def _on_heartbeat() -> None:
            try:
                await _heartbeat_stream(user_id_for_usage)  # type: ignore[arg-type]
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as _hb_e:
                logger.debug(f"Heartbeat failed for user_id={user_id_for_usage}: {_hb_e}")

        # Parse initial config
        try:
            raw_cfg = await wait_for(websocket.receive_text(), timeout=15.0)
            cfg_data = json.loads(raw_cfg)
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
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
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                    logger.debug(f"Invalid min_partial_duration value in audio chat config: {exc}")
            if "language" in stt_cfg:
                config.language = stt_cfg.get("language")
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as cfg_exc:
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
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
            tts_speed = 1.0
        response_format = tts_cfg.get("format") or tts_cfg.get("response_format") or "pcm"
        tts_model = tts_cfg.get("model", "kokoro")
        tts_voice = tts_cfg.get("voice", "af_heart")
        tts_provider = tts_cfg.get("provider")
        tts_extra_params = tts_cfg.get("extra_params") if isinstance(tts_cfg.get("extra_params"), dict) else None

        # Initialize STT transcriber + VAD gate
        try:
            TranscriberCls = _shim_transcriber_cls()
            transcriber = TranscriberCls(config)
            transcriber.initialize()
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
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
            payload: dict[str, Any] = {
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
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:
                logger.debug(f"audio.chat.stream VAD warning send failed: {send_exc}")

        if config.enable_vad:
            try:
                SileroCls = _shim_silero_cls()
                turn_detector = SileroCls(
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
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as vad_exc:
                logger.debug(f"VAD init failed: {vad_exc}")
                turn_detector = None

        chat_history: list[dict[str, Any]] = []
        if session_id:
            try:
                chat_history.append({"role": "system", "content": f"session:{session_id}"})
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
                chat_history = []

        def _action_hint() -> Optional[str]:
            try:
                if metadata and isinstance(metadata, dict) and metadata.get("action"):
                    return str(metadata.get("action"))
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                logger.debug(f"Failed to read action hint from metadata: {exc}")
            try:
                if llm_extra_params and isinstance(llm_extra_params, dict) and llm_extra_params.get("action"):
                    return str(llm_extra_params.get("action"))
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                logger.debug(f"Failed to read action hint from llm_extra_params: {exc}")
            return None

        async def _maybe_run_action(transcript_text: str) -> Optional[dict[str, Any]]:
            action_name = _action_hint()
            if not action_name:
                return None
            try:
                enabled = getattr(speech_chat_service, "_actions_enabled", lambda: False)()
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
                enabled = False
            if not enabled:
                return None

            user_obj = SimpleNamespace(id=user_id_for_usage)
            try:
                return await speech_chat_service._execute_action(action_name, transcript_text, user_obj)
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
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

        async def _stream_llm(transcript_text: str) -> tuple[str, Optional[str], Optional[dict[str, Any]]]:
            nonlocal chat_history
            def _fallback_resolver(name: str) -> Optional[str]:
                try:
                    return _shim_get_api_keys().get(name)
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
                    llm_stream = await _shim_chat_api_call_async(
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
                    if iscoroutine(stream_candidate):
                        try:
                            llm_stream = await stream_candidate
                        except NotImplementedError:
                            llm_stream = await _shim_chat_api_call_async(
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
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
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

            deltas: list[str] = []
            finish_reason: Optional[str] = None
            usage_payload: Optional[dict[str, Any]] = None

            async for raw_line in _iter_stream_lines(llm_stream):
                try:
                    line_str = (
                        raw_line.decode("utf-8", errors="ignore")
                        if isinstance(raw_line, (bytes, bytearray))
                        else str(raw_line)
                    )
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
                    content = delta.get("content") or delta.get("text") if isinstance(delta, dict) else None
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
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
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

            tts_service = await _shim_get_tts_service()

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
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:
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
                        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:
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
                    asyncio_module=aio,
                )
            finally:
                if _outer_stream:
                    try:
                        await _outer_stream.send_json({"type": "tts_done"})
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:
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
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
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
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                        logger.debug(f"Failed to append action_result to chat_history: {exc}")
                    if _outer_stream:
                        await _outer_stream.send_json({"type": "action_result", **action_result})
                await _stream_tts(assistant_text, final_emit_at)
            finally:
                try:
                    transcriber.reset()
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                    logger.debug(f"audio.chat.stream transcriber.reset() failed in finalize_turn: {exc}")
                processing_turn = False

        try:
            while True:
                raw_msg = await websocket.receive_text()
                try:
                    if _outer_stream:
                        _outer_stream.mark_activity()
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                    logger.debug(f"audio.chat.stream outer_stream.mark_activity failed: {exc}")
                try:
                    data = json.loads(raw_msg)
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
                        seconds = _bytes_to_seconds(len(audio_bytes), int(config.sample_rate or 16000))
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
                            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:
                                logger.debug(
                                    f"WebSocket send_json quota error failed (audio.chat.stream): error={send_exc}"
                                )
                        try:
                            await websocket.close(code=_policy_close_code(), reason="quota_exceeded")
                        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as close_exc:
                            logger.debug(
                                f"WebSocket close (quota case) failed (audio.chat.stream): error={close_exc}"
                            )
                        break

                    try:
                        await _on_heartbeat()
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as hb_exc:
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
                    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
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
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
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
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:  # noqa: BLE001
                logger.debug(f"audio.chat.stream failed to send internal_error frame: {send_exc}")
    finally:
        if acquired_stream:
            try:
                await _finish_stream(user_id_for_usage)
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
                logger.debug(
                    f"Failed to release streaming quota slot (audio.chat.stream): "
                    f"user_id={user_id_for_usage}, error={exc}"
                )
        try:
            if _outer_stream:
                await _outer_stream.stop()
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
            logger.debug(f"audio.chat.stream outer_stream.stop failed: {exc}")
        try:
            await websocket.close()
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        _idle_timeout = None

    aio = _shim_asyncio()
    wait_for = getattr(aio, "wait_for", asyncio.wait_for)

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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        request_id = str(uuid4())
    try:
        logger.info(f"TTS WS connected: request_id={request_id}")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"TTS WS connection logging failed: {exc}")

    def _policy_close_code() -> int:
        flag = str(os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    # Authenticate (parity with STT WS)
    auth_ok, jwt_user_id = await _shim_audio_ws_authenticate(
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
            ok_stream, msg_stream = await _can_start_stream(user_id_for_usage)
            if not ok_stream:
                if _outer_stream:
                    await _outer_stream.send_json(
                        {"type": "error", "message": msg_stream or "Concurrent audio streams limit reached"}
                    )
                await websocket.close(code=_policy_close_code())
                return
            acquired_stream = True
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
            if _outer_stream:
                await _outer_stream.send_json(
                    {"type": "error", "message": "Unable to evaluate audio stream quota or concurrency"}
                )
            await websocket.close(code=_policy_close_code())
            return

        # Parse prompt frame
        try:
            prompt_message = await wait_for(websocket.receive_text(), timeout=10.0)
            prompt_data = json.loads(prompt_message)
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
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
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as send_exc:
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
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
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
        reg = _shim_get_metrics_registry()
        tts_service = await _shim_get_tts_service()

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
            asyncio_module=aio,
        )
    finally:
        if acquired_stream:
            try:
                await _finish_stream(user_id_for_usage)
            except EXPECTED_DB_EXC as e:
                logger.debug(
                    f"Failed to release streaming quota slot (audio.stream.tts): "
                    f"user_id={user_id_for_usage}, error={e}"
                )
        try:
            if _outer_stream:
                await _outer_stream.done()
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as outer_exc:
            try:
                await websocket.close()
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as close_exc:
                logger.debug(
                    f"audio.stream.tts websocket close failed after _outer_stream.done error: "
                    f"outer_error={outer_exc}, close_error={close_exc}"
                )


@ws_router.websocket("/stream/tts/realtime")
async def websocket_tts_realtime(
    websocket: WebSocket,
    token: Optional[str] = Query(None),  # noqa: ARG001 - kept for parity
):
    """
    WebSocket realtime TTS endpoint: accepts streaming text frames and streams audio bytes.

    Client frames:
      - type=config: set provider/model/voice/format/speed/lang/extra_params/auto_flush_ms/auto_flush_tokens
      - type=text:   text delta (fields: delta | text | input)
      - type=commit: flush buffered text to synthesis
      - type=final:  flush and close session

    Server frames:
      - JSON status/warning/error frames
      - Binary audio frames for synthesized audio
    """
    await websocket.accept()

    try:
        _raw_idle = os.getenv("AUDIO_WS_IDLE_TIMEOUT_S") or os.getenv("STREAM_IDLE_TIMEOUT_S")
        _idle_timeout = float(_raw_idle) if _raw_idle else None
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        _idle_timeout = None

    aio = _shim_asyncio()
    wait_for = getattr(aio, "wait_for", asyncio.wait_for)
    TimeoutError = getattr(aio, "TimeoutError", asyncio.TimeoutError)
    create_task = getattr(aio, "create_task", asyncio.create_task)

    _outer_stream = None
    try:
        from tldw_Server_API.app.core.Streaming.streams import WebSocketStream as _WSStream

        _outer_stream = _WSStream(
            websocket,
            heartbeat_interval_s=None,
            compat_error_type=True,
            close_on_done=True,
            idle_timeout_s=_idle_timeout,
            labels={"component": "audio", "endpoint": "audio_tts_realtime_ws"},
        )
        await _outer_stream.start()
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        _outer_stream = None

    try:
        _hdrs = websocket.headers or {}
        request_id = (
            _hdrs.get("x-request-id")
            or _hdrs.get("X-Request-Id")
            or (websocket.query_params.get("request_id") if hasattr(websocket, "query_params") else None)
            or str(uuid4())
        )
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        request_id = str(uuid4())

    def _policy_close_code() -> int:
        flag = str(os.getenv("AUDIO_WS_QUOTA_CLOSE_1008", "0")).strip().lower()
        return 1008 if flag in {"1", "true", "yes", "on"} else 4003

    async def _send_json(payload: dict[str, Any]) -> None:
        if _outer_stream:
            await _outer_stream.send_json(payload)
        else:
            await websocket.send_json(payload)

    done_sent = False
    error_sent = False

    def _allowed_formats_for(provider_name: Optional[str]) -> set[str]:
        try:
            from tldw_Server_API.app.core.TTS.tts_validation import ProviderLimits

            limits = ProviderLimits.get_limits(str(provider_name).lower()) if provider_name else ProviderLimits.get_limits("default")
            return set(limits.get("valid_formats", {"pcm", "wav", "mp3"}))
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
            return {"pcm", "wav", "mp3", "opus", "flac"}

    async def _send_error(code: str, message: str, *, close: bool = False, close_code: Optional[int] = None) -> None:
        nonlocal error_sent
        payload = {
            "type": "error",
            "code": code,
            "message": message,
            "error_type": code,
            "request_id": request_id,
            "data": {"request_id": request_id},
        }
        if _outer_stream:
            await _outer_stream.send_json(payload)
        else:
            await websocket.send_json(payload)
        error_sent = True
        if not close:
            return
        if close_code is None:
            if code == "quota_exceeded":
                close_code = _policy_close_code()
            else:
                try:
                    close_code = _outer_stream._map_close_code(code) if _outer_stream else 1011
                except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
                    close_code = 1011
        with contextlib.suppress(_AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS):
            await websocket.close(code=close_code)

    auth_ok, jwt_user_id = await _shim_audio_ws_authenticate(
        websocket,
        _outer_stream,
        endpoint_id="audio.stream.tts.realtime",
        ws_path="/api/v1/audio/stream/tts/realtime",
    )
    if not auth_ok:
        return

    if is_multi_user_mode() and jwt_user_id is not None:
        user_id_for_usage = int(jwt_user_id)
    else:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings

        _s = _get_settings()
        user_id_for_usage = getattr(_s, "SINGLE_USER_FIXED_ID", 1)

    acquired_stream = False
    session = None
    sender_task: Optional[asyncio.Task] = None

    def _coerce_float(val: Any, default: float) -> float:
        try:
            return float(val)
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
            return default

    def _coerce_int(val: Any, default: int) -> int:
        try:
            return int(val)
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
            return default

    try:
        try:
            ok_stream, msg_stream = await _can_start_stream(user_id_for_usage)
            if not ok_stream:
                await _send_error("quota_exceeded", msg_stream or "Concurrent audio streams limit reached", close=False)
                await websocket.close(code=_policy_close_code())
                return
            acquired_stream = True
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
            await _send_error("quota_error", "Unable to evaluate audio stream quota or concurrency", close=False)
            await websocket.close(code=_policy_close_code())
            return

        # Read initial config or text frame
        try:
            raw_msg = await wait_for(websocket.receive_text(), timeout=10.0)
            first = json.loads(raw_msg)
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"TTS realtime WS initial frame parse failed: {exc}")
            await _send_error("bad_request", "Initial config or text frame required", close=False)
            await websocket.close(code=4400)
            return

        msg_type = (first.get("type") or "").lower()
        if msg_type not in {"config", "prompt", "text"}:
            await _send_error("bad_request", "First frame must be type=config, prompt, or text", close=False)
            await websocket.close(code=4400)
            return

        # Defaults
        default_provider = "vibevoice_realtime"
        default_model = "vibevoice-realtime-0.5b"
        default_voice = "default"
        default_format = "pcm"
        default_speed = 1.0
        default_auto_flush_ms = _coerce_int(os.getenv("TTS_REALTIME_AUTO_FLUSH_MS"), 600)
        default_auto_flush_tokens = _coerce_int(os.getenv("TTS_REALTIME_AUTO_FLUSH_TOKENS"), 60)

        provider_hint = first.get("provider") or default_provider
        model = first.get("model") or default_model
        voice = first.get("voice") or default_voice
        response_format = first.get("format") or first.get("response_format") or default_format
        response_format = str(response_format).lower()
        speed = _coerce_float(first.get("speed", default_speed), default_speed)
        lang_code = first.get("lang") or first.get("lang_code")
        extra_params = first.get("extra_params")
        if extra_params is not None and not isinstance(extra_params, dict):
            extra_params = None

        auto_flush_ms = _coerce_int(first.get("auto_flush_ms", default_auto_flush_ms), default_auto_flush_ms)
        auto_flush_tokens = _coerce_int(first.get("auto_flush_tokens", default_auto_flush_tokens), default_auto_flush_tokens)
        if auto_flush_ms < 0:
            auto_flush_ms = 0
        if auto_flush_tokens < 0:
            auto_flush_tokens = 0

        allowed_formats = _allowed_formats_for(str(provider_hint) if provider_hint else None)
        if response_format not in allowed_formats:
            await _send_error("bad_request", f"Unsupported format '{response_format}'")
            await websocket.close(code=4400)
            return

        tts_service = await _shim_get_tts_service()
        config = RealtimeSessionConfig(
            model=str(model),
            voice=str(voice),
            response_format=str(response_format),
            speed=float(speed),
            lang_code=lang_code,
            extra_params=extra_params,
            provider=str(provider_hint) if provider_hint else None,
        )
        handle = await tts_service.open_realtime_session(
            config=config,
            provider_hint=str(provider_hint) if provider_hint else None,
            route="audio.stream.tts.realtime",
            user_id=user_id_for_usage,
        )
        session = handle.session
        if handle.provider:
            provider_allowed = _allowed_formats_for(handle.provider)
            if response_format not in provider_allowed:
                await _send_error(
                    "bad_request",
                    f"Unsupported format '{response_format}' for provider '{handle.provider}'",
                    close=True,
                    close_code=4400,
                )
                with contextlib.suppress(_AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS):
                    await session.finish()
                return

        await _send_json(
            {
                "type": "ready",
                "provider": handle.provider or provider_hint,
                "format": response_format,
                "sample_rate": 24000,
                "request_id": request_id,
            }
        )
        if handle.warning:
            await _send_json({"type": "warning", "message": handle.warning, "request_id": request_id})

        async def _audio_sender() -> None:
            try:
                async for chunk in session.audio_stream():
                    if not chunk:
                        continue
                    await websocket.send_bytes(chunk)
                    if _outer_stream:
                        _outer_stream.mark_activity()
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"TTS realtime audio sender failed: {exc}")

        sender_task = create_task(_audio_sender())

        # Handle the initial frame as text if provided
        initial_text = first.get("delta") or first.get("text") or first.get("input")
        buffered_tokens = 0
        buffered_chars = 0
        last_input_ts: Optional[float] = None

        if isinstance(initial_text, str) and initial_text:
            await session.push_text(initial_text)
            buffered_chars += len(initial_text)
            buffered_tokens += len(initial_text.split())
            last_input_ts = time.monotonic()

        while True:
            timeout = None
            if auto_flush_ms and buffered_chars > 0:
                now = time.monotonic()
                elapsed = now - (last_input_ts or now)
                remaining = (auto_flush_ms / 1000.0) - elapsed
                timeout = max(0.0, remaining)

            try:
                raw_msg = await wait_for(websocket.receive_text(), timeout=timeout)
            except TimeoutError:
                if buffered_chars > 0:
                    await session.commit()
                    buffered_chars = 0
                    buffered_tokens = 0
                    last_input_ts = None
                continue

            try:
                data = json.loads(raw_msg)
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
                await _send_error("bad_request", "Invalid JSON frame", close=False)
                await websocket.close(code=4400)
                return

            msg_type = (data.get("type") or "").lower()
            if msg_type in {"text", "input"}:
                delta = data.get("delta") or data.get("text") or data.get("input")
                if not isinstance(delta, str) or not delta:
                    continue
                await session.push_text(delta)
                buffered_chars += len(delta)
                buffered_tokens += len(delta.split())
                last_input_ts = time.monotonic()
                if auto_flush_tokens and buffered_tokens >= auto_flush_tokens:
                    await session.commit()
                    buffered_chars = 0
                    buffered_tokens = 0
                    last_input_ts = None
            elif msg_type == "commit":
                await session.commit()
                buffered_chars = 0
                buffered_tokens = 0
                last_input_ts = None
            elif msg_type == "final":
                await session.finish()
                break
            elif msg_type == "config":
                await _send_json({"type": "warning", "message": "Config updates are ignored after session start."})
            elif msg_type == "ping":
                await _send_json({"type": "pong"})
            else:
                await _send_json({"type": "warning", "message": f"Unknown message type '{msg_type}'"})

        if sender_task:
            await sender_task
        if getattr(session, "error", None):
            await _send_error("internal_error", "Realtime TTS session failed", close=True)
        if not error_sent:
            if _outer_stream:
                await _outer_stream.done()
            else:
                await _send_json({"type": "done"})
            done_sent = True
    except WebSocketDisconnect:
        logger.info("TTS realtime WS disconnected")
    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"TTS realtime WS error: {exc}", exc_info=True)
        with contextlib.suppress(_AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS):
            await _send_error("internal_error", "Internal error", close=True)
    finally:
        if session is not None:
            with contextlib.suppress(_AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS):
                await session.finish()
        if sender_task and not sender_task.done():
            sender_task.cancel()
            with contextlib.suppress(_AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS):
                await sender_task
        if acquired_stream:
            try:
                await _finish_stream(user_id_for_usage)
            except EXPECTED_DB_EXC as e:
                logger.debug(
                    f"Failed to release streaming quota slot (audio.stream.tts.realtime): "
                    f"user_id={user_id_for_usage}, error={e}"
                )
        try:
            if _outer_stream and not done_sent and not error_sent:
                await _outer_stream.done()
        except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as outer_exc:
            try:
                await websocket.close()
            except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS as close_exc:
                logger.debug(
                    "audio.stream.tts.realtime websocket close failed after _outer_stream.done error: "
                    f"outer_error={outer_exc}, close_error={close_exc}"
                )


@router.get(
    "/stream/status",
    response_model=StreamingStatusResponse,
    summary="Check streaming transcription availability",
)
async def streaming_status():
    """
    Report availability and capabilities of the streaming transcription WebSocket endpoint.

    Returns:
        StreamingStatusResponse with the following keys:
          - `status` (str): "available" if at least one streaming model is present, "unavailable" otherwise, or "error" on failure.
          - `available_models` (list[str]): Names of detected streaming model variants (e.g., "parakeet-mlx", "parakeet-standard", "parakeet-onnx").
          - `websocket_endpoint` (str): URL path of the streaming transcription WebSocket.
          - `supported_features` (dict): Feature flags indicating supported streaming capabilities (boolean values).
    """
    try:
        # Check available models
        available_models = []

        import importlib.util as _importlib_util

        # Check for MLX variant
        if _importlib_util.find_spec(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_MLX"
        ):
            available_models.append("parakeet-mlx")

        # Check for standard variant (NeMo)
        if _importlib_util.find_spec(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo"
        ):
            available_models.append("parakeet-standard")

        # Check for ONNX variant
        if _importlib_util.find_spec("onnxruntime") and _importlib_util.find_spec(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_ONNX"
        ):
            available_models.append("parakeet-onnx")

        return {
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

    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        logger.error("Error checking streaming status", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "An internal error occurred. Please try again later."},
        )


@router.get(
    "/stream/limits",
    response_model=StreamingLimitsResponse,
    summary="Get user's streaming quota and usage",
)
async def streaming_limits(
    request: Request,
    current_user: User = Depends(get_request_user),
):
    """
    Return the current user's streaming quota and usage summary.

    Returns:
        StreamingLimitsResponse with the following keys:
            - user_id (str): The user's identifier.
            - tier (str): The user's tier name (e.g., "free").
            - limits (dict): The resolved limit values (e.g., daily_minutes, concurrent_streams, concurrent_jobs, max_file_size_mb).
            - used_today_minutes (float): Minutes already used today (0.0 if unavailable).
            - remaining_minutes (float|None): Minutes remaining today (0.0 if none left, `None` if unknown/unbounded).
            - active_streams (int): Number of currently active streams (0 if unavailable).
            - _can_start_stream (bool): Whether the user may start another stream given current active streams and concurrent_streams limit.
    """
    # Correlate logs with request_id if available
    rid = ensure_request_id(request) if request is not None else None
    try:
        limits = await _get_limits_for_user(current_user.id)
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
        used_minutes = await _get_daily_minutes_used(current_user.id)
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
        active_streams = await _active_streams_count(current_user.id)
    except EXPECTED_REDIS_EXC as e:
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="audio").warning(
            "Failed to get active streams for user %s, falling back to 0: %s", current_user.id, e
        )
        active_streams = 0
    try:
        tier = await _get_user_tier(current_user.id)
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
    return {
        "user_id": current_user.id,
        "tier": tier,
        "limits": limits,
        "used_today_minutes": used_minutes,
        "remaining_minutes": remaining_minutes,
        "active_streams": active_streams,
        "can_start_stream": can_start,
        "_can_start_stream": can_start,
    }


@router.post(
    "/stream/test",
    response_model=StreamingTestResponse,
    summary="Test streaming transcription setup",
)
async def test_streaming():
    """
    Run a lightweight end-to-end check of the streaming transcription pipeline using a short generated audio sample.

    Performs a minimal initialization of the Parakeet streaming transcriber, sends a short synthetic audio chunk, and returns the transcriber's immediate response or a buffering status.

    Returns:
        StreamingTestResponse: On success, a JSON object with keys:
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
        import base64

        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
            UnifiedStreamingConfig,
            UnifiedStreamingTranscriber,
        )

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

        return {
            "status": "success",
            "test_passed": True,
            "message": "Streaming transcription is working",
            "test_result": result if result else "Buffer accumulating",
        }

    except _AUDIO_STREAMING_NONCRITICAL_EXCEPTIONS:
        logger.error("Streaming test failed", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "test_passed": False,
                "message": "An internal error occurred during the streaming test. Please contact support if the problem persists.",
            },
        )
