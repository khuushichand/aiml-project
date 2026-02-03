# audio_tts.py
# Description: Audio TTS endpoints and helpers.
import base64
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from loguru import logger
from starlette import status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, require_token_scope
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest
from tldw_Server_API.app.core.Audio.error_payloads import _http_error_detail
from tldw_Server_API.app.core.Audio.tts_service import _raise_for_tts_error
from tldw_Server_API.app.core.AuthNZ.exceptions import QuotaExceededError, StorageError
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2, get_tts_service_v2

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

    if not hasattr(audio_shim, name):
        raise NameError(name)
    return getattr(audio_shim, name)


async def get_tts_service() -> TTSServiceV2:
    """Get the V2 TTS service instance."""
    return await get_tts_service_v2()


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
    request_data: OpenAISpeechRequest,
    request: Request,
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
    """
    request_id = ensure_request_id(request)

    provider_hint = _audio_shim_attr("_sanitize_speech_request")(request_data, request_id=request_id)

    tts_provider_hint = provider_hint
    user_id_int, tts_overrides, byok_tts_resolution = await _audio_shim_attr("_resolve_tts_byok")(
        provider_hint=tts_provider_hint,
        current_user=current_user,
        request=request,
    )
    logger.info(
        "Received speech request: model=%s, voice=%s, format=%s, request_id=%s",
        request_data.model,
        request_data.voice,
        request_data.response_format,
        request_id,
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

    # Determine Content-Type
    content_type_map = {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "pcm": "audio/L16; rate=24000; channels=1",
    }
    content_type = content_type_map.get(request_data.response_format)
    if not content_type:
        logger.warning(f"Unsupported response format: {request_data.response_format}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported response_format: "
                f"{request_data.response_format}. Supported formats are: {', '.join(content_type_map.keys())}"
            ),
        )
    if request_data.stream and request_data.return_download_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="return_download_link requires stream=false",
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
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "X-Request-Id": request_id,
            },
        )
    # Non-streaming mode: accumulate chunks and return a single response
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

    if request_data.return_download_link:
        try:
            file_record = await _audio_shim_attr("save_and_register_tts_audio")(
                user_id=user_id_int,
                audio_bytes=all_audio_bytes,
                audio_format=request_data.response_format,
                original_text=request_data.input,
                voice_name=request_data.voice,
                model_name=request_data.model,
                check_quota=True,
            )
            file_id = file_record.get("id")
            if file_id:
                headers["X-Download-Path"] = f"/api/v1/storage/files/{file_id}/download"
                headers["X-Generated-File-Id"] = str(file_id)
        except QuotaExceededError as exc:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail=str(exc),
            ) from exc
        except StorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

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
    provider_hint = _audio_shim_attr("_sanitize_speech_request")(request_data, request_id=request_id)
    tts_provider_hint = provider_hint
    user_id_int, tts_overrides, byok_tts_resolution = await _audio_shim_attr("_resolve_tts_byok")(
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

    if hasattr(request_data, "stream"):
        try:
            request_data.stream = False
        except (AttributeError, TypeError) as exc:
            logger.warning(
                "audio.speech.metadata: failed to set request_data.stream=False (model={}, request_id={}): {}",
                getattr(request_data, "model", None),
                request_id,
                exc,
            )
    else:
        logger.warning(
            "audio.speech.metadata: request_data missing stream attribute (model={}, request_id={})",
            getattr(request_data, "model", None),
            request_id,
        )

    try:
        speech_iter = tts_service.generate_speech(
            request_data,
            provider=tts_provider_hint,
            fallback=True,
            provider_overrides=tts_overrides,
            voice_to_voice_route="audio.speech.metadata",
            user_id=user_id_int,
            metadata_only=True,
        )
    except Exception as exc:
        _raise_for_tts_error(exc, request_id)

    try:
        try:
            await speech_iter.__anext__()
        except StopAsyncIteration:
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
    provider: Optional[str] = None,
    tts_service: TTSServiceV2 = Depends(get_tts_service),
):
    """
    List available voices from TTS providers.

    - If `provider` is specified, returns voices only for that provider.
    - Otherwise returns a mapping of provider name to voice lists.
    """
    try:
        all_voices = await tts_service.list_voices()
        if provider:
            key = provider.lower()
            if key in all_voices:
                return {key: all_voices[key]}
            raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found or unavailable")
        return all_voices
    except HTTPException:
        raise
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
                logger.info(f"Resetting metrics for provider: {provider}")
                return {"message": f"Metrics reset for provider {provider}"}
            logger.info("Resetting all TTS metrics")
            return {"message": "All TTS metrics reset"}
        return {"message": "Metrics not available"}
    except Exception as e:
        logger.error(f"Error resetting metrics: {e}", exc_info=True)
        request_id = ensure_request_id(request)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_http_error_detail("Failed to reset metrics", request_id, exc=e),
        )
