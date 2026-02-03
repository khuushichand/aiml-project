import asyncio
import json
import os
from collections.abc import Awaitable
from typing import Any, Callable, Optional

from fastapi import WebSocket
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import is_multi_user_mode
from tldw_Server_API.app.core.Metrics.metrics_manager import (
    MetricDefinition,
    MetricType,
    get_metrics_registry,
)


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


async def _stream_tts_to_websocket(
    *,
    websocket: WebSocket,
    speech_req: Any,
    tts_service: Any,
    provider: Optional[str],
    outer_stream: Optional[Any],
    reg: Any,
    route: str,
    component_label: str,
    voice_to_voice_start: Optional[float] = None,
    error_handler: Optional[Callable[[Exception], Awaitable[None]]] = None,
    asyncio_module: Optional[Any] = None,
) -> None:
    """
    Shared helper to stream TTS audio chunks over a WebSocket with backpressure and metrics.

    This consolidates the producer/consumer queue pattern used by both the
    audio.chat.stream and audio.stream.tts WebSocket handlers.
    """
    aio = asyncio_module or asyncio
    Queue = getattr(aio, "Queue", asyncio.Queue)
    QueueFull = getattr(aio, "QueueFull", asyncio.QueueFull)
    create_task = getattr(aio, "create_task", asyncio.create_task)
    wait = getattr(aio, "wait", asyncio.wait)
    FIRST_EXCEPTION = getattr(aio, "FIRST_EXCEPTION", asyncio.FIRST_EXCEPTION)
    queue: asyncio.Queue[Optional[bytes]] = Queue(maxsize=8)
    provider_label = (provider or getattr(speech_req, "model", None) or "default").lower()
    underrun_labels = {"provider": provider_label}
    error_labels = {"component": component_label, "provider": provider_label}

    async def _producer() -> None:
        try:
            generate_kwargs: dict[str, Any] = {
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
                except QueueFull:
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

    producer_task = create_task(_producer())
    consumer_task = create_task(_consumer())

    try:
        _done, pending = await wait(
            {producer_task, consumer_task},
            return_when=FIRST_EXCEPTION,
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
            from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
            from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
            from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
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
                from tldw_Server_API.app.core.AuthNZ.ip_allowlist import resolve_client_ip
                from tldw_Server_API.app.core.AuthNZ.quotas import increment_and_check_api_key_quota
                from tldw_Server_API.app.core.AuthNZ.settings import get_settings

                api_mgr = await get_api_key_manager()
                client_ip = resolve_client_ip(websocket, get_settings())
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
    from tldw_Server_API.app.core.AuthNZ.ip_allowlist import resolve_client_ip
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    expected_key = settings.SINGLE_USER_API_KEY
    client_ip = resolve_client_ip(websocket, settings)

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
