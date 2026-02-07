"""
chat_service.py
Lightweight helpers to keep the chat endpoint readable and testable without changing behavior.

These functions encapsulate small, deterministic pieces of logic used by
the /api/v1/chat/completions endpoint so the endpoint can orchestrate at a
higher level. The goal is to reduce duplication and cognitive load while
keeping the wire behavior identical.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import inspect
import json as _json
import os
import re
import time
import uuid as _uuid
from collections.abc import AsyncIterator, Awaitable, Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from loguru import logger
from starlette.responses import StreamingResponse

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditEventType
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import replace_placeholders
from tldw_Server_API.app.core.Character_Chat.modules.character_utils import (
    map_sender_to_role,
    sanitize_sender_name,
)
from tldw_Server_API.app.core.Chat.Chat_Deps import (
    ChatAPIError,
    ChatBadRequestError,
    ChatConfigurationError,
    ChatProviderError,
)
from tldw_Server_API.app.core.Chat.chat_exceptions import get_request_id

# Reuse existing helpers from chat_helpers and prompt templating
from tldw_Server_API.app.core.Chat.chat_helpers import (
    get_or_create_character_context,
    get_or_create_conversation,
)
from tldw_Server_API.app.core.Chat.message_utils import should_persist_message_role
from tldw_Server_API.app.core.Chat.prompt_template_manager import (
    DEFAULT_RAW_PASSTHROUGH_TEMPLATE,
    apply_template_to_string,
    load_template,
)
from tldw_Server_API.app.core.Chat.request_queue import (
    RequestPriority,
    get_request_queue,
)
from tldw_Server_API.app.core.Chat.streaming_utils import (
    CHAT_STREAM_INCLUDE_METADATA,
    create_streaming_response_with_timeout,
)
from tldw_Server_API.app.core.Chat.streaming_utils import (
    HEARTBEAT_INTERVAL as CHAT_HEARTBEAT_INTERVAL,
)
from tldw_Server_API.app.core.Chat.streaming_utils import (
    STREAMING_IDLE_TIMEOUT as CHAT_IDLE_TIMEOUT,
)
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.LLM_Calls import adapter_registry as _adapter_registry
from tldw_Server_API.app.core.LLM_Calls.streaming import wrap_sync_stream
from tldw_Server_API.app.core.Moderation.moderation_service import get_moderation_service
from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
from tldw_Server_API.app.core.Usage.pricing_catalog import list_provider_models
from tldw_Server_API.app.core.Usage.usage_tracker import log_llm_usage
from tldw_Server_API.app.core.Utils.cpu_bound_handler import process_large_json_async

_CHAT_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ChatAPIError,
    ChatBadRequestError,
    ChatConfigurationError,
    ChatProviderError,
    HTTPException,
    AttributeError,
    ConnectionError,
    KeyError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
    _json.JSONDecodeError,
    asyncio.CancelledError,
)

_config = load_comprehensive_config()
_chat_config: dict[str, str] = {}
if _config and _config.has_section("Chat-Module"):
    _chat_config = dict(_config.items("Chat-Module"))


def _coerce_int(value: str | None, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        return default


def _coerce_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


_MAX_HISTORY_MESSAGES = max(1, _coerce_int(_chat_config.get("max_history_messages"), 200))

_default_history_limit = 20
if "history_messages_limit" in _chat_config:
    _default_history_limit = max(
        1,
        min(_MAX_HISTORY_MESSAGES, _coerce_int(_chat_config.get("history_messages_limit"), _default_history_limit)),
    )
_env_history_limit = os.getenv("CHAT_HISTORY_LIMIT")
if _env_history_limit:
    with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
        _default_history_limit = max(1, min(_MAX_HISTORY_MESSAGES, int(_env_history_limit)))
DEFAULT_HISTORY_MESSAGE_LIMIT = _default_history_limit

_default_history_order = _chat_config.get("history_messages_order", "desc").strip().lower()
if _default_history_order not in {"asc", "desc"}:
    _default_history_order = "desc"
_env_history_order = os.getenv("CHAT_HISTORY_ORDER")
if _env_history_order:
    _env_history_order_val = _env_history_order.strip().lower()
    if _env_history_order_val in {"asc", "desc"}:
        _default_history_order = _env_history_order_val
DEFAULT_HISTORY_MESSAGE_ORDER = _default_history_order

_inject_assistant_name = _coerce_bool(_chat_config.get("inject_assistant_name"), False)
_env_inject_assistant_name = os.getenv("CHAT_INJECT_ASSISTANT_NAME")
if _env_inject_assistant_name is not None:
    _inject_assistant_name = _coerce_bool(_env_inject_assistant_name, _inject_assistant_name)
INJECT_ASSISTANT_NAME = _inject_assistant_name

_force_normalize_strings = _coerce_bool(_chat_config.get("force_normalize_string_responses"), False)
_env_force_normalize = os.getenv("CHAT_FORCE_NORMALIZE_STRING_RESPONSES")
if _env_force_normalize is not None:
    _force_normalize_strings = _coerce_bool(_env_force_normalize, _force_normalize_strings)
FORCE_NORMALIZE_STRING_RESPONSES = _force_normalize_strings


def should_force_normalize_string_responses() -> bool:
    """Return True when raw-string LLM responses should be wrapped in OpenAI format."""
    raw = os.getenv("CHAT_FORCE_NORMALIZE_STRING_RESPONSES")
    if raw is not None:
        return _coerce_bool(raw, FORCE_NORMALIZE_STRING_RESPONSES)
    return FORCE_NORMALIZE_STRING_RESPONSES


# --- Cached helpers (module scope) -------------------------------------------
@lru_cache(maxsize=16)
def _load_models_with_case_cached(provider: str) -> list[str]:
    """Load provider models preserving original key casing when possible.

    Attempts to read the raw model_pricing.json to preserve the original
    casing of model identifiers. Falls back to the normalized catalog
    via list_provider_models (lowercase keys) if needed.
    """
    try:
        cfg_path = Path(__file__).resolve().parents[3] / "Config_Files" / "model_pricing.json"
        if cfg_path.exists():
            data = _json.loads(cfg_path.read_text())
            prov_block = data.get(provider) or data.get(provider.capitalize()) or data.get(provider.upper())
            if isinstance(prov_block, dict):
                return list(prov_block.keys())
    except (OSError, ValueError, KeyError, AttributeError) as _e:
        # Expected file/format issues: fall back to normalized catalog
        logger.debug(f"Model catalog raw load fallback for provider '{provider}': {_e}")
    except _CHAT_NONCRITICAL_EXCEPTIONS as _ue:
        # Unexpected exceptions should be visible in production logs
        pass
        logger.warning(f"Unexpected error loading model catalog for provider '{provider}': {_ue}")

    # Fallback: use the normalized list (lowercase keys)
    return list_provider_models(provider) or []


@lru_cache(maxsize=1)
def _load_alias_overrides_cached() -> dict[str, dict[str, str]]:
    """Load model alias overrides from env and pricing catalog.

    Resolution order:
    1) ENV var CHAT_MODEL_ALIAS_OVERRIDES (JSON)
    2) Keys in Config_Files/model_pricing.json: model_aliases/aliases/alias_map
    3) Test-friendly defaults when PYTEST_CURRENT_TEST is set
    """
    # 1) ENV
    try:
        raw = os.getenv("CHAT_MODEL_ALIAS_OVERRIDES")
        if raw:
            data = _json.loads(raw)
            if isinstance(data, dict):
                return {
                    str(k).lower(): {str(ak).lower(): str(av) for ak, av in (v or {}).items()}
                    for k, v in data.items()
                    if isinstance(v, dict)
                }
    except (ValueError, TypeError) as _e:
        logger.debug(f"CHAT_MODEL_ALIAS_OVERRIDES parse failed: {_e}")
    except _CHAT_NONCRITICAL_EXCEPTIONS as _ue:
        # Unexpected exceptions should be visible in production logs
        pass
        logger.warning(f"Unexpected error parsing CHAT_MODEL_ALIAS_OVERRIDES: {_ue}")

    # 2) File keys in pricing catalog
    try:
        cfg_path = Path(__file__).resolve().parents[3] / "Config_Files" / "model_pricing.json"
        if cfg_path.exists():
            data = _json.loads(cfg_path.read_text())
            for key in ("model_aliases", "aliases", "alias_map"):
                block = data.get(key)
                if isinstance(block, dict):
                    return {
                        str(k).lower(): {str(ak).lower(): str(av) for ak, av in (v or {}).items()}
                        for k, v in block.items()
                        if isinstance(v, dict)
                    }
    except (OSError, ValueError, KeyError, AttributeError) as _e:
        logger.debug(f"Alias overrides load fallback: {_e}")
    except _CHAT_NONCRITICAL_EXCEPTIONS as _ue:
        # Unexpected exceptions should be visible in production logs
        pass
        logger.warning(f"Unexpected error loading alias overrides: {_ue}")

    # 3) Test-friendly defaults (preserve legacy behavior under pytest only)
    if os.getenv("PYTEST_CURRENT_TEST"):
        return {
            "anthropic": {"claude-sonnet": "claude-sonnet-4-5"},
            # Use a small, fast model via OpenRouter in tests
            "openrouter": {"dummy": "z-ai/glm-4.6"},
            "mistral": {"dummy": "mistral-small-latest"},
        }
    return {}


def invalidate_model_alias_caches() -> None:
    """Invalidate cached model list and alias overrides for hot-reload.

    Clears lru_cache for both `_load_models_with_case_cached` and
    `_load_alias_overrides_cached`. Safe to call at runtime (no side effects
    beyond cache flush). Subsequent requests will repopulate from sources.
    """
    with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
        _load_models_with_case_cached.cache_clear()
    with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
        _load_alias_overrides_cached.cache_clear()


def queue_is_active(queue: Any) -> bool:
    """Return True when the request queue is running and able to process work."""
    try:
        status = queue.is_running
    except AttributeError:
        status = None
    if callable(status):
        try:
            result = status()
            if result is not None:
                return bool(result)
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass
    elif status is not None:
        return bool(status)

    fallback_state = getattr(queue, "_running", None)
    if fallback_state is not None:
        return bool(fallback_state)
    # Assume truthy for lightweight test stubs that do not expose state
    return True


def _attach_queue_future_logger(future: asyncio.Future[Any], request_id: str) -> None:
    """Consume queue future exceptions to avoid unhandled warnings in streaming mode."""

    def _consume(fut: asyncio.Future[Any]) -> None:
        try:
            fut.result()
        except asyncio.CancelledError:
            return
        except _CHAT_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug("Queue streaming job {} failed: {}", request_id, exc)

    future.add_done_callback(_consume)


def _schedule_background_task(
    awaitable: Awaitable[Any],
    *,
    task_name: str,
    pending_tasks: list[asyncio.Task[Any]] | None = None,
) -> asyncio.Task[Any] | None:
    """Schedule a background task and observe failures to avoid silent task leaks."""

    try:
        task = asyncio.create_task(awaitable)
    except _CHAT_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug("Failed to schedule background task {}: {}", task_name, exc)
        return None

    if pending_tasks is not None:
        pending_tasks.append(task)

    def _consume(completed: asyncio.Task[Any]) -> None:
        if pending_tasks is not None:
            with contextlib.suppress(ValueError):
                pending_tasks.remove(completed)
        if completed.cancelled():
            return
        try:
            exc = completed.exception()
        except asyncio.CancelledError:
            return
        except _CHAT_NONCRITICAL_EXCEPTIONS as consume_exc:
            logger.debug("Background task {} observation failed: {}", task_name, consume_exc)
            return
        if exc is not None:
            logger.debug("Background task {} failed: {}", task_name, exc)

    task.add_done_callback(_consume)
    return task


def parse_provider_model_for_metrics(
    request_data: Any,
    default_provider: str,
) -> tuple[str, str]:
    """Parse provider and model for metrics logging without mutating request_data.

    Accepts model strings like "anthropic/claude-opus-4.1" and an optional
    api_provider on the request, falling back to the server default.

    Returns (provider, model_for_metrics).
    """
    model_str = getattr(request_data, "model", None) or "unknown"
    api_provider = getattr(request_data, "api_provider", None)
    if "/" in model_str:
        parts = model_str.split("/", 1)
        if len(parts) == 2:
            model_provider, model_name = parts
            provider = (api_provider or model_provider).lower()
            model = model_name
        else:
            provider = (api_provider or default_provider).lower()
            model = model_str
    else:
        provider = (api_provider or default_provider).lower()
        model = model_str
    return provider, model


def normalize_request_provider_and_model(
    request_data: Any,
    default_provider: str,
) -> str:
    """Normalize provider and model on the request.

    If the request's model contains a provider prefix (e.g., "groq/llama-3"),
    update request_data.model in-place to only the model component and return
    the selected provider name. This mirrors the behavior already present in
    the endpoint and avoids duplication.
    """
    model_str = getattr(request_data, "model", None) or ""
    api_provider = getattr(request_data, "api_provider", None)

    # --- Alias resolution via configurable catalog (model_pricing.json) ---
    # Prefer provider-agnostic model keys and avoid hardcoded, versioned IDs.
    # Alias resolution is strict: only explicit overrides or exact model matches
    # are applied. This avoids silently picking a default model.
    try:
        # Determine provider context for alias resolution.
        # If model includes an inline provider (e.g., "anthropic/claude-sonnet"),
        # prefer that; else honor api_provider, then default_provider.
        inline_provider: str | None = None
        inline_model_part: str | None = None
        if "/" in model_str:
            parts_for_alias = model_str.split("/", 1)
            if len(parts_for_alias) == 2:
                inline_provider, inline_model_part = parts_for_alias[0].strip(), parts_for_alias[1].strip()
        provider_for_mapping = ((inline_provider or api_provider or default_provider) or "").strip().lower()


        def _resolve_alias(provider: str, raw_model: str) -> str | None:
            m = (raw_model or "").strip()
            if not m:
                return None
            models = _load_models_with_case_cached(provider)
            if not models:
                return None
            m_lower = m.lower()
            # Strict resolution: only exact (case-insensitive) matches.
            for cand in models:
                if cand.lower() == m_lower:
                    return cand
            return None

        # Optional alias overrides allow cross-provider or provider-agnostic mappings
        # without changing code. Sources (first match wins):
        #  - ENV JSON CHAT_MODEL_ALIAS_OVERRIDES = { provider: { alias: concrete_model } }
        #  - Config_Files/model_pricing.json key "model_aliases" or "aliases"
        #  - Test-safe built-ins when PYTEST_CURRENT_TEST is set (keeps historical behavior)
        alias_overrides = _load_alias_overrides_cached()

        # First apply alias override (supports cross-provider targets)
        ov_map = alias_overrides.get(provider_for_mapping, {})
        target_model_part = inline_model_part if inline_model_part is not None else model_str
        override_target = ov_map.get((target_model_part or "").strip().lower())
        if override_target:
            resolved = override_target
        else:
            # Resolve against known models when no explicit override present
            resolved = _resolve_alias(provider_for_mapping, target_model_part)
        if resolved and resolved != model_str:
            allow_cross = str(os.getenv("CHAT_ALLOW_CROSS_PROVIDER_ALIASING", "0")).lower() in {"1", "true", "yes", "on"}
            if inline_provider:
                # Preserve inline provider prefix until final normalization below
                combined = f"{inline_provider}/{resolved}"
                request_data.model = combined
                model_str = combined
            else:
                # Prevent accidental provider flips unless explicitly allowed.
                # Special-case OpenRouter: it expects namespaced model ids like
                # "z-ai/glm-4.6" to be preserved when api_provider is openrouter.
                if provider_for_mapping == "openrouter":
                    request_data.model = resolved
                    model_str = request_data.model
                elif "/" in resolved and not allow_cross:
                    resolved = None
                else:
                    request_data.model = resolved
                    model_str = request_data.model
                if not resolved:
                    resolved = None  # leave model_str untouched, no override applied
    except (AttributeError, KeyError, ValueError):
        # Expected lookup/attr issues: do not block request
        pass
    except _CHAT_NONCRITICAL_EXCEPTIONS as _unexpected:
        # Unexpected exceptions should be visible in production logs
        pass
        logger.warning(f"Unexpected error during model alias resolution: {_unexpected}")
    provider = (api_provider or default_provider).lower()
    if "/" in model_str:
        parts = model_str.split("/", 1)
        if len(parts) == 2:
            model_provider, actual_model = parts
            inline_provider_lower = model_provider.lower()
            # If the api_provider was not explicitly set, allow inline provider to select it
            if not api_provider:
                provider = inline_provider_lower
                # In this case, strip the inline provider prefix from the model
                request_data.model = actual_model
            else:
                # api_provider is explicitly set on the request. For OpenRouter and
                # Hugging Face, many valid model IDs include a namespace
                # (e.g., "openai/gpt-4o-mini", "z-ai/glm-4.6"). Preserve the full
                # namespaced model id unless the inline namespace matches "openrouter".
                if provider in {"openrouter", "huggingface"}:
                    if provider == "openrouter" and inline_provider_lower == "openrouter":
                        request_data.model = actual_model
                    else:
                        request_data.model = model_str
                else:
                    # Non-OpenRouter providers do not use namespaced model ids; strip prefix
                    request_data.model = actual_model
    return provider


def resolve_provider_and_model(
    request_data: Any,
    metrics_default_provider: str,
    normalize_default_provider: str,
) -> tuple[str, str, str, str, dict[str, Any]]:
    """Resolve provider/model for metrics and execution and record the decision path.

    Returns a 5-tuple:
        (metrics_provider, metrics_model, selected_provider, selected_model, debug_info)

    - metrics_provider/metrics_model mirror the legacy behavior of
      `parse_provider_model_for_metrics` (used for request-level metrics and audit).
    - selected_provider/selected_model reflect the normalized provider/model that
      downstream logic should use (after alias resolution and inline prefixes).
    - debug_info is a JSON-serializable dict describing the decision path.

    The function may update `request_data.model` in-place via
    `normalize_request_provider_and_model`, matching existing behavior.
    """
    raw_model = getattr(request_data, "model", None)
    raw_api_provider = getattr(request_data, "api_provider", None)

    # Step 1: derive metrics-facing provider/model without mutating the request
    metrics_provider, metrics_model = parse_provider_model_for_metrics(
        request_data, metrics_default_provider
    )

    selected_provider = metrics_provider
    selected_model = metrics_model

    # Step 2: normalize provider/model for execution (may mutate request_data.model)
    try:
        normalized_provider = normalize_request_provider_and_model(
            request_data, normalize_default_provider
        )
        selected_provider = normalized_provider
        new_model = getattr(request_data, "model", None)
        if new_model:
            selected_model = new_model
    except _CHAT_NONCRITICAL_EXCEPTIONS as exc:
        # Do not block the request if normalization fails; fall back to metrics values.
        pass
        logger.debug(
            "resolve_provider_and_model: normalization failed, "
            "falling back to metrics provider/model. Error={}",
            exc,
        )

    debug_info: dict[str, Any] = {
        "raw": {
            "api_provider": raw_api_provider,
            "model": raw_model,
        },
        "metrics": {
            "default_provider": metrics_default_provider,
            "provider": metrics_provider,
            "model": metrics_model,
        },
        "normalized": {
            "default_provider": normalize_default_provider,
            "provider": selected_provider,
            "model": selected_model,
        },
        "changed": {
            "provider_changed": metrics_provider != selected_provider,
            "model_changed": metrics_model != selected_model,
        },
    }

    return metrics_provider, metrics_model, selected_provider, selected_model, debug_info


def resolve_provider_api_key(
    provider: str,
    *,
    prefer_module_keys_in_tests: bool = True,
) -> tuple[str | None, dict[str, Any]]:
    """
    Resolve the API key for a provider using env/config first, with optional test overrides.

    Resolution order:
    1) In test contexts (PYTEST_CURRENT_TEST or TEST_MODE) and when prefer_module_keys_in_tests=True,
       use module-level API_KEYS (schemas first, then endpoint) if present for the provider.
    2) Otherwise, return the dynamic key from get_api_keys() (env/config/dotenv).
    Returns (normalized_key, debug_info).
    """
    provider_key = (provider or "").strip().lower()
    debug_info: dict[str, Any] = {
        "provider": provider_key or provider,
        "selected_source": "missing",
        "module_sources": [],
        "test_flags": {},
        "raw_value_provided": False,
        "raw_value_was_empty": False,
        "dynamic_value_present": False,
        "override_value_present": False,
    }

    try:
        is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        is_pytest = False
    is_test_mode = os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    use_module_overrides = prefer_module_keys_in_tests and (is_pytest or is_test_mode)
    debug_info["test_flags"] = {"pytest": is_pytest, "test_mode": is_test_mode}

    try:
        from tldw_Server_API.app.api.v1.schemas import chat_request_schemas as _schemas_mod  # type: ignore

        dynamic_keys = _schemas_mod.get_api_keys() or {}
    except _CHAT_NONCRITICAL_EXCEPTIONS as _err:
        # API key loading errors should be visible in production
        pass
        logger.warning(f"resolve_provider_api_key failed to load dynamic keys: {_err}")
        dynamic_keys = {}

    module_keys: dict[str, str | None] = {}
    if use_module_overrides:
        try:
            schema_keys = getattr(_schemas_mod, "API_KEYS", None)
            if isinstance(schema_keys, dict) and schema_keys:
                module_keys.update(schema_keys)
                debug_info["module_sources"].append("chat_request_schemas")
        except _CHAT_NONCRITICAL_EXCEPTIONS as _schema_err:
            logger.warning(f"resolve_provider_api_key skipped schema module keys: {_schema_err}")
        try:
            from tldw_Server_API.app.api.v1.endpoints import chat as _chat_mod  # type: ignore

            endpoint_keys = getattr(_chat_mod, "API_KEYS", None)
            if isinstance(endpoint_keys, dict) and endpoint_keys:
                # Endpoint-level patches override schema-level for tests.
                module_keys.update(endpoint_keys)
                debug_info["module_sources"].append("chat_endpoint")
        except _CHAT_NONCRITICAL_EXCEPTIONS as _chat_err:
            logger.warning(f"resolve_provider_api_key skipped endpoint module keys: {_chat_err}")

    try:
        from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import get_llm_provider_override

        override = get_llm_provider_override(provider_key)
        override_value = override.api_key if override else None
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        override_value = None

    debug_info["override_value_present"] = override_value is not None

    dynamic_value = dynamic_keys.get(provider_key)
    debug_info["dynamic_value_present"] = dynamic_value is not None

    def _normalize(value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    raw_value = dynamic_value
    selected_override = False
    if override_value is not None:
        raw_value = override_value
        selected_override = True
        debug_info["selected_source"] = "override"
    if use_module_overrides and module_keys and provider_key in module_keys:
        raw_value = module_keys.get(provider_key)
        debug_info["selected_source"] = "module_override"
    elif raw_value is not None and not selected_override:
        env_var = (
            f"{provider_key.upper().replace('.', '_').replace('-', '_')}_API_KEY"
            if provider_key
            else None
        )
        debug_info["selected_source"] = "env" if env_var and os.getenv(env_var) is not None else "config"
    elif raw_value is None:
        debug_info["selected_source"] = "missing"

    debug_info["raw_value_provided"] = raw_value is not None
    debug_info["raw_value_was_empty"] = isinstance(raw_value, str) and raw_value.strip() == ""
    normalized_value = _normalize(raw_value)
    return normalized_value, debug_info


def _resolve_base_url_override(provider: str, chat_args: dict[str, Any]) -> str | None:
    base_url = chat_args.get("base_url")
    if base_url is None:
        base_url = chat_args.get("api_base_url")
    if base_url is None:
        return None
    provider_key = (provider or "").strip().lower()
    from tldw_Server_API.app.core.AuthNZ.byok_helpers import (
        is_trusted_base_url_request,
        resolve_byok_base_url_allowlist,
        validate_base_url_override,
    )

    allowlist = resolve_byok_base_url_allowlist()
    if provider_key not in allowlist:
        raise ChatBadRequestError(
            provider=provider_key or None,
            message=f"base_url override is not enabled for provider '{provider_key}'",
        )
    trusted_override = bool(chat_args.get("trusted_base_url_override"))
    if not trusted_override:
        request_obj = chat_args.get("request") or chat_args.get("caller_request")
        principal = chat_args.get("principal")
        user = chat_args.get("auth_user")
        trusted_override = is_trusted_base_url_request(request_obj, principal=principal, user=user)
    if not trusted_override:
        raise ChatBadRequestError(
            provider=provider_key or None,
            message="base_url override requires a trusted caller",
        )
    try:
        return validate_base_url_override(base_url)
    except ValueError as exc:
        raise ChatBadRequestError(provider=provider_key or None, message=str(exc)) from exc


def _build_adapter_request_from_chat_args(chat_args: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Translate chat_api_call-style args into an adapter request payload."""
    from tldw_Server_API.app.core.LLM_Calls.adapter_utils import (
        ensure_app_config,
        normalize_provider,
        resolve_provider_api_key_from_config,
        resolve_provider_model,
    )

    provider = normalize_provider(
        chat_args.get("api_endpoint")
        or chat_args.get("api_provider")
        or chat_args.get("provider")
    )
    if provider in {"local", "local_llm"}:
        provider = "local-llm"
    if not provider:
        raise ChatConfigurationError(provider=str(chat_args.get("api_endpoint")), message="LLM provider is required.")

    local_like = {
        "local-llm",
        "llama.cpp",
        "kobold",
        "ooba",
        "tabbyapi",
        "vllm",
        "ollama",
        "aphrodite",
        "mlx",
    }
    explicit_app_config = chat_args.get("app_config")
    app_config = explicit_app_config if explicit_app_config is not None else (
        None if provider in local_like else ensure_app_config(None)
    )
    model = chat_args.get("model")
    if model is None and app_config is not None:
        model = resolve_provider_model(provider, app_config)
    if not model and provider not in local_like:
        raise ChatConfigurationError(provider=provider, message="Model is required for provider.")

    api_key = chat_args.get("api_key") or resolve_provider_api_key_from_config(provider, app_config)
    messages_payload = chat_args.get("messages_payload") or chat_args.get("messages") or []

    request: dict[str, Any] = {
        "messages": messages_payload,
        "system_message": chat_args.get("system_message"),
        "model": model,
        "api_key": api_key,
        "app_config": app_config,
    }

    base_url_override = _resolve_base_url_override(provider, chat_args)
    if base_url_override:
        request["base_url"] = base_url_override

    stream_value = chat_args.get("stream")
    if stream_value is None:
        stream_value = chat_args.get("streaming")
    if stream_value is not None:
        request["stream"] = bool(stream_value)

    skip_keys = {
        "api_endpoint",
        "api_provider",
        "provider",
        "messages_payload",
        "messages",
        "system_message",
        "model",
        "api_key",
        "app_config",
        "base_url",
        "api_base_url",
        "request",
        "caller_request",
        "principal",
        "auth_user",
        "trusted_base_url_override",
        "stream",
        "streaming",
        "history_message_limit",
        "history_message_order",
        "slash_command_injection_mode",
    }
    for key, value in chat_args.items():
        if key in skip_keys or value is None:
            continue
        if key not in request:
            request[key] = value

    internal: dict[str, Any] = {}
    for key in ("http_client_factory", "http_fetcher"):
        if chat_args.get(key) is not None:
            internal[key] = chat_args[key]

    return provider, request, internal


def _attach_internal_http_hooks(adapter: Any, request: dict[str, Any], internal: dict[str, Any]) -> None:
    """Attach http_client_factory/http_fetcher only for adapters that opt in."""
    if not internal:
        return
    if getattr(adapter, "accepts_internal_http_hooks", False):
        request.update(internal)


def _get_llm_registry():
    """Resolve the adapter registry at call time to honor test monkeypatching."""
    return _adapter_registry.get_registry()


def perform_chat_api_call(**kwargs: Any) -> Any:
    """Adapter-backed replacement for chat_orchestrator.chat_api_call."""
    provider, request, internal = _build_adapter_request_from_chat_args(kwargs)
    adapter = _get_llm_registry().get_adapter(provider)
    if adapter is None:
        raise ChatConfigurationError(provider=provider, message="LLM adapter unavailable.")
    _attach_internal_http_hooks(adapter, request, internal)
    if request.get("stream"):
        return adapter.stream(request)
    return adapter.chat(request)


async def perform_chat_api_call_async(**kwargs: Any) -> Any:
    """Async adapter-backed replacement for chat_orchestrator.chat_api_call_async."""
    provider, request, internal = _build_adapter_request_from_chat_args(kwargs)
    adapter = _get_llm_registry().get_adapter(provider)
    if adapter is None:
        raise ChatConfigurationError(provider=provider, message="LLM adapter unavailable.")
    _attach_internal_http_hooks(adapter, request, internal)

    if request.get("stream"):
        try:
            stream_iter = adapter.astream(request)
            if inspect.isawaitable(stream_iter):
                stream_iter = await stream_iter
            return stream_iter
        except NotImplementedError:
            stream_iter = adapter.stream(request)
            return wrap_sync_stream(stream_iter)

    try:
        return await adapter.achat(request)
    except NotImplementedError:
        return await asyncio.to_thread(adapter.chat, request)


def merge_api_keys_for_provider(
    provider: str,
    module_keys: dict[str, str | None] | None,
    dynamic_keys: dict[str, str | None],
    requires_key_map: dict[str, bool],
) -> tuple[str | None, str | None]:
    """Merge module-level and dynamic API keys, normalizing empties to None.

    Returns a tuple of (raw_value, normalized_value). The raw value is the
    original string (possibly empty) used to validate presence when a provider
    requires a key. The normalized value is None if empty-string-like.
    """
    def _normalize(value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    raw_dynamic = dynamic_keys.get(provider)
    raw_module = module_keys.get(provider) if module_keys else None

    # Prefer dynamic/runtime keys (env/config) over module-level defaults.
    # If dynamic is explicitly empty/None, fall back to module-level value.
    raw_val = raw_dynamic if raw_dynamic is not None and str(raw_dynamic).strip() != "" else raw_module

    norm_val = _normalize(raw_val)

    # No raise here - the caller enforces requirements using requires_key_map
    return raw_val, norm_val


def build_call_params_from_request(
    request_data: Any,
    target_api_provider: str,
    provider_api_key: str | None,
    templated_llm_payload: list[dict[str, Any]],
    final_system_message: str | None,
    app_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the cleaned argument dictionary for chat_api_call.

    Mirrors the transformation previously in the endpoint: renames OpenAI-style
    params to the generic names expected by chat_api_call and attaches
    provider/model/messages/system/stream flags.
    """
    call_params = request_data.model_dump(
        exclude_none=True,
        exclude={
            "api_provider",
            "messages",
            "character_id",
            "conversation_id",
            "prompt_template_name",
            "stream",
            "save_to_db",
            "history_message_limit",
            "history_message_order",
            "slash_command_injection_mode",
        },
    )

    # Rename keys to match chat_api_call's generic signature
    if "temperature" in call_params:
        call_params["temp"] = call_params.pop("temperature")
    if "top_p" in call_params:
        top_p_value = call_params.pop("top_p")
        # Normalize to a single generic param; provider maps translate as needed
        call_params["topp"] = top_p_value
    if "user" in call_params:
        call_params["user_identifier"] = call_params.pop("user")

    call_params.update(
        {
            "api_endpoint": target_api_provider,
            "api_key": provider_api_key,
            "messages_payload": templated_llm_payload,
            "system_message": final_system_message,
            "streaming": getattr(request_data, "stream", False),
        }
    )
    if app_config is not None:
        call_params["app_config"] = app_config

    # Filter Nones; keep explicit None for system_message only if provided
    cleaned_args = {k: v for k, v in call_params.items() if v is not None}
    if "system_message" not in cleaned_args and final_system_message is not None:
        cleaned_args["system_message"] = final_system_message
    return cleaned_args


def estimate_tokens_from_json(request_json: str) -> int:
    """Rough estimate: assume ~4 chars per token for rate limiting.

    This matches the existing heuristic in the endpoint.
    """
    try:
        sanitized = _sanitize_data_uris(request_json)
        return max(1, len(sanitized) // 4)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        return 1


_DATA_URI_RE = re.compile(r"(data:image[^,]*,)[^\"\\s]+", re.IGNORECASE)


def _sanitize_data_uris(text: str) -> str:
    """Redact data URI payloads to avoid inflating token estimates."""
    try:
        return _DATA_URI_RE.sub(r"\1<omitted>", text)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        return text


def _sanitize_messages_for_token_estimate(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of messages with base64 image payloads replaced."""
    sanitized: list[dict[str, Any]] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        msg_copy = msg.copy()
        content = msg_copy.get("content")
        if isinstance(content, list):
            new_parts: list[Any] = []
            for part in content:
                if not isinstance(part, dict):
                    new_parts.append(part)
                    continue
                if part.get("type") == "image_url":
                    image_url = part.get("image_url") or {}
                    if isinstance(image_url, dict):
                        url_val = image_url.get("url")
                        if isinstance(url_val, str) and url_val.startswith("data:image"):
                            new_image_url = dict(image_url)
                            new_image_url["url"] = "data:image/omitted"
                            new_parts.append({**part, "image_url": new_image_url})
                            continue
                new_parts.append(part)
            msg_copy["content"] = new_parts
        elif isinstance(content, str):
            msg_copy["content"] = _sanitize_data_uris(content)
        sanitized.append(msg_copy)
    return sanitized


def _estimate_tokens_from_messages(messages: list[dict[str, Any]]) -> int:
    """Estimate tokens from message payloads with base64 redaction."""
    try:
        sanitized = _sanitize_messages_for_token_estimate(messages)
        return max(1, len(_json.dumps(sanitized, default=str)) // 4)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        return 1


def _extract_text_from_content(content: Any) -> str:
    """Extract text from a message content payload (string or list parts)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                if part:
                    parts.append(part)
                continue
            p_type = None
            p_text = None
            if isinstance(part, dict):
                p_type = part.get("type")
                p_text = part.get("text")
            else:
                try:
                    p_type = getattr(part, "type", None)
                    p_text = getattr(part, "text", None)
                except _CHAT_NONCRITICAL_EXCEPTIONS:
                    p_type = None
                    p_text = None
            if p_type == "text" and isinstance(p_text, str) and p_text:
                parts.append(p_text)
        return "\n".join(parts)
    try:
        return str(content)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        return ""


def _apply_redaction_to_content(content: Any, moderation: Any, policy: Any) -> Any:
    """Apply redaction to text parts while preserving non-text content when possible."""
    if content is None:
        return content
    if isinstance(content, str):
        return moderation.redact_text(content, policy)
    if isinstance(content, list):
        redacted_parts: list[Any] = []
        for part in content:
            if isinstance(part, str):
                redacted_parts.append(moderation.redact_text(part, policy))
                continue
            if isinstance(part, dict):
                if part.get("type") == "text":
                    new_part = dict(part)
                    new_part["text"] = moderation.redact_text(part.get("text", ""), policy)
                    redacted_parts.append(new_part)
                else:
                    redacted_parts.append(part)
                continue
            try:
                p_type = getattr(part, "type", None)
                if p_type == "text":
                    text_val = getattr(part, "text", "")
                    new_text = moderation.redact_text(text_val, policy)
                    try:
                        updated = part.model_copy(update={"text": new_text})
                        redacted_parts.append(updated)
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        redacted_parts.append({"type": "text", "text": new_text})
                else:
                    redacted_parts.append(part)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                redacted_parts.append(part)
        return redacted_parts
    return moderation.redact_text(str(content), policy)


def _wrap_raw_string_response(content: str, model: str | None) -> dict[str, Any]:
    """Wrap raw string responses in an OpenAI-compatible payload."""
    model_name = model or "unknown"
    return {
        "id": f"chatcmpl-{_uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


async def moderate_input_messages(
    request_data: Any,
    request: Any,
    moderation_service: Any,
    topic_monitoring_service: Any | None,
    metrics: Any,
    audit_service: Any | None,
    audit_context: Any | None,
    client_id: str,
    audit_event_type: Any | None = None,
) -> None:
    """Apply input moderation and redaction to user message text parts in-place.

    - Emits topic monitoring alerts non-blockingly when configured.
    - Tracks moderation metrics and audit events.
    - Raises HTTPException(400) when input is blocked by policy.
    """
    # Determine user id context for policy and telemetry
    req_user_id = None
    try:
        if request is not None and hasattr(request, "state"):
            req_user_id = getattr(request.state, "user_id", None)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        req_user_id = None

    eff_policy = moderation_service.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)
    conv_id = None
    try:
        conv_id = getattr(request_data, "conversation_id", None)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        conv_id = None

    async def _moderate_text_in_place(text: str) -> str:
        # Topic monitoring (non-blocking)
        try:
            mon = topic_monitoring_service
            team_ids = None
            org_ids = None
            try:
                if request is not None and hasattr(request, "state"):
                    team_ids = getattr(request.state, "team_ids", None)
                    org_ids = getattr(request.state, "org_ids", None)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                pass
            if mon is not None and text:
                mon.schedule_evaluate_and_alert(
                    user_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                    text=text,
                    source="chat.input",
                    scope_type="user",
                    scope_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                    team_ids=team_ids,
                    org_ids=org_ids,
                    source_id=str(conv_id) if conv_id is not None else None,
                )
        except _CHAT_NONCRITICAL_EXCEPTIONS as _e:
            logger.debug(f"Topic monitoring (input) skipped: {_e}")

        if not eff_policy.enabled or not eff_policy.input_enabled:
            return text

        resolved_action = None
        sample = None
        redacted = None
        category = None
        matched_pattern = None
        match_span = None
        if hasattr(moderation_service, "evaluate_action_with_match"):
            try:
                eval_res = moderation_service.evaluate_action_with_match(text, eff_policy, "input")
                if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                    resolved_action, redacted, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                    category = eval_res[3] if len(eval_res) >= 4 else None
                    match_span = eval_res[4] if len(eval_res) >= 5 else None
                else:
                    resolved_action, redacted, matched_pattern = eval_res  # type: ignore
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                resolved_action = None
            if match_span and hasattr(moderation_service, "build_sanitized_snippet"):
                try:
                    sample = moderation_service.build_sanitized_snippet(text, eff_policy, match_span, matched_pattern)
                except _CHAT_NONCRITICAL_EXCEPTIONS:
                    sample = None
        elif hasattr(moderation_service, "evaluate_action"):
            try:
                eval_res = moderation_service.evaluate_action(text, eff_policy, "input")
                if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                    resolved_action, redacted, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                    category = eval_res[3] if len(eval_res) >= 4 else None
                else:
                    resolved_action, redacted, matched_pattern = eval_res  # type: ignore
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                resolved_action = None
            if resolved_action and resolved_action != "pass" and sample is None:
                try:
                    _, sample = moderation_service.check_text(text, eff_policy, "input")
                except _CHAT_NONCRITICAL_EXCEPTIONS:
                    sample = None
        if not resolved_action:
            flagged, sample = moderation_service.check_text(text, eff_policy, "input")
            if not flagged:
                return text
            resolved_action = eff_policy.input_action
            redacted = (
                moderation_service.redact_text(text, eff_policy)
                if resolved_action == "redact"
                else None
            )

        if resolved_action == "pass":
            return text

        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
            metrics.track_moderation_input(str(req_user_id or client_id), resolved_action, category=(category or "default"))
        try:
            if audit_service and audit_context:
                _schedule_background_task(
                    audit_service.log_event(
                        event_type=audit_event_type,
                        context=audit_context,
                        action="moderation.input",
                        result=("failure" if resolved_action == "block" else "success"),
                        metadata={"phase": "input", "action": resolved_action, "pattern": sample},
                    ),
                    task_name="chat.moderation.input.audit",
                )
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass

        if resolved_action == "block":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input violates moderation policy")
        if resolved_action == "redact":
            return redacted if isinstance(redacted, str) else moderation_service.redact_text(text, eff_policy)
        return text

    # Apply moderation across request messages
    # Moderate both "user" messages and "tool" messages (tool call results may contain
    # external content that should be checked for policy violations)
    MODERATED_ROLES = {"user", "tool"}
    try:
        if eff_policy.enabled and eff_policy.input_enabled and request_data and request_data.messages:
            for m in request_data.messages:
                if getattr(m, "role", None) not in MODERATED_ROLES:
                    continue
                if isinstance(m.content, str):
                    m.content = await _moderate_text_in_place(m.content)
                elif isinstance(m.content, list):
                    for part in m.content:
                        try_type = getattr(part, "type", None)
                        if try_type == "text":
                            current = getattr(part, "text", None)
                            if isinstance(current, str):
                                part.text = await _moderate_text_in_place(current)
    except HTTPException:
        raise
    except _CHAT_NONCRITICAL_EXCEPTIONS as e:
        logger.warning(f"Moderation input processing error: {e}")


async def build_context_and_messages(
    chat_db: Any,
    request_data: Any,
    loop: Any,
    metrics: Any,
    default_save_to_db: bool,
    final_conversation_id: str | None,
    save_message_fn: Any,
) -> tuple[dict[str, Any], int | None, str, bool, list[dict[str, Any]], bool]:
    """Resolve character/conversation context, load history, save current messages, and return LLM-ready payload.

    Returns (character_card, character_db_id, final_conversation_id, conversation_created, llm_payload_messages, should_persist)
    """
    # Character context
    character_card, character_db_id = await get_or_create_character_context(chat_db, request_data.character_id, loop)
    if character_card:
        system_prompt_preview = character_card.get("system_prompt")
        if system_prompt_preview:
            system_prompt_preview = system_prompt_preview[:50] + "..." if len(system_prompt_preview) > 50 else system_prompt_preview
        else:
            system_prompt_preview = "None"
        logger.debug(f"Loaded character: {character_card.get('name')} with system_prompt: {system_prompt_preview}")

    if character_card:
        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
            metrics.track_character_access(character_id=str(request_data.character_id or "default"), cache_hit=False)

    if not character_card:
        logger.warning("No character context found; proceeding with ephemeral default context.")
        character_card = {"name": DEFAULT_CHARACTER_NAME, "system_prompt": "You are a helpful AI assistant."}
        character_db_id = None

    # Persistence decision
    requested = getattr(request_data, "save_to_db", None)
    should_persist: bool = bool(requested) if (requested is not None) else bool(default_save_to_db)

    # Conversation resolution
    client_id_from_db = getattr(chat_db, "client_id", None)
    conversation_created = False
    conv_id = final_conversation_id
    # Ensure a valid character ID is present before attempting persistence
    if should_persist and character_db_id is None:
        logger.warning(
            "Persistence requested but no character ID is available; disabling persistence for conversation %s.",
            final_conversation_id or "<new>",
        )
        should_persist = False

    if should_persist:
        conv_id, conversation_created = await get_or_create_conversation(
            chat_db,
            conv_id,
            character_db_id,
            character_card.get("name", "Chat"),
            client_id_from_db,
            loop,
        )
    else:
        if not conv_id:
            conv_id = str(_uuid.uuid4())
        conversation_created = False

    if conv_id:
        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
            metrics.track_conversation(conv_id, conversation_created)
    if not conv_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to establish conversation context.")

    # History loading (configurable limit/order; filter missing roles, normalize assistant names)
    requested_history_limit = getattr(request_data, "history_message_limit", None)
    if requested_history_limit is None:
        history_limit = DEFAULT_HISTORY_MESSAGE_LIMIT
    else:
        try:
            history_limit = int(requested_history_limit)
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            history_limit = DEFAULT_HISTORY_MESSAGE_LIMIT
        history_limit = max(0, min(_MAX_HISTORY_MESSAGES, history_limit))

    requested_history_order = getattr(request_data, "history_message_order", None)
    if requested_history_order:
        history_order = str(requested_history_order).strip().lower()
        if history_order not in {"asc", "desc"}:
            history_order = DEFAULT_HISTORY_MESSAGE_ORDER
    else:
        history_order = DEFAULT_HISTORY_MESSAGE_ORDER
    db_order = "ASC" if history_order == "asc" else "DESC"

    historical_msgs: list[dict[str, Any]] = []
    if conv_id and (not conversation_created) and history_limit > 0:
        raw_hist = await loop.run_in_executor(
            None,
            chat_db.get_messages_for_conversation,
            conv_id,
            history_limit,
            0,
            db_order,
        )
        for db_msg in raw_hist:
            sender_val = str(db_msg.get("sender", "") or "")
            metadata = None
            try:
                metadata = await loop.run_in_executor(None, chat_db.get_message_metadata, db_msg.get("id"))
            except _CHAT_NONCRITICAL_EXCEPTIONS as meta_err:
                logger.debug("Metadata lookup failed for message {}: {}", db_msg.get("id"), meta_err)

            tool_calls_meta = None
            function_call_meta = None
            content_placeholder_reason = None
            tool_call_id_meta = None
            stored_role = None
            stored_name = None
            if metadata:
                tool_calls_meta = metadata.get("tool_calls")
                extra_meta = metadata.get("extra") or {}
                if isinstance(extra_meta, dict):
                    function_call_meta = extra_meta.get("function_call")
                    content_placeholder_reason = extra_meta.get("content_placeholder_reason")
                    tool_call_id_meta = extra_meta.get("tool_call_id")
                    stored_role = extra_meta.get("sender_role")
                    stored_name = extra_meta.get("sender_name")

            role_initial = map_sender_to_role(sender_val, character_card.get("name") if character_card else None)
            role = stored_role if stored_role in {"user", "assistant", "system", "tool"} else role_initial
            if not should_persist_message_role(role):
                continue
            char_name_hist = character_card.get("name", "Char") if character_card else "Char"
            text_content = db_msg.get("content", "")
            if text_content and role != "tool":
                text_content = replace_placeholders(text_content, char_name_hist, "User")
            msg_parts = []
            if text_content:
                msg_parts.append({"type": "text", "text": text_content})
            raw_images = db_msg.get("images") or []
            if (not raw_images) and db_msg.get("image_data") and db_msg.get("image_mime_type"):
                raw_images = [{
                    "position": 0,
                    "image_data": db_msg.get("image_data"),
                    "image_mime_type": db_msg.get("image_mime_type"),
                }]

            for image_entry in raw_images:
                try:
                    img_bytes = image_entry.get("image_data")
                    if isinstance(img_bytes, memoryview):
                        img_bytes = img_bytes.tobytes()
                    if not img_bytes:
                        continue
                    img_mime = image_entry.get("image_mime_type") or db_msg.get("image_mime_type") or "image/png"
                    b64_img = await loop.run_in_executor(None, base64.b64encode, img_bytes)
                    msg_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{img_mime};base64,{b64_img.decode('utf-8')}"}
                    })
                except _CHAT_NONCRITICAL_EXCEPTIONS as e:
                    logger.warning(f"Error encoding DB image for history (msg_id {db_msg.get('id')}): {e}")
            if msg_parts:
                hist_entry = {"role": role}
                if role == "tool" and len(msg_parts) == 1 and msg_parts[0].get("type") == "text":
                    hist_entry["content"] = msg_parts[0].get("text", "")
                else:
                    hist_entry["content"] = msg_parts
                if role == "assistant":
                    name_source = stored_name or (character_card.get("name") if character_card else None)
                    if name_source:
                        name = sanitize_sender_name(name_source)
                        if name:
                            hist_entry["name"] = name

                if tool_calls_meta is not None:
                    hist_entry["tool_calls"] = tool_calls_meta
                if function_call_meta and not hist_entry.get("tool_calls"):
                    hist_entry["function_call"] = function_call_meta
                if content_placeholder_reason in {"tool_calls", "function_call"}:
                    hist_entry["content"] = ""
                if role == "tool" and tool_call_id_meta:
                    hist_entry["tool_call_id"] = tool_call_id_meta
                if role == "tool" and not tool_call_id_meta:
                    logger.debug(
                        "Skipping tool message {} without tool_call_id metadata.",
                        db_msg.get("id"),
                    )
                    continue
                historical_msgs.append(hist_entry)
        logger.info(f"Loaded {len(historical_msgs)} historical messages for conv_id '{conv_id}'.")

    # Process current turn messages (persist if needed)
    request_messages: list[dict[str, Any]] = []
    for msg_model in request_data.messages:
        if not should_persist_message_role(msg_model.role):
            continue
        msg_dict = msg_model.model_dump(exclude_none=True)
        raw_name = msg_dict.get("name")
        if isinstance(raw_name, str) and raw_name.strip():
            sanitized = sanitize_sender_name(raw_name)
            if sanitized:
                msg_dict["name"] = sanitized
            else:
                msg_dict.pop("name", None)
        request_messages.append(msg_dict)

    # If the client included history with conversation_id, trim overlaps against DB history
    overlap_cut = 0
    if conv_id and historical_msgs and request_messages:
        has_non_user_role = any(
            msg.get("role") in {"assistant", "tool"} for msg in request_messages
        )
        all_user_roles = all(msg.get("role") == "user" for msg in request_messages)
        def _normalize_content(value: Any) -> Any:
            if isinstance(value, str):
                return [{"type": "text", "text": value}]
            if isinstance(value, list):
                return value
            return value

        def _msg_sig(msg: dict[str, Any]) -> str:
            payload = {
                "role": msg.get("role"),
                "content": _normalize_content(msg.get("content")),
                "tool_calls": msg.get("tool_calls"),
                "function_call": msg.get("function_call"),
                "tool_call_id": msg.get("tool_call_id"),
            }
            try:
                return _json.dumps(payload, sort_keys=True, default=str)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                return str(payload)

        if has_non_user_role:
            # Overlap detection assumes chronological ordering for comparison.
            # If history is requested newest-first, reverse a copy for overlap checks
            # while preserving the requested order in the final payload.
            hist_for_overlap = (
                list(reversed(historical_msgs)) if history_order == "desc" else historical_msgs
            )
            hist_sigs = [_msg_sig(m) for m in hist_for_overlap]
            req_sigs = [_msg_sig(m) for m in request_messages]
            max_k = min(len(hist_sigs), len(req_sigs))
            overlap_start = None
            overlap_k = 0
            for k in range(max_k, 0, -1):
                tail = hist_sigs[-k:]
                for i in range(0, len(req_sigs) - k + 1):
                    if req_sigs[i:i + k] == tail:
                        overlap_start = i
                        overlap_k = k
                        break
                if overlap_k:
                    break
            if overlap_k and overlap_start is not None:
                overlap_cut = overlap_start + overlap_k
                if overlap_cut > 0:
                    logger.debug(
                        "Trimmed %d request messages overlapping history for conv_id %s.",
                        overlap_cut,
                        conv_id,
                    )
        else:
            try:
                user_only_trim = str(os.getenv("CHAT_TRIM_USER_ONLY_OVERLAP", "false")).strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                user_only_trim = False
            if user_only_trim and all_user_roles:
                hist_for_overlap = (
                    list(reversed(historical_msgs)) if history_order == "desc" else historical_msgs
                )
                hist_sigs = [_msg_sig(m) for m in hist_for_overlap]
                req_sigs = [_msg_sig(m) for m in request_messages]
                if req_sigs and len(req_sigs) <= len(hist_sigs):
                    if hist_sigs[-len(req_sigs):] == req_sigs:
                        overlap_cut = len(req_sigs)
                        logger.debug(
                            "Trimmed %d user-only request messages overlapping history for conv_id %s.",
                            overlap_cut,
                            conv_id,
                        )

    current_turn: list[dict[str, Any]] = []
    for msg_dict in request_messages[overlap_cut:]:
        role = msg_dict.get("role")
        msg_for_db = msg_dict.copy()
        if role == "assistant" and character_card:
            # Persist assistant sender as sanitized character name
            msg_for_db["name"] = sanitize_sender_name(character_card.get("name", "Assistant"))
        if should_persist:
            await save_message_fn(chat_db, conv_id, msg_for_db, use_transaction=True)
        msg_for_llm = msg_dict.copy()
        if role == "assistant" and character_card and character_card.get("name"):
            name = sanitize_sender_name(character_card.get("name"))
            if name:
                msg_for_llm["name"] = name
        current_turn.append(msg_for_llm)

    # Preserve requested history ordering (DB fetch already honors ASC/DESC).
    historical_msgs_for_payload = historical_msgs

    llm_payload_messages = historical_msgs_for_payload + current_turn

    return character_card, character_db_id, conv_id, conversation_created, llm_payload_messages, should_persist


def _extract_system_messages(messages: list[dict[str, Any]]) -> list[str]:
    """Extract system message text content from OpenAI-style message payloads."""
    system_messages: list[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "system":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            text_val = content.strip()
            if text_val:
                system_messages.append(text_val)
            continue
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text_val = part.get("text")
                    if isinstance(text_val, str) and text_val.strip():
                        text_parts.append(text_val)
            combined = "\n".join(text_parts).strip()
            if combined:
                system_messages.append(combined)
    return system_messages


def _extract_system_messages_from_request(messages: list[Any]) -> list[str]:
    """Extract system messages from request model objects."""
    system_messages: list[str] = []
    for msg in messages or []:
        try:
            if getattr(msg, "role", None) != "system":
                continue
            content = getattr(msg, "content", None)
            if isinstance(content, str):
                text_val = content.strip()
                if text_val:
                    system_messages.append(text_val)
                continue
            if isinstance(content, list):
                text_parts: list[str] = []
                for part in content:
                    try_type = getattr(part, "type", None)
                    if try_type is None and isinstance(part, dict):
                        try_type = part.get("type")
                    if try_type == "text":
                        text_val = getattr(part, "text", None) if not isinstance(part, dict) else part.get("text")
                        if isinstance(text_val, str) and text_val.strip():
                            text_parts.append(text_val)
                combined = "\n".join(text_parts).strip()
                if combined:
                    system_messages.append(combined)
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            continue
    return system_messages


def apply_prompt_templating(
    request_data: Any,
    character_card: dict[str, Any],
    llm_payload_messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Compute final system message and apply content templating to payload messages.

    Returns (final_system_message, templated_llm_payload)
    """
    active_template = load_template(getattr(request_data, "prompt_template_name", None) or DEFAULT_RAW_PASSTHROUGH_TEMPLATE.name)
    template_data: dict[str, Any] = {}
    if character_card:
        template_data.update({k: v for k, v in character_card.items() if isinstance(v, (str, int, float))})
        template_data["char_name"] = character_card.get("name", "Character")
        template_data["character_system_prompt"] = character_card.get("system_prompt", "")

    system_msgs_from_request = _extract_system_messages_from_request(getattr(request_data, "messages", []))
    sys_msg_from_req = system_msgs_from_request[0] if system_msgs_from_request else None
    template_data["original_system_message_from_request"] = sys_msg_from_req or ""
    template_data["system_messages_from_request"] = "\n\n".join(system_msgs_from_request) if system_msgs_from_request else ""
    system_msgs_from_payload = _extract_system_messages(llm_payload_messages)
    payload_system_message = system_msgs_from_payload[-1] if system_msgs_from_payload else None
    template_data["system_messages_from_payload"] = "\n\n".join(system_msgs_from_payload) if system_msgs_from_payload else ""
    template_data["system_messages_combined"] = (
        template_data["system_messages_from_request"]
        or (payload_system_message or "")
    )

    final_system_message: str | None = None
    logger.debug(
        f"sys_msg_from_req: {sys_msg_from_req}, active_template: {active_template}, character: {character_card.get('name') if character_card else None}"
    )
    if active_template and active_template.system_message_template:
        final_system_message = apply_template_to_string(active_template.system_message_template, template_data)
        if not final_system_message and payload_system_message:
            final_system_message = payload_system_message
            system_prompt_preview = final_system_message[:50] if final_system_message else ""
            logger.debug(f"Template empty, using payload system message: {repr(system_prompt_preview)}...")
        if not final_system_message and character_card and character_card.get("system_prompt"):
            final_system_message = character_card.get("system_prompt")
            system_prompt_preview = final_system_message[:50] if final_system_message else ""
            logger.debug(f"Template empty, using character system prompt: {repr(system_prompt_preview)}...")
    elif sys_msg_from_req:
        final_system_message = sys_msg_from_req
    elif payload_system_message:
        final_system_message = payload_system_message
    elif character_card and character_card.get("system_prompt"):
        final_system_message = character_card.get("system_prompt")
        system_prompt_preview = final_system_message[:50] if final_system_message else ""
        logger.debug(f"Using character system prompt: {repr(system_prompt_preview)}...")

    logger.debug(f"Final system message: {repr(final_system_message)}")

    if final_system_message:
        llm_payload_messages = [m for m in llm_payload_messages if m.get("role") != "system"]

    templated_llm_payload: list[dict[str, Any]] = []
    if active_template:
        for msg in llm_payload_messages:
            templated_msg_content = msg.get("content")
            role = msg.get("role")
            content_template_str = None
            if role == "user" and active_template.user_message_content_template:
                content_template_str = active_template.user_message_content_template
            elif role == "assistant" and active_template.assistant_message_content_template:
                content_template_str = active_template.assistant_message_content_template
            if content_template_str:
                new_content_parts = []
                msg_template_data = template_data.copy()
                if isinstance(templated_msg_content, str):
                    msg_template_data["message_content"] = templated_msg_content
                    new_text = apply_template_to_string(content_template_str, msg_template_data)
                    new_content_parts.append({"type": "text", "text": new_text or templated_msg_content})
                elif isinstance(templated_msg_content, list):
                    for part in templated_msg_content:
                        if part.get("type") == "text":
                            msg_template_data["message_content"] = part.get("text", "")
                            new_text_part = apply_template_to_string(content_template_str, msg_template_data)
                            new_content_parts.append({"type": "text", "text": new_text_part or part.get("text", "")})
                        else:
                            new_content_parts.append(part)
                templated_llm_payload.append({**msg, "content": new_content_parts or templated_msg_content})
            else:
                templated_llm_payload.append(msg)
    else:
        templated_llm_payload = llm_payload_messages

    return final_system_message, templated_llm_payload


async def _maybe_refund_streaming_rg(
    rg_refund_cb: Callable[..., Any] | None,
    *,
    cancelled: bool = False,
    error: bool = True,
) -> None:
    """Best-effort RG refund hook for streaming failures before stream setup."""
    if not callable(rg_refund_cb):
        return
    try:
        res = rg_refund_cb(cancelled=cancelled, error=error)
        if hasattr(res, "__await__"):
            await res  # type: ignore[misc]
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        pass


async def execute_streaming_call(
    *,
    current_loop: Any,
    cleaned_args: dict[str, Any],
    selected_provider: str,
    provider: str,
    model: str,
    request_json: str,
    request: Any,
    metrics: Any,
    provider_manager: Any,
    templated_llm_payload: list[dict[str, Any]],
    should_persist: bool,
    final_conversation_id: str,
    character_card_for_context: dict[str, Any] | None,
    chat_db: Any,
    save_message_fn: Callable[..., Any],
    system_message_id: str | None = None,
    audit_service: Any | None,
    audit_context: Any | None,
    client_id: str,
    queue_execution_enabled: bool,
    enable_provider_fallback: bool,
    llm_call_func: Callable[[], Any],
    refresh_provider_params: Callable[[str], Any],
    moderation_getter: Callable[[], Any] | None = None,
    rg_commit_cb: Callable[[int], Any] | None = None,
    rg_refund_cb: Callable[..., Any] | None = None,
    on_success: Callable[[str], Awaitable[None]] | None = None,
) -> StreamingResponse:
    """Execute a streaming LLM call with queue, failover, moderation, and persistence.

    Returns a StreamingResponse that yields SSE chunks and handles:
    - provider call invocation and fallback
    - output moderation (chunk-wise)
    - saving final assistant message to DB
    - usage logging and audit success
    """
    llm_start_time = time.time()
    stream_metrics_recorded = False
    stream_failure_recorded = False
    raw_stream_iter: AsyncIterator[str] | Iterator[str] | None = None
    queue_for_exec = None
    queue_future: asyncio.Future[Any] | None = None
    queue_enabled = False
    try:
        try:
            queue_for_exec = get_request_queue()
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            queue_for_exec = None
        queue_enabled = (
            queue_execution_enabled
            and queue_for_exec is not None
            and queue_is_active(queue_for_exec)
        )

        if queue_enabled:
            # Submit streaming job to the queue and bridge chunks via channel
            # Bounded per-request channel for queued streaming; size is configurable via config.txt
            try:
                _maxsz_raw = os.getenv("CHAT_STREAM_CHANNEL_MAXSIZE")
                if not _maxsz_raw:
                    from tldw_Server_API.app.core.config import load_comprehensive_config
                    _cp = load_comprehensive_config()
                    _maxsz_raw = _cp.get('Chat-Module', 'chat_stream_channel_maxsize', fallback='100') if _cp else '100'
                stream_channel_maxsize = int(str(_maxsz_raw))
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                stream_channel_maxsize = 100
            stream_channel: asyncio.Queue = asyncio.Queue(maxsize=stream_channel_maxsize)
            est_tokens_for_queue = estimate_tokens_from_json(request_json)

            def _refresh_params_sync(target_provider: str) -> tuple[dict[str, Any], str | None]:
                """Resolve provider params inside a sync queue processor."""
                refreshed = refresh_provider_params(target_provider)
                if inspect.isawaitable(refreshed):
                    return asyncio.run(refreshed)  # Safe in executor thread
                return refreshed  # type: ignore[return-value]

            def _queued_processor():
                nonlocal selected_provider, model, llm_call_func, stream_failure_recorded
                local_start = time.time()
                try:
                    result = llm_call_func()
                    if selected_provider != provider:
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=selected_provider,
                                streaming=True,
                                queued=True,
                            )
                    return result
                except _CHAT_NONCRITICAL_EXCEPTIONS as proc_error:
                    latency = time.time() - local_start
                    metrics.track_llm_call(
                        selected_provider,
                        model,
                        latency,
                        success=False,
                        error_type=type(proc_error).__name__,
                    )
                    stream_failure_recorded = True
                    if provider_manager:
                        provider_manager.record_failure(selected_provider, proc_error)
                        name_lower = type(proc_error).__name__.lower()
                        client_like_error = (
                            "authentication" in name_lower
                            or "ratelimit" in name_lower
                            or "rate_limit" in name_lower
                            or "badrequest" in name_lower
                            or "bad_request" in name_lower
                            or "configuration" in name_lower
                        )
                        if enable_provider_fallback and isinstance(proc_error, (ChatProviderError, ChatAPIError)) and not client_like_error:
                            fallback_provider = provider_manager.get_available_provider(exclude=[selected_provider])
                            if fallback_provider:
                                logger.warning(
                                    f"Trying fallback provider {fallback_provider} after {selected_provider} failed (queued)"
                                )
                                try:
                                    refreshed_args, refreshed_model = _refresh_params_sync(fallback_provider)
                                    if not isinstance(refreshed_args, dict) or "messages_payload" not in refreshed_args:
                                        raise ValueError(
                                            f"Invalid refreshed params for {fallback_provider}: missing required fields"
                                        )
                                except _CHAT_NONCRITICAL_EXCEPTIONS as refresh_error:
                                    provider_manager.record_failure(fallback_provider, refresh_error)
                                    raise
                                model = refreshed_model or model
                                def llm_call_func_fb():
                                    return perform_chat_api_call(**refreshed_args)
                                try:
                                    result = llm_call_func_fb()
                                    selected_provider = fallback_provider
                                    llm_call_func = llm_call_func_fb
                                    with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                                        metrics.track_provider_fallback_success(
                                            requested_provider=provider,
                                            selected_provider=fallback_provider,
                                            streaming=True,
                                            queued=True,
                                        )
                                    return result
                                except _CHAT_NONCRITICAL_EXCEPTIONS as fallback_error:
                                    provider_manager.record_failure(fallback_provider, fallback_error)
                                    raise
                    raise

            queue_request_id = get_request_id() or "unknown"
            try:
                queue_future = await queue_for_exec.enqueue(
                    request_id=queue_request_id,
                    request_data={"endpoint": "/api/v1/chat/completions", "mode": "stream"},
                    client_id=str(client_id),
                    priority=RequestPriority.HIGH,
                    estimated_tokens=est_tokens_for_queue,
                    processor=_queued_processor,
                    processor_args=(),
                    processor_kwargs={},
                    streaming=True,
                    stream_channel=stream_channel,
                )
                _attach_queue_future_logger(queue_future, queue_request_id)
            except (ValueError, TimeoutError) as admission_error:
                with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                    metrics.track_rate_limit(str(client_id))
                detail = str(admission_error) or "Service busy. Please retry."
                status_code = (
                    status.HTTP_429_TOO_MANY_REQUESTS
                    if "rate limit" in detail.lower()
                    else status.HTTP_503_SERVICE_UNAVAILABLE
                )
                queue_exc = HTTPException(status_code=status_code, detail=detail)
                queue_exc._chat_queue_admission = True
                raise queue_exc

            async def _channel_stream():
                graceful_end = False
                try:
                    while True:
                        try:
                            # Add timeout to prevent indefinite hang if producer crashes
                            # without sending the sentinel None value
                            item = await asyncio.wait_for(
                                stream_channel.get(),
                                timeout=float(CHAT_IDLE_TIMEOUT)
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Stream channel get timed out after {}s - "
                                "producer may have crashed without sending sentinel",
                                CHAT_IDLE_TIMEOUT
                            )
                            try:
                                if queue_future is not None and not queue_future.done():
                                    queue_future.cancel()
                            except _CHAT_NONCRITICAL_EXCEPTIONS:
                                pass
                            try:
                                while True:
                                    stream_channel.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                            try:
                                error_payload = {
                                    "error": {
                                        "message": "Stream channel timed out waiting for queued response.",
                                        "type": "stream_timeout",
                                    }
                                }
                                yield f"data: {_json.dumps(error_payload)}\n\n"
                            except _CHAT_NONCRITICAL_EXCEPTIONS:
                                yield "data: {\"error\":{\"message\":\"Stream channel timed out waiting for queued response.\",\"type\":\"stream_timeout\"}}\n\n"
                            break
                        if item is None:
                            graceful_end = True
                            break
                        yield item
                except asyncio.CancelledError:
                    logger.info(
                        "Queued stream consumer cancelled for request {}; cancelling queued job",
                        queue_request_id,
                    )
                    raise
                finally:
                    # Pragmatic disconnect handling: cancel queued producer immediately so
                    # workers do not remain blocked waiting on a full channel.
                    if not graceful_end:
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            if queue_future is not None and not queue_future.done():
                                queue_future.cancel()
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            while True:
                                try:
                                    stream_channel.get_nowait()
                                except asyncio.QueueEmpty:
                                    break

            raw_stream_iter = _channel_stream()
        else:
            # Execute provided LLM call function in a worker to avoid blocking the loop.
            # llm_call_func is a sync callable (partial of perform_chat_api_call or a mock).
            raw_stream_iter = await current_loop.run_in_executor(None, llm_call_func)
            if selected_provider != provider:
                with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                    metrics.track_provider_fallback_success(
                        requested_provider=provider,
                        selected_provider=selected_provider,
                        streaming=True,
                        queued=False,
                    )
    except HTTPException as he:
        if getattr(he, "_chat_queue_admission", False):
            raise
        metrics.track_llm_call(
            selected_provider,
            model,
            time.time() - llm_start_time,
            success=False,
            error_type=type(he).__name__,
        )
        # For streaming endpoint semantics, emit SSE error + DONE instead of HTTP error
        # Bind error strings outside the generator to avoid Python 3.11+ exception scoping
        _err_msg = str(getattr(he, "detail", he))
        _err_type = type(he).__name__

        async def _err_gen(msg: str = _err_msg, typ: str = _err_type):
            try:
                import json as _json
                payload = {"error": {"message": msg, "type": typ}}
                if CHAT_STREAM_INCLUDE_METADATA and final_conversation_id:
                    payload["conversation_id"] = final_conversation_id
                    payload["tldw_conversation_id"] = final_conversation_id
                    if system_message_id:
                        payload["tldw_system_message_id"] = system_message_id
                yield f"data: {_json.dumps(payload)}\n\n"
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                # Fallback string serialization
                pass
                if CHAT_STREAM_INCLUDE_METADATA and final_conversation_id:
                    yield (
                        f"data: {{\"error\":{{\"message\":\"{msg}\",\"type\":\"{typ}\"}},"
                        f"\"conversation_id\":\"{final_conversation_id}\","
                        f"\"tldw_conversation_id\":\"{final_conversation_id}\"}}\n\n"
                    )
                else:
                    yield f"data: {{\"error\":{{\"message\":\"{msg}\",\"type\":\"{typ}\"}}}}\n\n"
            yield "data: [DONE]\n\n"
        await _maybe_refund_streaming_rg(rg_refund_cb, cancelled=False, error=True)
        return StreamingResponse(
            _err_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except _CHAT_NONCRITICAL_EXCEPTIONS as e:
        metrics.track_llm_call(
            selected_provider,
            model,
            time.time() - llm_start_time,
            success=False,
            error_type=type(e).__name__,
        )
        if provider_manager and not queue_enabled:
            provider_manager.record_failure(selected_provider, e)
            # Only fallback on upstream/server errors; skip fallback for client/config errors
            name_lower_e = type(e).__name__.lower()
            client_like_error = (
                "authentication" in name_lower_e
                or "ratelimit" in name_lower_e
                or "rate_limit" in name_lower_e
                or "badrequest" in name_lower_e
                or "bad_request" in name_lower_e
                or "configuration" in name_lower_e
            )
            if enable_provider_fallback and isinstance(e, (ChatProviderError, ChatAPIError)) and not client_like_error:
                fallback_provider = provider_manager.get_available_provider(exclude=[selected_provider])
                if fallback_provider:
                    logger.warning(f"Trying fallback provider {fallback_provider} after {selected_provider} failed")
                    try:
                        refreshed = refresh_provider_params(fallback_provider)
                        if hasattr(refreshed, "__await__"):
                            refreshed_args, refreshed_model = await refreshed  # type: ignore[misc]
                        else:
                            refreshed_args, refreshed_model = refreshed
                        # Validate refreshed params have required fields before proceeding
                        if not isinstance(refreshed_args, dict) or "messages_payload" not in refreshed_args:
                            raise ValueError(f"Invalid refreshed params for {fallback_provider}: missing required fields")
                    except _CHAT_NONCRITICAL_EXCEPTIONS as refresh_error:
                        provider_manager.record_failure(fallback_provider, refresh_error)
                        raise
                    cleaned_args = refreshed_args
                    model = refreshed_model or model
                    fallback_start_time = time.time()
                    def llm_call_func_fb():
                        return perform_chat_api_call(**cleaned_args)
                    try:
                        raw_stream_iter = await current_loop.run_in_executor(None, llm_call_func_fb)
                        fallback_latency = time.time() - fallback_start_time
                        provider_manager.record_success(fallback_provider, fallback_latency)
                        metrics.track_llm_call(fallback_provider, model, fallback_latency, success=True)
                        selected_provider = fallback_provider
                        llm_call_func = llm_call_func_fb
                        # Explicit telemetry for direct (non-queued) streaming fallback success
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=fallback_provider,
                                streaming=True,
                                queued=False,
                            )
                    except _CHAT_NONCRITICAL_EXCEPTIONS as fallback_error:
                        provider_manager.record_failure(fallback_provider, fallback_error)
                        raise
                else:
                    # No fallback available: stream SSE error (200) instead of raising
                    pass
            else:
                # Client/config errors in streaming mode: stream SSE error (200)
                pass
        else:
            # Queue path: stream SSE error as well
            pass

        # Safely capture exception details for streaming outside the closure
        _err_message = str(e)
        _err_type = type(e).__name__

        # New safe variant that does not reference the except-scope variable directly
        async def _safe_err_stream():
            try:
                import json as _json
                payload = {"error": {"message": _err_message, "type": _err_type}}
                if CHAT_STREAM_INCLUDE_METADATA and final_conversation_id:
                    payload["conversation_id"] = final_conversation_id
                    payload["tldw_conversation_id"] = final_conversation_id
                    if system_message_id:
                        payload["tldw_system_message_id"] = system_message_id
                yield f"data: {_json.dumps(payload)}\n\n"
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                if CHAT_STREAM_INCLUDE_METADATA and final_conversation_id:
                    yield (
                        f"data: {{\"error\":{{\"message\":\"{_err_message}\",\"type\":\"{_err_type}\"}},"
                        f"\"conversation_id\":\"{final_conversation_id}\","
                        f"\"tldw_conversation_id\":\"{final_conversation_id}\"}}\n\n"
                    )
                else:
                    yield f"data: {{\"error\":{{\"message\":\"{_err_message}\",\"type\":\"{_err_type}\"}}}}\n\n"
            yield "data: [DONE]\n\n"

        await _maybe_refund_streaming_rg(rg_refund_cb, cancelled=False, error=True)
        return StreamingResponse(
            _safe_err_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    if not (hasattr(raw_stream_iter, "__aiter__") or hasattr(raw_stream_iter, "__iter__")):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Provider did not return a valid stream.")

    stream_mod_state = {"block_logged": False, "redact_logged": False}

    async def save_callback(
        full_reply: str,
        tool_calls: list[dict[str, Any]] | None,
        function_call: dict[str, Any] | None,
    ):
        nonlocal stream_metrics_recorded
        saved_message_id: str | None = None
        full_reply_to_save = full_reply
        post_stream_blocked = False
        try:
            _get_mod = moderation_getter or get_moderation_service
            moderation = _get_mod()
            req_user_id = None
            try:
                if request is not None and hasattr(request, "state"):
                    req_user_id = getattr(request.state, "user_id", None)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                req_user_id = None
            eff_policy = moderation.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)
            if full_reply and eff_policy.enabled and eff_policy.output_enabled:
                action = None
                redacted = None
                sample = None
                category = None
                matched_pattern = None
                match_span = None
                if hasattr(moderation, "evaluate_action_with_match"):
                    eval_res = moderation.evaluate_action_with_match(full_reply, eff_policy, "output")
                    if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                        action, redacted, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                        category = eval_res[3] if len(eval_res) >= 4 else None
                        match_span = eval_res[4] if len(eval_res) >= 5 else None
                    else:
                        action, redacted, matched_pattern = eval_res  # type: ignore
                    if match_span and hasattr(moderation, "build_sanitized_snippet"):
                        try:
                            sample = moderation.build_sanitized_snippet(full_reply, eff_policy, match_span, matched_pattern)
                        except _CHAT_NONCRITICAL_EXCEPTIONS:
                            sample = None
                elif hasattr(moderation, "evaluate_action"):
                    eval_res = moderation.evaluate_action(full_reply, eff_policy, "output")
                    if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                        action, redacted, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                        category = eval_res[3] if len(eval_res) >= 4 else None
                    else:
                        action, redacted, matched_pattern = eval_res  # type: ignore
                if action and action != "pass" and sample is None:
                    try:
                        _, sample = moderation.check_text(full_reply, eff_policy, "output")
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        sample = None
                if action is None:
                    flagged, sample = moderation.check_text(full_reply, eff_policy, "output")
                    if flagged:
                        action = eff_policy.output_action
                        if action == "redact":
                            moderation.redact_text(full_reply, eff_policy)

                if action == "block":
                    if not stream_mod_state["block_logged"]:
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_moderation_stream_block(
                                str(req_user_id or client_id),
                                category=(category or "default"),
                            )
                        try:
                            if audit_service and audit_context:
                                _schedule_background_task(
                                    audit_service.log_event(
                                        event_type=AuditEventType.SECURITY_VIOLATION,
                                        context=audit_context,
                                        action="moderation.output",
                                        result="failure",
                                        metadata={
                                            "phase": "output",
                                            "streaming": True,
                                            "action": "block",
                                            "pattern": sample,
                                        },
                                    ),
                                    task_name="chat.stream.save.output.block.audit",
                                )
                        except _CHAT_NONCRITICAL_EXCEPTIONS:
                            pass
                        stream_mod_state["block_logged"] = True
                    post_stream_blocked = True
                    full_reply_to_save = None
                elif action == "redact":
                    if not stream_mod_state["redact_logged"]:
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_moderation_output(
                                str(req_user_id or client_id),
                                "redact",
                                streaming=True,
                                category=(category or "default"),
                            )
                        try:
                            if audit_service and audit_context:
                                _schedule_background_task(
                                    audit_service.log_event(
                                        event_type=AuditEventType.SECURITY_VIOLATION,
                                        context=audit_context,
                                        action="moderation.output",
                                        result="success",
                                        metadata={
                                            "phase": "output",
                                            "streaming": True,
                                            "action": "redact",
                                            "pattern": sample,
                                        },
                                    ),
                                    task_name="chat.stream.save.output.redact.audit",
                                )
                        except _CHAT_NONCRITICAL_EXCEPTIONS:
                            pass
                        stream_mod_state["redact_logged"] = True
                    full_reply_to_save = moderation.redact_text(full_reply, eff_policy)
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass

        if not stream_metrics_recorded:
            try:
                latency = time.time() - llm_start_time
                metrics.track_llm_call(selected_provider, model, latency, success=True)
                if provider_manager:
                    provider_manager.record_success(selected_provider, latency)
                stream_metrics_recorded = True
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                pass

        if should_persist and final_conversation_id and not post_stream_blocked and (
            full_reply_to_save or tool_calls or function_call
        ):
            asst_name = sanitize_sender_name(
                character_card_for_context.get("name") if character_card_for_context else None
            )
            message_payload: dict[str, Any] = {
                "role": "assistant",
                "name": asst_name,
            }
            if full_reply_to_save is not None:
                message_payload["content"] = full_reply_to_save
            if tool_calls:
                message_payload["tool_calls"] = tool_calls
            if function_call:
                message_payload["function_call"] = function_call
            saved_message_id = await save_message_fn(
                chat_db,
                final_conversation_id,
                message_payload,
                use_transaction=True,
            )
        # Usage logging (estimated) after stream completes
        total_est = 0
        try:
            pt_est = 0
            try:
                pt_est = _estimate_tokens_from_messages(templated_llm_payload)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                pt_est = 0
            ct_est = max(0, len(full_reply or "") // 4)
            user_id = None
            api_key_id = None
            try:
                if request is not None and hasattr(request, "state"):
                    user_id = getattr(request.state, "user_id", None)
                    api_key_id = getattr(request.state, "api_key_id", None)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                pass
            latency_ms = int((time.time() - llm_start_time) * 1000)
            total_est = int(pt_est + ct_est)
            await log_llm_usage(
                user_id=user_id,
                key_id=api_key_id,
                endpoint=(f"{request.method}:{request.url.path}" if request else "POST:/api/v1/chat/completions"),
                operation="chat",
                provider=selected_provider,
                model=model,
                status=200,
                latency_ms=latency_ms,
                prompt_tokens=int(pt_est),
                completion_tokens=int(ct_est),
                total_tokens=total_est,
                request_id=(request.headers.get("X-Request-ID") if request else None) or (get_request_id() or None),
                estimated=True,
            )
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass
        # Commit reserved tokens to Resource Governor, if provided
        try:
            if callable(rg_commit_cb):
                # rg_commit_cb may be async or sync; call accordingly
                res = rg_commit_cb(total_est)
                if hasattr(res, "__await__"):
                    await res  # type: ignore[misc]
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass
        # Audit success
        try:
            if audit_service and audit_context:
                await audit_service.log_event(
                    event_type=AuditEventType.API_RESPONSE,
                    context=audit_context,
                    action="chat_completion_success",
                    result="success",
                    metadata={
                        "conversation_id": final_conversation_id,
                        "provider": selected_provider,
                        "model": model,
                        "streaming": True,
                    },
                )
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass
        # BYOK usage tracking (best-effort)
        try:
            if callable(on_success):
                await on_success(selected_provider)
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass
        return saved_message_id

    async def tracked_streaming_generator():
        async with metrics.track_streaming(final_conversation_id) as stream_tracker:
            _get_mod = moderation_getter or get_moderation_service
            moderation = _get_mod()
            req_user_id = None
            try:
                if request is not None and hasattr(request, "state"):
                    req_user_id = getattr(request.state, "user_id", None)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                req_user_id = None
            eff_policy = moderation.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)

            from tldw_Server_API.app.core.Chat.streaming_utils import StopStreamWithError

            pending_audit_tasks: list[asyncio.Task[Any]] = []
            stream_id = _uuid.uuid4().hex
            chunk_seq = 0

            stream_holdback = ""
            try:
                stream_buffer_limit = int(os.getenv("MODERATION_STREAM_BUFFER_CHARS", "1024"))
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                stream_buffer_limit = 1024
            if stream_buffer_limit < 0:
                stream_buffer_limit = 0

            def _emit_with_holdback(text: str) -> str:
                nonlocal stream_holdback
                if stream_buffer_limit <= 0:
                    stream_holdback = ""
                    return text
                if not text:
                    return ""
                if len(text) <= stream_buffer_limit:
                    stream_holdback = text
                    return ""
                emit = text[:-stream_buffer_limit]
                stream_holdback = text[-stream_buffer_limit:]
                return emit

            def _flush_holdback() -> str:
                nonlocal stream_holdback
                if not stream_holdback:
                    return ""
                out = stream_holdback
                stream_holdback = ""
                return out

            def _out_transform(s: str) -> str:
                nonlocal chunk_seq
                try:
                    mon = None
                    try:
                        mon = get_topic_monitoring_service()
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        mon = None
                    team_ids = None
                    org_ids = None
                    try:
                        if request is not None and hasattr(request, "state"):
                            team_ids = getattr(request.state, "team_ids", None)
                            org_ids = getattr(request.state, "org_ids", None)
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        pass
                    if mon is not None and s:
                        chunk_seq += 1
                        chunk_id = f"{stream_id}:{chunk_seq}"
                        mon.schedule_evaluate_and_alert(
                            user_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            text=s,
                            source="chat.output",
                            scope_type="user",
                            scope_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            team_ids=team_ids,
                            org_ids=org_ids,
                            source_id=stream_id,
                            chunk_id=chunk_id,
                            chunk_seq=chunk_seq,
                        )
                except _CHAT_NONCRITICAL_EXCEPTIONS as _e:
                    logger.debug(f"Topic monitoring (stream chunk) skipped: {_e}")
                if not eff_policy.enabled or not eff_policy.output_enabled:
                    if stream_holdback:
                        out = f"{stream_holdback}{s}"
                        _flush_holdback()
                        return out
                    return s
                combined = f"{stream_holdback}{s}" if stream_holdback else s
                resolved_action = None
                matched_pattern = None
                sample = None
                redacted_combined = None
                out_category = None
                match_span = None
                if hasattr(moderation, "evaluate_action_with_match"):
                    try:
                        eval_res = moderation.evaluate_action_with_match(combined, eff_policy, "output")
                        if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                            resolved_action, redacted_combined, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                            out_category = eval_res[3] if len(eval_res) >= 4 else None
                            match_span = eval_res[4] if len(eval_res) >= 5 else None
                        else:
                            resolved_action, redacted_combined, matched_pattern = eval_res  # type: ignore
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        resolved_action = None
                    if match_span and hasattr(moderation, "build_sanitized_snippet"):
                        try:
                            sample = moderation.build_sanitized_snippet(combined, eff_policy, match_span, matched_pattern)
                        except _CHAT_NONCRITICAL_EXCEPTIONS:
                            sample = None
                elif hasattr(moderation, "evaluate_action"):
                    try:
                        eval_res = moderation.evaluate_action(combined, eff_policy, "output")
                        if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                            resolved_action, redacted_combined, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                            out_category = eval_res[3] if len(eval_res) >= 4 else None
                        else:
                            resolved_action, redacted_combined, matched_pattern = eval_res  # type: ignore
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        resolved_action = None
                if resolved_action and resolved_action != "pass" and sample is None:
                    try:
                        _, sample = moderation.check_text(combined, eff_policy, "output")
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        sample = None
                if not resolved_action:
                    flagged, sample = moderation.check_text(combined, eff_policy, "output")
                    if not flagged:
                        return _emit_with_holdback(combined)
                    resolved_action = eff_policy.output_action
                    redacted_combined = moderation.redact_text(combined, eff_policy) if resolved_action == "redact" else None
                if resolved_action == "block":
                    if not stream_mod_state["block_logged"]:
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_moderation_stream_block(str(req_user_id or client_id), category=(out_category or "default"))
                        try:
                            if audit_service and audit_context:
                                _schedule_background_task(
                                    audit_service.log_event(
                                        event_type=AuditEventType.SECURITY_VIOLATION,
                                        context=audit_context,
                                        action="moderation.output",
                                        result="failure",
                                        metadata={
                                            "phase": "output",
                                            "streaming": True,
                                            "action": "block",
                                            "pattern": sample,
                                        },
                                    ),
                                    task_name="chat.streaming.output.block.audit",
                                    pending_tasks=pending_audit_tasks,
                                )
                        except _CHAT_NONCRITICAL_EXCEPTIONS:
                            pass
                        stream_mod_state["block_logged"] = True
                    raise StopStreamWithError(message="Output violates moderation policy", error_type="output_moderation_block")
                if resolved_action == "redact":
                    if not stream_mod_state["redact_logged"]:
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_moderation_output(str(req_user_id or client_id), "redact", streaming=True, category=(out_category or "default"))
                        try:
                            if audit_service and audit_context:
                                _schedule_background_task(
                                    audit_service.log_event(
                                        event_type=AuditEventType.SECURITY_VIOLATION,
                                        context=audit_context,
                                        action="moderation.output",
                                        result="success",
                                        metadata={
                                            "phase": "output",
                                            "streaming": True,
                                            "action": "redact",
                                            "pattern": sample,
                                        },
                                    ),
                                    task_name="chat.streaming.output.redact.audit",
                                    pending_tasks=pending_audit_tasks,
                                )
                        except _CHAT_NONCRITICAL_EXCEPTIONS:
                            pass
                        stream_mod_state["redact_logged"] = True
                    redacted_out = (
                        redacted_combined
                        if isinstance(redacted_combined, str)
                        else moderation.redact_text(combined, eff_policy)
                    )
                    return _emit_with_holdback(redacted_out)
                return _emit_with_holdback(combined)

            # Allow streaming handler to flush any held-back tail at stream end
            with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                _out_transform.flush = _flush_holdback

            async def _finalize_stream(*, success: bool, cancelled: bool, error: bool) -> None:
                nonlocal stream_failure_recorded, stream_metrics_recorded
                if not success and not stream_failure_recorded and not stream_metrics_recorded:
                    try:
                        latency = time.time() - llm_start_time
                        if cancelled:
                            error_type = "stream_cancelled"
                        elif error:
                            error_type = "stream_error"
                        else:
                            error_type = "stream_incomplete"
                        metrics.track_llm_call(
                            selected_provider,
                            model,
                            latency,
                            success=False,
                            error_type=error_type,
                        )
                        if provider_manager and error and not cancelled:
                            provider_manager.record_failure(selected_provider, RuntimeError(error_type))
                        stream_failure_recorded = True
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        pass
                if success:
                    return
                if callable(rg_refund_cb):
                    res = rg_refund_cb(cancelled=cancelled, error=error)
                    if hasattr(res, "__await__"):
                        await res  # type: ignore[misc]

            generator = create_streaming_response_with_timeout(
                stream=raw_stream_iter,  # type: ignore[arg-type]
                conversation_id=final_conversation_id,
                model_name=model,
                save_callback=save_callback,
                finalize_callback=_finalize_stream,
                idle_timeout=CHAT_IDLE_TIMEOUT,
                heartbeat_interval=CHAT_HEARTBEAT_INTERVAL,
                text_transform=_out_transform,
                system_message_id=system_message_id,
            )
            try:
                async for chunk in generator:
                    if "heartbeat" in chunk:
                        stream_tracker.add_heartbeat()
                    else:
                        stream_tracker.add_chunk()
                    yield chunk
            finally:
                if pending_audit_tasks:
                    await asyncio.gather(*pending_audit_tasks, return_exceptions=True)

    streaming_generator = tracked_streaming_generator()

    # Feature-flagged: route through unified SSE abstraction for pilot
    try:
        use_unified = str(os.getenv("STREAMS_UNIFIED", "0")).strip().lower() in {"1", "true", "yes", "on"}
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        use_unified = False

    if use_unified:
        # Use SSEStream to standardize lifecycle + metrics; forward lines from the
        # existing tracked generator, filtering provider [DONE] and emitting our own.
        from tldw_Server_API.app.core.Streaming.streams import SSEStream

        sse_stream = SSEStream(labels={"component": "chat", "endpoint": "chat_completions_stream"})
        done_seen = False

        async def _produce():
            nonlocal done_seen
            try:
                async for ln in streaming_generator:
                    if not ln:
                        continue
                    if ln.strip().lower() == "data: [done]":
                        # Suppress provider DONE; emit unified DONE immediately and stop producing
                        if not done_seen:
                            await sse_stream.done()
                            done_seen = True
                        break
                    await sse_stream.send_raw_sse_line(ln)
                if not done_seen:
                    await sse_stream.done()
            except _CHAT_NONCRITICAL_EXCEPTIONS as e:
                # As a safeguard; tracked_streaming_generator typically yields error frames itself
                pass
                await sse_stream.error("internal_error", f"{e}")

        async def _gen():
            prod = asyncio.create_task(_produce())
            try:
                async for line in sse_stream.iter_sse():
                    yield line
            except asyncio.CancelledError:
                # Cancel producer promptly on client disconnect
                if not prod.done():
                    with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                        prod.cancel()
                    with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                        await prod
                raise
            else:
                # Normal shutdown: ensure producer completes cleanly
                if not prod.done():
                    with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                        await prod

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Legacy path: return the tracked generator directly
    return StreamingResponse(
        streaming_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def execute_non_stream_call(
    *,
    current_loop: Any,
    cleaned_args: dict[str, Any],
    selected_provider: str,
    provider: str,
    model: str,
    request_json: str,
    request: Any,
    metrics: Any,
    provider_manager: Any,
    templated_llm_payload: list[dict[str, Any]],
    should_persist: bool,
    final_conversation_id: str,
    character_card_for_context: dict[str, Any] | None,
    chat_db: Any,
    save_message_fn: Callable[..., Any],
    system_message_id: str | None = None,
    audit_service: Any | None,
    audit_context: Any | None,
    client_id: str,
    queue_execution_enabled: bool,
    enable_provider_fallback: bool,
    llm_call_func: Callable[[], Any],
    refresh_provider_params: Callable[[str], Any],
    moderation_getter: Callable[[], Any] | None = None,
    on_success: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Execute a non-streaming LLM call with queue, failover, moderation, and persistence.

    Returns the encoded payload (dict) ready to be wrapped by JSONResponse.
    """
    llm_start_time = time.time()
    llm_response = None
    metrics_recorded = False
    queue_failure_recorded = False
    queue_enabled = False
    try:
        queue_for_exec = None
        try:
            queue_for_exec = get_request_queue()
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            queue_for_exec = None
        queue_enabled = (
            queue_execution_enabled
            and queue_for_exec is not None
            and queue_is_active(queue_for_exec)
        )
        if queue_enabled:
            est_tokens_for_queue = estimate_tokens_from_json(request_json)
            def _queued_processor():
                nonlocal queue_failure_recorded
                local_start = time.time()
                try:
                    result = llm_call_func()
                    latency = time.time() - local_start
                    metrics.track_llm_call(selected_provider, model, latency, success=True)
                    if provider_manager:
                        provider_manager.record_success(selected_provider, latency)
                    if selected_provider != provider:
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=selected_provider,
                                streaming=False,
                                queued=True,
                            )
                    return result
                except _CHAT_NONCRITICAL_EXCEPTIONS as proc_error:
                    latency = time.time() - local_start
                    metrics.track_llm_call(
                        selected_provider,
                        model,
                        latency,
                        success=False,
                        error_type=type(proc_error).__name__,
                    )
                    if provider_manager:
                        provider_manager.record_failure(selected_provider, proc_error)
                    queue_failure_recorded = True
                    raise

            try:
                fut = await queue_for_exec.enqueue(
                    request_id=(get_request_id() or "unknown"),
                    request_data={"endpoint": "/api/v1/chat/completions", "mode": "non-stream"},
                    client_id=str(client_id),
                    priority=RequestPriority.NORMAL,
                    estimated_tokens=est_tokens_for_queue,
                    processor=_queued_processor,
                    processor_args=(),
                    processor_kwargs={},
                    streaming=False,
                    stream_channel=None,
                )
            except (ValueError, TimeoutError) as admission_error:
                with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                    metrics.track_rate_limit(str(client_id))
                detail = str(admission_error) or "Service busy. Please retry."
                status_code = (
                    status.HTTP_429_TOO_MANY_REQUESTS
                    if "rate limit" in detail.lower()
                    else status.HTTP_503_SERVICE_UNAVAILABLE
                )
                queue_exc = HTTPException(status_code=status_code, detail=detail)
                queue_exc._chat_queue_admission = True
                raise queue_exc
            llm_response = await fut
            metrics_recorded = True
        else:
            # Execute provided LLM call function in a worker to avoid blocking the loop.
            # llm_call_func is a sync callable (partial of perform_chat_api_call or a mock).
            loop = asyncio.get_running_loop()
            llm_response = await loop.run_in_executor(None, llm_call_func)
        llm_latency = time.time() - llm_start_time
        if not metrics_recorded:
            metrics.track_llm_call(selected_provider, model, llm_latency, success=True)
            if provider_manager:
                provider_manager.record_success(selected_provider, llm_latency)
            if selected_provider != provider:
                with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                    metrics.track_provider_fallback_success(
                        requested_provider=provider,
                        selected_provider=selected_provider,
                        streaming=False,
                        queued=False,
                    )
    except HTTPException as he:
        if getattr(he, "_chat_queue_admission", False):
            raise
        raise
    except _CHAT_NONCRITICAL_EXCEPTIONS as e:
        llm_latency = time.time() - llm_start_time
        if not queue_failure_recorded:
            metrics.track_llm_call(
                selected_provider,
                model,
                llm_latency,
                success=False,
                error_type=type(e).__name__,
            )
            if provider_manager:
                provider_manager.record_failure(selected_provider, e)

        if provider_manager:
            name_lower_e = type(e).__name__.lower()
            client_like_error = (
                "authentication" in name_lower_e
                or "ratelimit" in name_lower_e
                or "rate_limit" in name_lower_e
                or "badrequest" in name_lower_e
                or "bad_request" in name_lower_e
                or "configuration" in name_lower_e
            )
            if enable_provider_fallback and isinstance(e, (ChatProviderError, ChatAPIError)) and not client_like_error:
                fallback_provider = provider_manager.get_available_provider(exclude=[selected_provider])
                if fallback_provider:
                    logger.warning(f"Trying fallback provider {fallback_provider} after {selected_provider} failed")
                    try:
                        refreshed = refresh_provider_params(fallback_provider)
                        if hasattr(refreshed, "__await__"):
                            refreshed_args, refreshed_model = await refreshed  # type: ignore[misc]
                        else:
                            refreshed_args, refreshed_model = refreshed
                        # Validate refreshed params have required fields before proceeding
                        if not isinstance(refreshed_args, dict) or "messages_payload" not in refreshed_args:
                            raise ValueError(
                                f"Invalid refreshed params for {fallback_provider}: missing required fields"
                            )
                    except _CHAT_NONCRITICAL_EXCEPTIONS as refresh_error:
                        provider_manager.record_failure(fallback_provider, refresh_error)
                        raise
                    cleaned_args = refreshed_args
                    model = refreshed_model or model
                    fallback_start_time = time.time()
                    try:
                        llm_response = await perform_chat_api_call_async(**cleaned_args)
                        fallback_latency = time.time() - fallback_start_time
                        provider_manager.record_success(fallback_provider, fallback_latency)
                        metrics.track_llm_call(fallback_provider, model, fallback_latency, success=True)
                        selected_provider = fallback_provider
                        metrics_recorded = True
                        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=fallback_provider,
                                streaming=False,
                                queued=False,
                            )
                    except _CHAT_NONCRITICAL_EXCEPTIONS as fallback_error:
                        provider_manager.record_failure(fallback_provider, fallback_error)
                        raise
                else:
                    raise
            else:
                raise
        else:
            raise

    if isinstance(llm_response, str) and should_force_normalize_string_responses():
        llm_response = _wrap_raw_string_response(llm_response, model)

    content_to_save: str | None = None
    tool_calls_to_save: Any | None = None
    function_call_to_save: Any | None = None
    if llm_response and isinstance(llm_response, dict):
        choices = llm_response.get("choices")
        if choices and isinstance(choices, list) and len(choices) > 0:
            message_block = choices[0].get("message") or {}
            if isinstance(message_block, dict):
                content_to_save = message_block.get("content")
                tool_calls_to_save = message_block.get("tool_calls")
                function_call_to_save = message_block.get("function_call")
        usage = llm_response.get("usage")
        if usage:
            try:
                prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                metrics.track_tokens(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model=model,
                    provider=selected_provider,
                )
                user_id = None
                api_key_id = None
                try:
                    if request is not None and hasattr(request, "state"):
                        user_id = getattr(request.state, "user_id", None)
                        api_key_id = getattr(request.state, "api_key_id", None)
                except _CHAT_NONCRITICAL_EXCEPTIONS:
                    pass
                await log_llm_usage(
                    user_id=user_id,
                    key_id=api_key_id,
                    endpoint=(f"{request.method}:{request.url.path}" if request else "POST:/api/v1/chat/completions"),
                    operation="chat",
                    provider=selected_provider,
                    model=model,
                    status=200,
                    latency_ms=int((time.time() - llm_start_time) * 1000),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=int((usage.get("total_tokens") or 0) or (prompt_tokens + completion_tokens)),
                    request_id=(request.headers.get("X-Request-ID") if request else None) or (get_request_id() or None),
                )
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                pass
        else:
            # Estimate usage if not provided
            try:
                pt_est = 0
                try:
                    pt_est = _estimate_tokens_from_messages(templated_llm_payload)
                except _CHAT_NONCRITICAL_EXCEPTIONS:
                    pt_est = 0
                content_text_for_usage = _extract_text_from_content(content_to_save)
                ct_est = max(0, len(content_text_for_usage) // 4)
                user_id = None
                api_key_id = None
                try:
                    if request is not None and hasattr(request, "state"):
                        user_id = getattr(request.state, "user_id", None)
                        api_key_id = getattr(request.state, "api_key_id", None)
                except _CHAT_NONCRITICAL_EXCEPTIONS:
                    pass
                await log_llm_usage(
                    user_id=user_id,
                    key_id=api_key_id,
                    endpoint=(f"{request.method}:{request.url.path}" if request else "POST:/api/v1/chat/completions"),
                    operation="chat",
                    provider=selected_provider,
                    model=model,
                    status=200,
                    latency_ms=int((time.time() - llm_start_time) * 1000),
                    prompt_tokens=int(pt_est),
                    completion_tokens=int(ct_est),
                    total_tokens=int(pt_est + ct_est),
                    request_id=(request.headers.get("X-Request-ID") if request else None) or (get_request_id() or None),
                    estimated=True,
                )
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                pass
    elif isinstance(llm_response, str):
        content_to_save = llm_response
    elif llm_response is None:
        raise ChatProviderError(provider=provider, message="Provider unavailable or returned no response", status_code=502)

    # Cache content text for moderation/usage when content is non-string
    content_text_for_usage = _extract_text_from_content(content_to_save)

    # Output moderation (non-streaming)
    try:
        if content_text_for_usage:
            _get_mod = moderation_getter or get_moderation_service
            moderation = _get_mod()
            req_user_id = None
            try:
                if request is not None and hasattr(request, "state"):
                    req_user_id = getattr(request.state, "user_id", None)
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                req_user_id = None
            eff_policy = moderation.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)
            if eff_policy.enabled and eff_policy.output_enabled:
                resolved_action = None
                sample = None
                redacted_val = None
                out_category2 = None
                matched_pattern = None
                match_span = None
                if hasattr(moderation, "evaluate_action_with_match"):
                    try:
                        eval_res = moderation.evaluate_action_with_match(content_text_for_usage, eff_policy, "output")
                        if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                            resolved_action, redacted_val, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                            out_category2 = eval_res[3] if len(eval_res) >= 4 else None
                            match_span = eval_res[4] if len(eval_res) >= 5 else None
                        else:
                            resolved_action, redacted_val, matched_pattern = eval_res  # type: ignore
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        resolved_action = None
                    if match_span and hasattr(moderation, "build_sanitized_snippet"):
                        try:
                            sample = moderation.build_sanitized_snippet(content_text_for_usage, eff_policy, match_span, matched_pattern)
                        except _CHAT_NONCRITICAL_EXCEPTIONS:
                            sample = None
                elif hasattr(moderation, "evaluate_action"):
                    try:
                        eval_res = moderation.evaluate_action(content_text_for_usage, eff_policy, "output")
                        if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                            resolved_action, redacted_val, matched_pattern = eval_res[0], eval_res[1], eval_res[2]
                            out_category2 = eval_res[3] if len(eval_res) >= 4 else None
                        else:
                            resolved_action, redacted_val, matched_pattern = eval_res  # type: ignore
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        resolved_action = None
                if resolved_action and resolved_action != "pass" and sample is None:
                    try:
                        _, sample = moderation.check_text(content_text_for_usage, eff_policy, "output")
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        sample = None
                if not resolved_action:
                    flagged, sample = moderation.check_text(content_text_for_usage, eff_policy, "output")
                    if flagged:
                        resolved_action = eff_policy.output_action
                        redacted_val = moderation.redact_text(content_text_for_usage, eff_policy) if resolved_action == "redact" else None
                # Topic monitoring (final output)
                try:
                    mon3 = None
                    try:
                        mon3 = get_topic_monitoring_service()
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        mon3 = None
                    team_ids = None
                    org_ids = None
                    try:
                        if request is not None and hasattr(request, "state"):
                            team_ids = getattr(request.state, "team_ids", None)
                            org_ids = getattr(request.state, "org_ids", None)
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        pass
                    if mon3 is not None and content_text_for_usage:
                        mon3.schedule_evaluate_and_alert(
                            user_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            text=content_text_for_usage,
                            source="chat.output",
                            scope_type="user",
                            scope_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            team_ids=team_ids,
                            org_ids=org_ids,
                            source_id=str(final_conversation_id) if final_conversation_id else None,
                        )
                except _CHAT_NONCRITICAL_EXCEPTIONS as _ex:
                    logger.debug(f"Topic monitoring (non-stream final) skipped: {_ex}")

                if resolved_action == "block":
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Output violates moderation policy")
                if resolved_action == "redact":
                    try:
                        if sample is not None:
                            metrics.track_moderation_output(str(req_user_id or client_id), "redact", streaming=False, category=(out_category2 or "default"))
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        pass
                    try:
                        if audit_service and audit_context:
                            await audit_service.log_event(
                                event_type=AuditEventType.SECURITY_VIOLATION,
                                context=audit_context,
                                action="moderation.output",
                                result="success",
                                metadata={
                                    "phase": "output",
                                    "streaming": False,
                                    "action": "redact",
                                    "pattern": sample,
                                },
                            )
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        pass
                    if isinstance(content_to_save, str):
                        content_to_save = (
                            redacted_val
                            if isinstance(redacted_val, str)
                            else moderation.redact_text(content_text_for_usage, eff_policy)
                        )
                    else:
                        content_to_save = _apply_redaction_to_content(content_to_save, moderation, eff_policy)
                    # Update llm_response dict if applicable
                    try:
                        if isinstance(llm_response, dict):
                            if llm_response.get("choices") and isinstance(llm_response["choices"], list) and llm_response["choices"]:
                                msg = llm_response["choices"][0].get("message") or {}
                                if isinstance(msg, dict):
                                    msg["content"] = content_to_save
                    except _CHAT_NONCRITICAL_EXCEPTIONS:
                        pass
    except HTTPException:
        raise
    except _CHAT_NONCRITICAL_EXCEPTIONS as e:
        logger.warning(f"Moderation output processing error: {e}")

    assistant_message_id: str | None = None
    should_save_response = (
        should_persist
        and final_conversation_id
        and (content_to_save or tool_calls_to_save or function_call_to_save)
    )
    if should_save_response:
        asst_name = sanitize_sender_name(
            character_card_for_context.get("name") if character_card_for_context else None
        )
        message_payload: dict[str, Any] = {"role": "assistant", "name": asst_name}
        if content_to_save is not None:
            message_payload["content"] = content_to_save
        if tool_calls_to_save is not None:
            message_payload["tool_calls"] = tool_calls_to_save
        if function_call_to_save is not None:
            message_payload["function_call"] = function_call_to_save
        assistant_message_id = await save_message_fn(
            chat_db,
            final_conversation_id,
            message_payload,
            use_transaction=True,
        )

    if INJECT_ASSISTANT_NAME and isinstance(llm_response, dict):
        try:
            choices = llm_response.get("choices")
            if choices and isinstance(choices, list):
                message_block = choices[0].get("message") or {}
                if isinstance(message_block, dict) and not message_block.get("name"):
                    asst_name = sanitize_sender_name(
                        character_card_for_context.get("name") if character_card_for_context else None
                    )
                    if asst_name:
                        message_block["name"] = asst_name
        except _CHAT_NONCRITICAL_EXCEPTIONS:
            pass

    # Encode payload (large responses via CPU-bound handler)
    if llm_response and isinstance(llm_response, dict) and len(str(llm_response)) > 10000:
        encoded_json = await process_large_json_async(llm_response)
        encoded_payload = _json.loads(encoded_json)
    else:
        encoded_payload = await current_loop.run_in_executor(None, jsonable_encoder, llm_response)

    if isinstance(encoded_payload, dict):
        if INJECT_ASSISTANT_NAME:
            try:
                choices = encoded_payload.get("choices")
                if choices and isinstance(choices, list):
                    message_block = choices[0].get("message") or {}
                    if isinstance(message_block, dict) and not message_block.get("name"):
                        asst_name = sanitize_sender_name(
                            character_card_for_context.get("name") if character_card_for_context else None
                        )
                        if asst_name:
                            message_block["name"] = asst_name
            except _CHAT_NONCRITICAL_EXCEPTIONS:
                pass
        encoded_payload["tldw_conversation_id"] = final_conversation_id
        if assistant_message_id:
            encoded_payload["tldw_message_id"] = assistant_message_id
        if system_message_id:
            encoded_payload["tldw_system_message_id"] = system_message_id

    # Audit success
    if audit_service and audit_context:
        with contextlib.suppress(_CHAT_NONCRITICAL_EXCEPTIONS):
            await audit_service.log_event(
                event_type=AuditEventType.API_RESPONSE,
                context=audit_context,
                action="chat_completion_success",
                result="success",
                metadata={
                    "conversation_id": final_conversation_id,
                    "provider": selected_provider,
                    "model": model,
                    "streaming": False,
                },
            )

    # BYOK usage tracking (best-effort)
    try:
        if callable(on_success):
            await on_success(selected_provider)
    except _CHAT_NONCRITICAL_EXCEPTIONS:
        pass

    return encoded_payload
