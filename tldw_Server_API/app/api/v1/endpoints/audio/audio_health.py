# audio_health.py
# Description: Audio health endpoints.
import asyncio
from dataclasses import asdict, is_dataclass
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from starlette import status

from tldw_Server_API.app.api.v1.endpoints.audio.audio_tts import get_tts_service
from tldw_Server_API.app.core.Audio.error_payloads import _http_error_detail
from tldw_Server_API.app.core.Audio.transcription_service import _map_openai_audio_model_to_whisper
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id
from tldw_Server_API.app.core.TTS.circuit_breaker import build_qwen_runtime_breaker_key
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat

router = APIRouter(
    tags=["Audio"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limit exceeded"},
    },
)


def _build_internal_health_request(path: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
    }
    return Request(scope)


def _serialize_tts_caps_for_health(tts_service: TTSServiceV2, caps: Any) -> Any:
    if caps is None:
        return None
    serializer = getattr(tts_service, "_serialize_capabilities", None)
    if callable(serializer):
        try:
            return serializer(caps)
        except Exception as exc:
            logger.debug(f"TTS health capabilities serialization failed via service helper: {exc}")
    if isinstance(caps, dict):
        return dict(caps)
    try:
        dumped = model_dump_compat(caps)
        if isinstance(dumped, dict):
            return dumped
    except Exception as dump_error:
        logger.debug("TTS health capabilities model dump failed", exc_info=dump_error)
    try:
        if is_dataclass(caps):
            return asdict(caps)
    except Exception as dataclass_error:
        logger.debug("TTS health capabilities dataclass conversion failed", exc_info=dataclass_error)
    return None


@router.get("/health")
async def get_tts_health(request: Request, tts_service: TTSServiceV2 = Depends(get_tts_service)):
    """
    Get health status of TTS providers.
    """
    from datetime import datetime

    try:
        status_data = tts_service.get_status()
        if not isinstance(status_data, dict):
            logger.warning("TTS service returned non-mapping status; falling back to defaults")
            status_map = {}
        else:
            status_map = status_data

        capabilities = await tts_service.get_capabilities()
        if not isinstance(capabilities, dict):
            capabilities = {}
        provider_details = status_map.get("providers", {})
        if not isinstance(provider_details, dict):
            provider_details = {}
        capability_envelopes: list[dict[str, Any]] = []

        available_providers = status_map.get("available", 0)
        total_providers = status_map.get("total_providers", 0)

        factory = None
        try:
            from tldw_Server_API.app.core.TTS.adapter_registry import get_tts_factory

            factory = await get_tts_factory()
            registry = getattr(factory, "registry", None)
            list_caps = getattr(registry, "list_capabilities", None)
            if callable(list_caps):
                entries = list_caps(include_disabled=True)
                if asyncio.iscoroutine(entries):
                    entries = await entries
                if isinstance(entries, list):
                    for raw_entry in entries:
                        if not isinstance(raw_entry, dict):
                            continue
                        provider_name = str(raw_entry.get("provider") or "").strip()
                        if not provider_name:
                            continue
                        availability = str(raw_entry.get("availability") or "unknown").strip().lower() or "unknown"
                        serialized_caps = _serialize_tts_caps_for_health(tts_service, raw_entry.get("capabilities"))
                        metadata = {}
                        if isinstance(serialized_caps, dict):
                            metadata = dict(serialized_caps.get("metadata") or {})
                        runtime_name = metadata.get("runtime")
                        breaker_key = provider_name
                        if provider_name == "qwen3_tts" and runtime_name:
                            breaker_key = build_qwen_runtime_breaker_key(provider_name, str(runtime_name))
                        capability_envelopes.append(
                            {
                                "provider": provider_name,
                                "availability": availability,
                                "runtime": runtime_name,
                                "breaker_key": breaker_key,
                                "capabilities": serialized_caps,
                            }
                        )
                        if serialized_caps is not None and provider_name not in capabilities:
                            capabilities[provider_name] = serialized_caps
                        current_details = provider_details.get(provider_name)
                        if isinstance(current_details, dict):
                            current_details.setdefault("availability", availability)
                            current_details.setdefault("status", availability)
                            if runtime_name:
                                current_details.setdefault("runtime", runtime_name)
                            current_details.setdefault("breaker_key", breaker_key)
                        else:
                            provider_details[provider_name] = {
                                "status": availability,
                                "availability": availability,
                                "runtime": runtime_name,
                                "breaker_key": breaker_key,
                                "initialized": False,
                                "failed": availability == "failed",
                            }
        except Exception as envelope_exc:
            logger.debug(f"TTS health envelope enrichment failed: {envelope_exc}")

        if capability_envelopes:
            if not total_providers:
                total_providers = len(capability_envelopes)
            if not available_providers:
                available_providers = sum(
                    1 for entry in capability_envelopes if entry.get("availability") == "enabled"
                )

        health_status = "healthy" if available_providers > 0 else "unhealthy"

        health = {
            "status": health_status,
            "providers": {
                "total": total_providers,
                "available": available_providers,
                "details": provider_details,
            },
            "circuit_breakers": status_map.get("circuit_breakers", {}),
            "capabilities": capabilities,
            "capabilities_envelope": capability_envelopes,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            from tldw_Server_API.app.core.TTS.adapter_registry import TTSProvider

            if factory is None:
                from tldw_Server_API.app.core.TTS.adapter_registry import get_tts_factory

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


async def collect_setup_tts_health() -> dict[str, Any]:
    """Collect TTS health without going through the HTTP routing layer."""

    request = _build_internal_health_request("/api/v1/audio/health")
    try:
        tts_service = await get_tts_service()
        return await get_tts_health(request, tts_service)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
        message = detail.get("message")
        if not isinstance(message, str) or not message.strip():
            raw_error = detail.get("error")
            message = raw_error if isinstance(raw_error, str) else None
        if not isinstance(message, str) or not message.strip():
            message = "TTS health check failed"
        return {
            "status": "error",
            "providers": {"total": 0, "available": 0, "details": {}},
            "message": message,
            "error": detail,
            "status_code": exc.status_code,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("TTS setup health collection failed")
        request_id = ensure_request_id(request)
        payload = _http_error_detail("TTS health check failed", request_id, exc=exc)
        return {
            "status": "error",
            "providers": {"total": 0, "available": 0, "details": {}},
            **payload,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }


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
    """
    from datetime import datetime

    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as stt_lib
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files as audio_files

    request_id = ensure_request_id(request)
    raw_model = (model or "").strip()
    if not raw_model:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (
            resolve_default_transcription_model,
        )

        raw_model = resolve_default_transcription_model("whisper-1")
    provider_raw, _, _ = stt_lib.parse_transcription_model(raw_model)

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

    try:
        status_info = audio_files.check_transcription_model_status(resolved_model)
    except Exception:
        logger.exception("STT health: check_transcription_model_status failed")
        status_info = {
            "available": False,
            "message": "Failed to check model status.",
            "model": resolved_model,
        }

    health: dict[str, Any] = {
        "provider": provider_raw,
        "alias": raw_model,
        "model": status_info.get("model", resolved_model),
        "available": bool(status_info.get("available", False)),
        "usable": bool(status_info.get("usable", status_info.get("available", False))),
        "on_demand": bool(status_info.get("on_demand", False)),
        "message": status_info.get("message"),
        "estimated_size": status_info.get("estimated_size"),
        "timestamp": datetime.utcnow().isoformat(),
    }

    warm_info: dict[str, Any] = {}
    if warm and provider_raw == "whisper":
        device = getattr(stt_lib, "processing_choice", "cpu")
        try:
            stt_lib.get_whisper_model(resolved_model, device, check_download_status=False)
            warm_info = {"ok": True, "device": device}
            # Warm-up succeeded, so the model is ready to serve requests.
            health["available"] = True
            health["usable"] = True
            health["on_demand"] = False
            health["message"] = f"Model {resolved_model} is available and ready for use"
            health["estimated_size"] = None
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


async def collect_setup_stt_health(
    model: Optional[str] = None,
    *,
    warm: bool = False,
) -> dict[str, Any]:
    """Collect STT health without going through the HTTP routing layer."""

    request = _build_internal_health_request("/api/v1/audio/transcriptions/health")
    try:
        return await get_stt_health(request, model=model, warm=warm)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
        message = detail.get("message")
        if not isinstance(message, str) or not message.strip():
            raw_error = detail.get("error")
            message = raw_error if isinstance(raw_error, str) else None
        if not isinstance(message, str) or not message.strip():
            message = "Failed to collect STT health."
        return {
            "provider": None,
            "alias": model,
            "model": model,
            "available": False,
            "usable": False,
            "on_demand": False,
            "message": message,
            "error": detail,
            "status_code": exc.status_code,
        }
