from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional, Tuple

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from starlette.responses import JSONResponse, StreamingResponse

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.byok_config import merge_app_config_overrides
from tldw_Server_API.app.core.AuthNZ.byok_runtime import (
    record_byok_missing_credentials,
    resolve_byok_credentials,
)
from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import (
    get_override_credentials,
    validate_provider_override,
)
from tldw_Server_API.app.core.Chat.chat_service import resolve_provider_and_model
from tldw_Server_API.app.core.Chat.chat_service import resolve_provider_api_key
from tldw_Server_API.app.core.LLM_Calls.anthropic_messages import (
    anthropic_messages_to_openai,
    anthropic_tool_choice_to_openai,
    anthropic_tools_to_openai,
    openai_response_to_anthropic,
    openai_stream_to_anthropic,
)
from tldw_Server_API.app.core.LLM_Calls.provider_metadata import provider_requires_api_key
from tldw_Server_API.app.core.http_client import create_client as http_client_factory
from tldw_Server_API.app.core.config import loaded_config_data
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import DEFAULT_LLM_PROVIDER
from tldw_Server_API.app.api.v1.schemas.anthropic_messages import (
    AnthropicCountTokensRequest,
    AnthropicMessagesRequest,
)
from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async


router = APIRouter()
public_router = APIRouter()

MESSAGES_NATIVE_PROVIDERS = {"anthropic", "llama.cpp"}
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


def _config_default_llm_provider() -> Optional[str]:
    cfg = loaded_config_data
    def _extract(section: str) -> Optional[str]:
        try:
            data = cfg.get(section)
        except Exception:
            data = None
        if isinstance(data, dict):
            default_api = data.get("default_api")
            if isinstance(default_api, str):
                value = default_api.strip()
                if value:
                    return value
        return None
    return _extract("llm_api_settings") or _extract("API")


def _get_default_provider() -> str:
    cfg_default = _config_default_llm_provider()
    if cfg_default:
        return cfg_default
    env_val = os.getenv("DEFAULT_LLM_PROVIDER")
    if env_val:
        return env_val
    if os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes"}:
        return "local-llm"
    return DEFAULT_LLM_PROVIDER


def _resolve_messages_base_url(provider: str, app_config: Optional[Dict[str, Any]]) -> str:
    cfg = app_config or loaded_config_data
    if provider == "anthropic":
        base = None
        try:
            anth = cfg.get("anthropic_api")
        except Exception:
            anth = None
        if isinstance(anth, dict):
            base = anth.get("api_base_url")
        if not base:
            base = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        return str(base)
    if provider == "llama.cpp":
        base = None
        try:
            llama = cfg.get("llama_api")
        except Exception:
            llama = None
        if isinstance(llama, dict):
            base = llama.get("api_ip") or llama.get("api_base_url")
        if not base:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Llama.cpp API URL/IP is required but not configured.",
            )
        normalized = _normalize_llamacpp_base_url(str(base))
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Llama.cpp API URL/IP is required but not configured.",
            )
        return normalized
    raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not messages-native.")


def _join_messages_endpoint(base_url: str, suffix: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}{suffix}"
    return f"{base}/v1{suffix}"


def _normalize_llamacpp_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    lowered = normalized.lower()
    for suffix in ("/v1/chat/completions", "/chat/completions", "/completion"):
        if lowered.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def _resolve_provider_and_model_for_request(request_data: Any) -> Tuple[str, str]:
    _, metrics_model, selected_provider, selected_model, _debug = resolve_provider_and_model(
        request_data=request_data,
        metrics_default_provider=DEFAULT_LLM_PROVIDER,
        normalize_default_provider=_get_default_provider(),
    )
    provider = selected_provider
    model = selected_model or metrics_model or getattr(request_data, "model", None)
    return provider, model


def _fallback_resolver(name: str) -> Optional[str]:
    key_val, _ = resolve_provider_api_key(name, prefer_module_keys_in_tests=True)
    return key_val


def _apply_override_credentials(
    provider: str,
    app_config_override: Optional[Dict[str, Any]],
    *,
    uses_byok: bool,
) -> Optional[Dict[str, Any]]:
    override_creds = get_override_credentials(provider)
    if not override_creds or not override_creds.get("credential_fields") or uses_byok:
        return app_config_override

    credential_fields = override_creds.get("credential_fields") or {}
    if provider == "llama.cpp":
        base_url = credential_fields.get("base_url")
        if isinstance(base_url, str) and base_url.strip():
            try:
                merged = dict(app_config_override or dict(loaded_config_data))
            except Exception:
                merged = dict(app_config_override or {})
            llama_cfg = merged.get("llama_api")
            if not isinstance(llama_cfg, dict):
                llama_cfg = {}
            base_url = base_url.strip()
            llama_cfg["api_ip"] = base_url
            llama_cfg["api_base_url"] = base_url
            merged["llama_api"] = llama_cfg
            return merged

    try:
        base_config = app_config_override or dict(loaded_config_data)
    except Exception:
        base_config = app_config_override or {}
    return merge_app_config_overrides(
        base_config,
        provider,
        credential_fields,
    )


def _resolve_llamacpp_api_key(app_config: Optional[Dict[str, Any]]) -> Optional[str]:
    def _from_cfg(cfg: Any) -> Optional[str]:
        try:
            llama = cfg.get("llama_api")
        except Exception:
            llama = None
        if isinstance(llama, dict):
            key = llama.get("api_key")
            if isinstance(key, str) and key.strip():
                return key.strip()
        return None

    key = _from_cfg(app_config or loaded_config_data)
    if key:
        return key
    if app_config is not None and app_config is not loaded_config_data:
        return _from_cfg(loaded_config_data)
    return None


def _resolve_native_timeout(provider: str, app_config: Optional[Dict[str, Any]]) -> Optional[float]:
    cfg = app_config or loaded_config_data
    section = "anthropic_api" if provider == "anthropic" else "llama_api"
    default_timeout = 60.0 if provider == "anthropic" else 120.0
    try:
        section_cfg = cfg.get(section)
    except Exception:
        section_cfg = None
    if not isinstance(section_cfg, dict):
        return default_timeout
    raw = section_cfg.get("api_timeout")
    try:
        return float(raw)
    except Exception:
        return default_timeout


def _build_native_headers(
    provider: str,
    api_key: Optional[str],
    *,
    anthropic_version: Optional[str],
    anthropic_beta: Optional[str],
) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if provider == "anthropic":
        headers["x-api-key"] = api_key or ""
        headers["anthropic-version"] = anthropic_version or DEFAULT_ANTHROPIC_VERSION
        if anthropic_beta:
            headers["anthropic-beta"] = anthropic_beta
        return headers
    if provider == "llama.cpp":
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if anthropic_version:
            headers["anthropic-version"] = anthropic_version
        if anthropic_beta:
            headers["anthropic-beta"] = anthropic_beta
        return headers
    return headers


def _extract_stream_flag(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(raw)


def _build_openai_call_params(
    *,
    request_data: AnthropicMessagesRequest,
    provider: str,
    model: str,
    app_config: Optional[Dict[str, Any]],
    api_key: Optional[str],
) -> Dict[str, Any]:
    messages_payload, system_message = anthropic_messages_to_openai(
        [m.model_dump(exclude_none=True) for m in request_data.messages],
        request_data.system,
    )
    tools = anthropic_tools_to_openai(
        [t.model_dump(exclude_none=True) for t in request_data.tools]
    ) if request_data.tools else None
    tool_choice = anthropic_tool_choice_to_openai(request_data.tool_choice)

    call_params: Dict[str, Any] = {
        "api_provider": provider,
        "model": model,
        "messages": messages_payload,
        "system_message": system_message,
        "api_key": api_key,
        "app_config": app_config,
        "stream": _extract_stream_flag(request_data.stream),
        "temperature": request_data.temperature,
        "top_p": request_data.top_p,
        "top_k": request_data.top_k,
        "max_tokens": request_data.max_tokens,
        "stop": request_data.stop_sequences,
        "tools": tools,
        "tool_choice": tool_choice,
    }
    return call_params


def _prepare_native_payload(request_data: Any, *, model: str) -> Dict[str, Any]:
    payload = request_data.model_dump(exclude_none=True)
    payload.pop("api_provider", None)
    payload["model"] = model
    return payload


def _proxy_native_stream(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    *,
    timeout: Optional[float] = None,
) -> Iterable[bytes]:
    with http_client_factory(timeout=timeout) as client:
        with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_raw():
                if chunk:
                    yield chunk


async def _handle_messages(
    request_data: AnthropicMessagesRequest,
    *,
    current_user: User,
    request: Request,
    anthropic_version: Optional[str],
    anthropic_beta: Optional[str],
) -> JSONResponse | StreamingResponse:
    provider, model = _resolve_provider_and_model_for_request(request_data)
    override_error = validate_provider_override(provider, model)
    if override_error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=override_error)

    user_id_int = getattr(current_user, "id_int", None)
    if user_id_int is None:
        try:
            user_id_int = int(getattr(current_user, "id", None))
        except Exception:
            user_id_int = None

    byok_resolution = await resolve_byok_credentials(
        provider,
        user_id=user_id_int,
        request=request,
        fallback_resolver=_fallback_resolver,
    )
    api_key = byok_resolution.api_key
    app_config_override = byok_resolution.app_config
    app_config_override = _apply_override_credentials(
        provider,
        app_config_override,
        uses_byok=byok_resolution.uses_byok,
    )
    if provider == "llama.cpp" and not api_key:
        api_key = _resolve_llamacpp_api_key(app_config_override)

    if provider_requires_api_key(provider) and not api_key:
        record_byok_missing_credentials(provider, operation="messages")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "missing_provider_credentials",
                "message": f"Provider '{provider}' requires an API key. Please configure credentials.",
            },
        )

    if provider in MESSAGES_NATIVE_PROVIDERS:
        base_url = _resolve_messages_base_url(provider, app_config_override)
        url = _join_messages_endpoint(base_url, "/messages")
        payload = _prepare_native_payload(request_data, model=model)
        timeout = _resolve_native_timeout(provider, app_config_override)
        headers = _build_native_headers(
            provider,
            api_key,
            anthropic_version=anthropic_version,
            anthropic_beta=anthropic_beta,
        )
        stream = _extract_stream_flag(request_data.stream)
        if stream:
            return StreamingResponse(
                _proxy_native_stream(url, headers, payload, timeout=timeout),
                media_type="text/event-stream",
            )
        with http_client_factory(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return JSONResponse(data)

    # Non-native providers: convert to OpenAI-compatible request
    call_params = _build_openai_call_params(
        request_data=request_data,
        provider=provider,
        model=model,
        app_config=app_config_override,
        api_key=api_key,
    )

    stream = bool(call_params.get("stream"))
    if stream:
        stream_iter = await perform_chat_api_call_async(**call_params)
        return StreamingResponse(
            openai_stream_to_anthropic(stream_iter, model=model),
            media_type="text/event-stream",
        )

    response = await perform_chat_api_call_async(**call_params)
    if not isinstance(response, dict):
        raise HTTPException(status_code=502, detail="Upstream provider returned invalid response.")
    return JSONResponse(openai_response_to_anthropic(response, model=model))


async def _handle_count_tokens(
    request_data: AnthropicCountTokensRequest,
    *,
    current_user: User,
    request: Request,
    anthropic_version: Optional[str],
    anthropic_beta: Optional[str],
) -> JSONResponse:
    provider, model = _resolve_provider_and_model_for_request(request_data)
    override_error = validate_provider_override(provider, model)
    if override_error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=override_error)

    user_id_int = getattr(current_user, "id_int", None)
    if user_id_int is None:
        try:
            user_id_int = int(getattr(current_user, "id", None))
        except Exception:
            user_id_int = None

    byok_resolution = await resolve_byok_credentials(
        provider,
        user_id=user_id_int,
        request=request,
        fallback_resolver=_fallback_resolver,
    )
    api_key = byok_resolution.api_key
    app_config_override = byok_resolution.app_config
    app_config_override = _apply_override_credentials(
        provider,
        app_config_override,
        uses_byok=byok_resolution.uses_byok,
    )
    if provider == "llama.cpp" and not api_key:
        api_key = _resolve_llamacpp_api_key(app_config_override)

    if provider_requires_api_key(provider) and not api_key:
        record_byok_missing_credentials(provider, operation="messages.count_tokens")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "missing_provider_credentials",
                "message": f"Provider '{provider}' requires an API key. Please configure credentials.",
            },
        )

    if provider not in MESSAGES_NATIVE_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="count_tokens is only supported for Anthropic-compatible providers.",
        )

    base_url = _resolve_messages_base_url(provider, app_config_override)
    url = _join_messages_endpoint(base_url, "/messages/count_tokens")
    payload = _prepare_native_payload(request_data, model=model)
    timeout = _resolve_native_timeout(provider, app_config_override)
    headers = _build_native_headers(
        provider,
        api_key,
        anthropic_version=anthropic_version,
        anthropic_beta=anthropic_beta,
    )
    with http_client_factory(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return JSONResponse(data)


@router.post(
    "/messages",
    summary="Anthropic-compatible Messages API",
    dependencies=[Depends(check_rate_limit)],
)
async def create_messages(
    request_data: AnthropicMessagesRequest = Body(...),
    current_user: User = Depends(get_request_user),
    request: Request = None,
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version"),
    anthropic_beta: Optional[str] = Header(None, alias="anthropic-beta"),
):
    return await _handle_messages(
        request_data,
        current_user=current_user,
        request=request,
        anthropic_version=anthropic_version,
        anthropic_beta=anthropic_beta,
    )


@public_router.post(
    "/v1/messages",
    summary="Anthropic-compatible Messages API",
    dependencies=[Depends(check_rate_limit)],
)
async def create_messages_public(
    request_data: AnthropicMessagesRequest = Body(...),
    current_user: User = Depends(get_request_user),
    request: Request = None,
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version"),
    anthropic_beta: Optional[str] = Header(None, alias="anthropic-beta"),
):
    return await _handle_messages(
        request_data,
        current_user=current_user,
        request=request,
        anthropic_version=anthropic_version,
        anthropic_beta=anthropic_beta,
    )


@router.post(
    "/messages/count_tokens",
    summary="Anthropic-compatible Messages count_tokens",
    dependencies=[Depends(check_rate_limit)],
)
async def count_tokens(
    request_data: AnthropicCountTokensRequest = Body(...),
    current_user: User = Depends(get_request_user),
    request: Request = None,
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version"),
    anthropic_beta: Optional[str] = Header(None, alias="anthropic-beta"),
):
    return await _handle_count_tokens(
        request_data,
        current_user=current_user,
        request=request,
        anthropic_version=anthropic_version,
        anthropic_beta=anthropic_beta,
    )


@public_router.post(
    "/v1/messages/count_tokens",
    summary="Anthropic-compatible Messages count_tokens",
    dependencies=[Depends(check_rate_limit)],
)
async def count_tokens_public(
    request_data: AnthropicCountTokensRequest = Body(...),
    current_user: User = Depends(get_request_user),
    request: Request = None,
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version"),
    anthropic_beta: Optional[str] = Header(None, alias="anthropic-beta"),
):
    return await _handle_count_tokens(
        request_data,
        current_user=current_user,
        request=request,
        anthropic_version=anthropic_version,
        anthropic_beta=anthropic_beta,
    )
