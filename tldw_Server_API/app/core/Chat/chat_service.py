"""
chat_service.py
Lightweight helpers to keep the chat endpoint readable and testable without changing behavior.

These functions encapsulate small, deterministic pieces of logic used by
the /api/v1/chat/completions endpoint so the endpoint can orchestrate at a
higher level. The goal is to reduce duplication and cognitive load while
keeping the wire behavior identical.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List, Callable, AsyncIterator, Iterator, Awaitable
from fastapi import HTTPException, status
from loguru import logger
import base64
import uuid as _uuid
import asyncio
import time
import json as _json
import os
from pathlib import Path
from functools import lru_cache

# Reuse existing helpers from chat_helpers and prompt templating
from tldw_Server_API.app.core.Chat.chat_helpers import (
    get_or_create_character_context,
    get_or_create_conversation,
)
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import replace_placeholders
from tldw_Server_API.app.core.Character_Chat.modules.character_utils import (
    map_sender_to_role,
    sanitize_sender_name,
)
from tldw_Server_API.app.core.Chat.message_utils import should_persist_message_role
from tldw_Server_API.app.core.Chat.prompt_template_manager import (
    DEFAULT_RAW_PASSTHROUGH_TEMPLATE,
    load_template,
    apply_template_to_string,
)
from tldw_Server_API.app.core.Chat.chat_orchestrator import (
    chat_api_call as perform_chat_api_call,
    chat_api_call_async as perform_chat_api_call_async,
)
from tldw_Server_API.app.core.Chat.streaming_utils import (
    create_streaming_response_with_timeout,
)
from tldw_Server_API.app.core.Chat.streaming_utils import (
    HEARTBEAT_INTERVAL as CHAT_HEARTBEAT_INTERVAL,
    STREAMING_IDLE_TIMEOUT as CHAT_IDLE_TIMEOUT,
)
from tldw_Server_API.app.core.Chat.request_queue import (
    get_request_queue,
    RequestPriority,
)
from tldw_Server_API.app.core.Moderation.moderation_service import get_moderation_service
from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
from tldw_Server_API.app.core.Chat.Chat_Deps import (
    ChatAPIError,
    ChatProviderError,
)
from tldw_Server_API.app.core.Usage.usage_tracker import log_llm_usage
from tldw_Server_API.app.core.Chat.chat_exceptions import get_request_id
from fastapi.encoders import jsonable_encoder
from tldw_Server_API.app.core.Utils.cpu_bound_handler import process_large_json_async
from starlette.responses import StreamingResponse
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditEventType
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.Usage.pricing_catalog import list_provider_models

_config = load_comprehensive_config()
_chat_config: Dict[str, str] = {}
if _config and _config.has_section("Chat-Module"):
    _chat_config = dict(_config.items("Chat-Module"))


def _coerce_int(value: Optional[str], default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


_MAX_HISTORY_MESSAGES = max(1, _coerce_int(_chat_config.get("max_history_messages"), 200))

_default_history_limit = 20
if "history_messages_limit" in _chat_config:
    _default_history_limit = max(
        1,
        min(_MAX_HISTORY_MESSAGES, _coerce_int(_chat_config.get("history_messages_limit"), _default_history_limit)),
    )
_env_history_limit = os.getenv("CHAT_HISTORY_LIMIT")
if _env_history_limit:
    try:
        _default_history_limit = max(1, min(_MAX_HISTORY_MESSAGES, int(_env_history_limit)))
    except Exception:
        pass
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


# --- Cached helpers (module scope) -------------------------------------------
@lru_cache(maxsize=16)
def _load_models_with_case_cached(provider: str) -> List[str]:
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
    except Exception as _ue:
        # Unexpected exceptions should be visible in production logs
        logger.warning(f"Unexpected error loading model catalog for provider '{provider}': {_ue}")

    # Fallback: use the normalized list (lowercase keys)
    return list_provider_models(provider) or []


@lru_cache(maxsize=1)
def _load_alias_overrides_cached() -> Dict[str, Dict[str, str]]:
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
    except Exception as _ue:
        # Unexpected exceptions should be visible in production logs
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
    except Exception as _ue:
        # Unexpected exceptions should be visible in production logs
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
    try:
        _load_models_with_case_cached.cache_clear()
    except Exception:
        pass
    try:
        _load_alias_overrides_cached.cache_clear()
    except Exception:
        pass


def queue_is_active(queue: Any) -> bool:
    """Return True when the request queue is running and able to process work."""
    try:
        status = getattr(queue, "is_running")
    except AttributeError:
        status = None
    if callable(status):
        try:
            result = status()
            if result is not None:
                return bool(result)
        except Exception:
            pass
    elif status is not None:
        return bool(status)

    fallback_state = getattr(queue, "_running", None)
    if fallback_state is not None:
        return bool(fallback_state)
    # Assume truthy for lightweight test stubs that do not expose state
    return True


def parse_provider_model_for_metrics(
    request_data: Any,
    default_provider: str,
) -> Tuple[str, str]:
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
    # Use pricing catalog (and raw file when available) to pick a concrete model
    # for aliases like "claude-sonnet". Preserve mapped casing from the source.
    try:
        # Determine provider context for alias resolution.
        # If model includes an inline provider (e.g., "anthropic/claude-sonnet"),
        # prefer that; else honor api_provider, then default_provider.
        inline_provider: Optional[str] = None
        inline_model_part: Optional[str] = None
        if "/" in model_str:
            parts_for_alias = model_str.split("/", 1)
            if len(parts_for_alias) == 2:
                inline_provider, inline_model_part = parts_for_alias[0].strip(), parts_for_alias[1].strip()
        provider_for_mapping = ((inline_provider or api_provider or default_provider) or "").strip().lower()


        def _resolve_alias(provider: str, raw_model: str) -> Optional[str]:
            m = (raw_model or "").strip()
            if not m:
                return None
            models = _load_models_with_case_cached(provider)
            if not models:
                return None
            m_lower = m.lower()
            # 1) Exact (case-insensitive) match
            for cand in models:
                if cand.lower() == m_lower:
                    return cand
            # 2) Prefer anchored prefix (alias + '-') to choose family head, e.g., 'claude-sonnet' -> 'claude-sonnet-4.5'
            anchored = [cand for cand in models if cand.lower().startswith(m_lower + "-")]
            if anchored:
                # Pick the longest name to bias towards more specific (likely newer) variants
                return sorted(anchored, key=lambda s: (len(s), s))[-1]
            # 3) Substring fallback
            contains = [cand for cand in models if m_lower in cand.lower()]
            if contains:
                # Prefer shorter names to avoid overly specific accidental matches
                return sorted(contains, key=lambda s: (len(s), s))[0]
            # 4) Soft default: pick a small/mini/tiny if present; else first sorted
            priority = ["mini", "small", "tiny", "haiku", "flash"]
            prioritized = [cand for cand in models if any(p in cand.lower() for p in priority)]
            if prioritized:
                return sorted(prioritized)[0]
            return sorted(models)[0]

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
    except Exception as _unexpected:
        # Unexpected exceptions should be visible in production logs
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
                setattr(request_data, "model", actual_model)
            else:
                # api_provider is explicitly set on the request. For OpenRouter, many valid
                # model IDs include a provider namespace (e.g., "openai/gpt-4o-mini",
                # "z-ai/glm-4.6"). OpenRouter expects that namespace to be preserved.
                # Only strip when the inline namespace is literally "openrouter";
                # otherwise, keep the full "namespace/model" string.
                if provider == "openrouter":
                    if inline_provider_lower == "openrouter":
                        setattr(request_data, "model", actual_model)
                    else:
                        # Keep the namespaced model id as-is for OpenRouter
                        setattr(request_data, "model", model_str)
                else:
                    # Non-OpenRouter providers do not use namespaced model ids; strip prefix
                    setattr(request_data, "model", actual_model)
    return provider


def resolve_provider_and_model(
    request_data: Any,
    metrics_default_provider: str,
    normalize_default_provider: str,
) -> Tuple[str, str, str, str, Dict[str, Any]]:
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
    except Exception as exc:
        # Do not block the request if normalization fails; fall back to metrics values.
        logger.debug(
            "resolve_provider_and_model: normalization failed, "
            "falling back to metrics provider/model. Error={}",
            exc,
        )

    debug_info: Dict[str, Any] = {
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
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Resolve the API key for a provider using env/config first, with optional test overrides.

    Resolution order:
    1) In test contexts (PYTEST_CURRENT_TEST or TEST_MODE) and when prefer_module_keys_in_tests=True,
       use module-level API_KEYS (schemas first, then endpoint) if present for the provider.
    2) Otherwise, return the dynamic key from get_api_keys() (env/config/dotenv).
    Returns (normalized_key, debug_info).
    """
    provider_key = (provider or "").strip().lower()
    debug_info: Dict[str, Any] = {
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
    except Exception:
        is_pytest = False
    is_test_mode = os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    use_module_overrides = prefer_module_keys_in_tests and (is_pytest or is_test_mode)
    debug_info["test_flags"] = {"pytest": is_pytest, "test_mode": is_test_mode}

    try:
        from tldw_Server_API.app.api.v1.schemas import chat_request_schemas as _schemas_mod  # type: ignore

        dynamic_keys = _schemas_mod.get_api_keys() or {}
    except Exception as _err:
        # API key loading errors should be visible in production
        logger.warning(f"resolve_provider_api_key failed to load dynamic keys: {_err}")
        dynamic_keys = {}

    module_keys: Dict[str, Optional[str]] = {}
    if use_module_overrides:
        try:
            schema_keys = getattr(_schemas_mod, "API_KEYS", None)
            if isinstance(schema_keys, dict) and schema_keys:
                module_keys.update(schema_keys)
                debug_info["module_sources"].append("chat_request_schemas")
        except Exception as _schema_err:
            logger.warning(f"resolve_provider_api_key skipped schema module keys: {_schema_err}")
        try:
            from tldw_Server_API.app.api.v1.endpoints import chat as _chat_mod  # type: ignore

            endpoint_keys = getattr(_chat_mod, "API_KEYS", None)
            if isinstance(endpoint_keys, dict) and endpoint_keys:
                # Endpoint-level patches override schema-level for tests.
                module_keys.update(endpoint_keys)
                debug_info["module_sources"].append("chat_endpoint")
        except Exception as _chat_err:
            logger.warning(f"resolve_provider_api_key skipped endpoint module keys: {_chat_err}")

    try:
        from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import get_llm_provider_override

        override = get_llm_provider_override(provider_key)
        override_value = override.api_key if override else None
    except Exception:
        override_value = None

    debug_info["override_value_present"] = override_value is not None

    dynamic_value = dynamic_keys.get(provider_key)
    debug_info["dynamic_value_present"] = dynamic_value is not None

    def _normalize(value: Optional[str]) -> Optional[str]:
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


def merge_api_keys_for_provider(
    provider: str,
    module_keys: Optional[Dict[str, Optional[str]]],
    dynamic_keys: Dict[str, Optional[str]],
    requires_key_map: Dict[str, bool],
) -> Tuple[Optional[str], Optional[str]]:
    """Merge module-level and dynamic API keys, normalizing empties to None.

    Returns a tuple of (raw_value, normalized_value). The raw value is the
    original string (possibly empty) used to validate presence when a provider
    requires a key. The normalized value is None if empty-string-like.
    """
    def _normalize(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    raw_dynamic = dynamic_keys.get(provider)
    raw_module = module_keys.get(provider) if module_keys else None

    # Prefer dynamic/runtime keys (env/config) over module-level defaults.
    # If dynamic is explicitly empty/None, fall back to module-level value.
    if raw_dynamic is not None and str(raw_dynamic).strip() != "":
        raw_val = raw_dynamic
    else:
        raw_val = raw_module

    norm_val = _normalize(raw_val)

    # No raise here - the caller enforces requirements using requires_key_map
    return raw_val, norm_val


def build_call_params_from_request(
    request_data: Any,
    target_api_provider: str,
    provider_api_key: Optional[str],
    templated_llm_payload: List[Dict[str, Any]],
    final_system_message: Optional[str],
    app_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
        return max(1, len(request_json) // 4)
    except Exception:
        return 1


async def moderate_input_messages(
    request_data: Any,
    request: Any,
    moderation_service: Any,
    topic_monitoring_service: Optional[Any],
    metrics: Any,
    audit_service: Optional[Any],
    audit_context: Optional[Any],
    client_id: str,
    audit_event_type: Optional[Any] = None,
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
    except Exception:
        req_user_id = None

    eff_policy = moderation_service.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)

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
            except Exception:
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
                )
        except Exception as _e:
            logger.debug(f"Topic monitoring (input) skipped: {_e}")

        if not eff_policy.enabled or not eff_policy.input_enabled:
            return text

        resolved_action = None
        sample = None
        redacted = None
        category = None
        if hasattr(moderation_service, "evaluate_action"):
            try:
                eval_res = moderation_service.evaluate_action(text, eff_policy, "input")
                if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                    resolved_action, redacted, sample = eval_res[0], eval_res[1], eval_res[2]
                    category = eval_res[3] if len(eval_res) >= 4 else None
                else:
                    resolved_action, redacted, sample = eval_res  # type: ignore
            except Exception:
                resolved_action = None
        if not resolved_action:
            flagged, sample = moderation_service.check_text(text, eff_policy)
            if not flagged:
                return text
            resolved_action = eff_policy.input_action
            redacted = (
                moderation_service.redact_text(text, eff_policy)
                if resolved_action == "redact"
                else None
            )

        if resolved_action == "pass" or (resolved_action == "warn" and sample is None):
            return text

        try:
            metrics.track_moderation_input(str(req_user_id or client_id), resolved_action, category=(category or "default"))
        except Exception:
            pass
        try:
            if audit_service and audit_context:
                import asyncio as _asyncio
                _asyncio.create_task(
                    audit_service.log_event(
                        event_type=audit_event_type,
                        context=audit_context,
                        action="moderation.input",
                        result=("failure" if resolved_action == "block" else "success"),
                        metadata={"phase": "input", "action": resolved_action, "pattern": sample},
                    )
                )
        except Exception:
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
                                setattr(part, "text", await _moderate_text_in_place(current))
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Moderation input processing error: {e}")


async def build_context_and_messages(
    chat_db: Any,
    request_data: Any,
    loop: Any,
    metrics: Any,
    default_save_to_db: bool,
    final_conversation_id: Optional[str],
    save_message_fn: Any,
) -> Tuple[Dict[str, Any], Optional[int], str, bool, List[Dict[str, Any]], bool]:
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
        try:
            metrics.track_character_access(character_id=str(request_data.character_id or "default"), cache_hit=False)
        except Exception:
            pass

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
        try:
            metrics.track_conversation(conv_id, conversation_created)
        except Exception:
            pass
    if not conv_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to establish conversation context.")

    # History loading (configurable limit/order; filter missing roles, normalize assistant names)
    requested_history_limit = getattr(request_data, "history_message_limit", None)
    if requested_history_limit is None:
        history_limit = DEFAULT_HISTORY_MESSAGE_LIMIT
    else:
        try:
            history_limit = int(requested_history_limit)
        except Exception:
            history_limit = DEFAULT_HISTORY_MESSAGE_LIMIT
        history_limit = max(1, min(_MAX_HISTORY_MESSAGES, history_limit))

    requested_history_order = getattr(request_data, "history_message_order", None)
    if requested_history_order:
        history_order = str(requested_history_order).strip().lower()
        if history_order not in {"asc", "desc"}:
            history_order = DEFAULT_HISTORY_MESSAGE_ORDER
    else:
        history_order = DEFAULT_HISTORY_MESSAGE_ORDER
    db_order = "ASC" if history_order == "asc" else "DESC"

    historical_msgs: List[Dict[str, Any]] = []
    if conv_id and (not conversation_created) and history_limit > 0:
        raw_hist = await loop.run_in_executor(
            None,
            chat_db.get_messages_for_conversation,
            conv_id,
            history_limit,
            0,
            db_order,
        )
        if db_order == "DESC":
            raw_hist = list(reversed(raw_hist))
        for db_msg in raw_hist:
            sender_val = str(db_msg.get("sender", "") or "")
            role = map_sender_to_role(sender_val, character_card.get("name") if character_card else None)
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
                except Exception as e:
                    logger.warning(f"Error encoding DB image for history (msg_id {db_msg.get('id')}): {e}")
            if msg_parts:
                hist_entry = {"role": role}
                if role == "tool" and len(msg_parts) == 1 and msg_parts[0].get("type") == "text":
                    hist_entry["content"] = msg_parts[0].get("text", "")
                else:
                    hist_entry["content"] = msg_parts
                if role == "assistant" and character_card and character_card.get("name"):
                    name = sanitize_sender_name(character_card.get("name"))
                    if name:
                        hist_entry["name"] = name

                metadata = None
                try:
                    metadata = await loop.run_in_executor(None, chat_db.get_message_metadata, db_msg.get("id"))
                except Exception as meta_err:
                    logger.debug("Metadata lookup failed for message {}: {}", db_msg.get("id"), meta_err)

                tool_calls_meta = None
                function_call_meta = None
                content_placeholder_reason = None
                tool_call_id_meta = None
                if metadata:
                    tool_calls_meta = metadata.get("tool_calls")
                    extra_meta = metadata.get("extra") or {}
                    if isinstance(extra_meta, dict):
                        function_call_meta = extra_meta.get("function_call")
                        content_placeholder_reason = extra_meta.get("content_placeholder_reason")
                        tool_call_id_meta = extra_meta.get("tool_call_id")
                if tool_calls_meta is not None:
                    hist_entry["tool_calls"] = tool_calls_meta
                if function_call_meta and not hist_entry.get("tool_calls"):
                    hist_entry["function_call"] = function_call_meta
                if content_placeholder_reason in {"tool_calls", "function_call"}:
                    hist_entry["content"] = ""
                if role == "tool" and tool_call_id_meta:
                    hist_entry["tool_call_id"] = tool_call_id_meta
                historical_msgs.append(hist_entry)
        logger.info(f"Loaded {len(historical_msgs)} historical messages for conv_id '{conv_id}'.")

    # Process current turn messages (persist if needed)
    request_messages: List[Dict[str, Any]] = []
    for msg_model in request_data.messages:
        if not should_persist_message_role(msg_model.role):
            continue
        request_messages.append(msg_model.model_dump(exclude_none=True))

    # If the client included history with conversation_id, trim overlaps against DB history
    overlap_cut = 0
    if conv_id and historical_msgs and request_messages:
        has_non_user_role = any(
            msg.get("role") in {"assistant", "tool"} for msg in request_messages
        )
        if not has_non_user_role or len(request_messages) < 2:
            has_non_user_role = False
        def _normalize_content(value: Any) -> Any:
            if isinstance(value, str):
                return [{"type": "text", "text": value}]
            if isinstance(value, list):
                return value
            return value

        def _msg_sig(msg: Dict[str, Any]) -> str:
            payload = {
                "role": msg.get("role"),
                "content": _normalize_content(msg.get("content")),
                "tool_calls": msg.get("tool_calls"),
                "function_call": msg.get("function_call"),
                "tool_call_id": msg.get("tool_call_id"),
            }
            try:
                return _json.dumps(payload, sort_keys=True, default=str)
            except Exception:
                return str(payload)

        if has_non_user_role:
            hist_sigs = [_msg_sig(m) for m in historical_msgs]
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

    current_turn: List[Dict[str, Any]] = []
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

    llm_payload_messages = historical_msgs + current_turn

    return character_card, character_db_id, conv_id, conversation_created, llm_payload_messages, should_persist


def apply_prompt_templating(
    request_data: Any,
    character_card: Dict[str, Any],
    llm_payload_messages: List[Dict[str, Any]],
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Compute final system message and apply content templating to payload messages.

    Returns (final_system_message, templated_llm_payload)
    """
    active_template = load_template(getattr(request_data, "prompt_template_name", None) or DEFAULT_RAW_PASSTHROUGH_TEMPLATE.name)
    template_data: Dict[str, Any] = {}
    if character_card:
        template_data.update({k: v for k, v in character_card.items() if isinstance(v, (str, int, float))})
        template_data["char_name"] = character_card.get("name", "Character")
        template_data["character_system_prompt"] = character_card.get("system_prompt", "")

    sys_msg_from_req = next((m.content for m in request_data.messages if m.role == "system" and isinstance(m.content, str)), None)
    template_data["original_system_message_from_request"] = sys_msg_from_req or ""

    final_system_message: Optional[str] = None
    logger.debug(
        f"sys_msg_from_req: {sys_msg_from_req}, active_template: {active_template}, character: {character_card.get('name') if character_card else None}"
    )
    if active_template and active_template.system_message_template:
        final_system_message = apply_template_to_string(active_template.system_message_template, template_data)
        if not final_system_message and character_card and character_card.get("system_prompt"):
            final_system_message = character_card.get("system_prompt")
            system_prompt_preview = final_system_message[:50] if final_system_message else ""
            logger.debug(f"Template empty, using character system prompt: {repr(system_prompt_preview)}...")
    elif sys_msg_from_req:
        final_system_message = sys_msg_from_req
    elif character_card and character_card.get("system_prompt"):
        final_system_message = character_card.get("system_prompt")
        system_prompt_preview = final_system_message[:50] if final_system_message else ""
        logger.debug(f"Using character system prompt: {repr(system_prompt_preview)}...")

    logger.debug(f"Final system message: {repr(final_system_message)}")

    templated_llm_payload: List[Dict[str, Any]] = []
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


async def execute_streaming_call(
    *,
    current_loop: Any,
    cleaned_args: Dict[str, Any],
    selected_provider: str,
    provider: str,
    model: str,
    request_json: str,
    request: Any,
    metrics: Any,
    provider_manager: Any,
    templated_llm_payload: List[Dict[str, Any]],
    should_persist: bool,
    final_conversation_id: str,
    character_card_for_context: Optional[Dict[str, Any]],
    chat_db: Any,
    save_message_fn: Callable[..., Any],
    system_message_id: Optional[str] = None,
    audit_service: Optional[Any],
    audit_context: Optional[Any],
    client_id: str,
    queue_execution_enabled: bool,
    enable_provider_fallback: bool,
    llm_call_func: Callable[[], Any],
    refresh_provider_params: Callable[[str], Any],
    moderation_getter: Optional[Callable[[], Any]] = None,
    rg_commit_cb: Optional[Callable[[int], Any]] = None,
    rg_refund_cb: Optional[Callable[..., Any]] = None,
    on_success: Optional[Callable[[str], Awaitable[None]]] = None,
) -> StreamingResponse:
    """Execute a streaming LLM call with queue, failover, moderation, and persistence.

    Returns a StreamingResponse that yields SSE chunks and handles:
    - provider call invocation and fallback
    - output moderation (chunk-wise)
    - saving final assistant message to DB
    - usage logging and audit success
    """
    llm_start_time = time.time()
    raw_stream_iter: Optional[AsyncIterator[str] | Iterator[str]] = None
    queue_for_exec = None
    queue_enabled = False
    try:
        try:
            queue_for_exec = get_request_queue()
        except Exception:
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
            except Exception:
                stream_channel_maxsize = 100
            stream_channel: asyncio.Queue = asyncio.Queue(maxsize=stream_channel_maxsize)
            est_tokens_for_queue = max(1, len(request_json) // 4)

            def _queued_processor():
                local_start = time.time()
                try:
                    result = llm_call_func()
                    latency = time.time() - local_start
                    metrics.track_llm_call(selected_provider, model, latency, success=True)
                    if provider_manager:
                        provider_manager.record_success(selected_provider, latency)
                    if selected_provider != provider:
                        try:
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=selected_provider,
                                streaming=True,
                                queued=True,
                            )
                        except Exception:
                            pass
                    return result
                except Exception as proc_error:
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
                    raise

            try:
                await queue_for_exec.enqueue(
                    request_id=(get_request_id() or "unknown"),
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
            except (ValueError, TimeoutError) as admission_error:
                try:
                    metrics.track_rate_limit(str(client_id))
                except Exception:
                    pass
                detail = str(admission_error) or "Service busy. Please retry."
                status_code = (
                    status.HTTP_429_TOO_MANY_REQUESTS
                    if "rate limit" in detail.lower()
                    else status.HTTP_503_SERVICE_UNAVAILABLE
                )
                queue_exc = HTTPException(status_code=status_code, detail=detail)
                setattr(queue_exc, "_chat_queue_admission", True)
                raise queue_exc

            async def _channel_stream():
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
                        break
                    if item is None:
                        break
                    yield item

            raw_stream_iter = _channel_stream()
        else:
            # Execute provided LLM call function in a worker to avoid blocking the loop.
            # llm_call_func is a sync callable (partial of perform_chat_api_call or a mock).
            raw_stream_iter = await current_loop.run_in_executor(None, llm_call_func)
            latency = time.time() - llm_start_time
            metrics.track_llm_call(selected_provider, model, latency, success=True)
            try:
                if provider_manager:
                    provider_manager.record_success(selected_provider, latency)
            except Exception:
                pass
            if selected_provider != provider:
                try:
                    metrics.track_provider_fallback_success(
                        requested_provider=provider,
                        selected_provider=selected_provider,
                        streaming=True,
                        queued=False,
                    )
                except Exception:
                    pass
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
                yield f"data: {_json.dumps(payload)}\n\n"
            except Exception:
                # Fallback string serialization
                yield f"data: {{\"error\":{{\"message\":\"{msg}\",\"type\":\"{typ}\"}}}}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            _err_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
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
                    except Exception as refresh_error:
                        provider_manager.record_failure(fallback_provider, refresh_error)
                        raise
                    cleaned_args = refreshed_args
                    model = refreshed_model or model
                    fallback_start_time = time.time()
                    llm_call_func_fb = lambda: perform_chat_api_call(**cleaned_args)
                    try:
                        raw_stream_iter = await current_loop.run_in_executor(None, llm_call_func_fb)
                        fallback_latency = time.time() - fallback_start_time
                        provider_manager.record_success(fallback_provider, fallback_latency)
                        metrics.track_llm_call(fallback_provider, model, fallback_latency, success=True)
                        selected_provider = fallback_provider
                        llm_call_func = llm_call_func_fb
                        # Explicit telemetry for direct (non-queued) streaming fallback success
                        try:
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=fallback_provider,
                                streaming=True,
                                queued=False,
                            )
                        except Exception:
                            pass
                    except Exception as fallback_error:
                        provider_manager.record_failure(fallback_provider, fallback_error)
                        raise fallback_error
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
                yield f"data: {_json.dumps(payload)}\n\n"
            except Exception:
                yield f"data: {{\"error\":{{\"message\":\"{_err_message}\",\"type\":\"{_err_type}\"}}}}\n\n"
            yield "data: [DONE]\n\n"

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
        tool_calls: Optional[List[Dict[str, Any]]],
        function_call: Optional[Dict[str, Any]],
    ):
        saved_message_id: Optional[str] = None
        full_reply_to_save = full_reply
        post_stream_blocked = False
        try:
            _get_mod = moderation_getter or get_moderation_service
            moderation = _get_mod()
            req_user_id = None
            try:
                if request is not None and hasattr(request, "state"):
                    req_user_id = getattr(request.state, "user_id", None)
            except Exception:
                req_user_id = None
            eff_policy = moderation.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)
            if full_reply and eff_policy.enabled and eff_policy.output_enabled:
                action = None
                redacted = None
                sample = None
                category = None
                if hasattr(moderation, "evaluate_action"):
                    eval_res = moderation.evaluate_action(full_reply, eff_policy, "output")
                    if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                        action, redacted, sample = eval_res[0], eval_res[1], eval_res[2]
                        category = eval_res[3] if len(eval_res) >= 4 else None
                    else:
                        action, redacted, sample = eval_res  # type: ignore
                else:
                    flagged, sample = moderation.check_text(full_reply, eff_policy)
                    if flagged:
                        action = eff_policy.output_action
                        if action == "redact":
                            redacted = moderation.redact_text(full_reply, eff_policy)

                if action == "block":
                    if not stream_mod_state["block_logged"]:
                        try:
                            metrics.track_moderation_stream_block(
                                str(req_user_id or client_id),
                                category=(category or "default"),
                            )
                        except Exception:
                            pass
                        try:
                            if audit_service and audit_context:
                                import asyncio as _asyncio
                                _asyncio.create_task(
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
                                    )
                                )
                        except Exception:
                            pass
                        stream_mod_state["block_logged"] = True
                    post_stream_blocked = True
                    full_reply_to_save = None
                elif action == "redact":
                    if not stream_mod_state["redact_logged"]:
                        try:
                            metrics.track_moderation_output(
                                str(req_user_id or client_id),
                                "redact",
                                streaming=True,
                                category=(category or "default"),
                            )
                        except Exception:
                            pass
                        try:
                            if audit_service and audit_context:
                                import asyncio as _asyncio
                                _asyncio.create_task(
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
                                    )
                                )
                        except Exception:
                            pass
                        stream_mod_state["redact_logged"] = True
                    full_reply_to_save = moderation.redact_text(full_reply, eff_policy)
        except Exception:
            pass

        if should_persist and final_conversation_id and not post_stream_blocked and (
            full_reply_to_save or tool_calls or function_call
        ):
            asst_name = sanitize_sender_name(
                character_card_for_context.get("name") if character_card_for_context else None
            )
            message_payload: Dict[str, Any] = {
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
                pt_est = max(0, len(_json.dumps(templated_llm_payload)) // 4)
            except Exception:
                pt_est = 0
            ct_est = max(0, len(full_reply or "") // 4)
            user_id = None
            api_key_id = None
            try:
                if request is not None and hasattr(request, "state"):
                    user_id = getattr(request.state, "user_id", None)
                    api_key_id = getattr(request.state, "api_key_id", None)
            except Exception:
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
        except Exception:
            pass
        # Commit reserved tokens to Resource Governor, if provided
        try:
            if callable(rg_commit_cb):
                # rg_commit_cb may be async or sync; call accordingly
                res = rg_commit_cb(total_est)
                if hasattr(res, "__await__"):
                    await res  # type: ignore[misc]
        except Exception:
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
        except Exception:
            pass
        # BYOK usage tracking (best-effort)
        try:
            if callable(on_success):
                await on_success(selected_provider)
        except Exception:
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
            except Exception:
                req_user_id = None
            eff_policy = moderation.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)

            from tldw_Server_API.app.core.Chat.streaming_utils import StopStreamWithError

            pending_audit_tasks: list[asyncio.Task[Any]] = []

            def _track_audit_task(task: "asyncio.Task[Any]") -> None:
                pending_audit_tasks.append(task)
                def _cleanup(completed: "asyncio.Task[Any]") -> None:
                    try:
                        pending_audit_tasks.remove(completed)
                    except ValueError:
                        pass
                task.add_done_callback(_cleanup)

            def _out_transform(s: str) -> str:
                try:
                    mon = None
                    try:
                        mon = get_topic_monitoring_service()
                    except Exception:
                        mon = None
                    team_ids = None
                    org_ids = None
                    try:
                        if request is not None and hasattr(request, "state"):
                            team_ids = getattr(request.state, "team_ids", None)
                            org_ids = getattr(request.state, "org_ids", None)
                    except Exception:
                        pass
                    if mon is not None and s:
                        mon.schedule_evaluate_and_alert(
                            user_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            text=s,
                            source="chat.output",
                            scope_type="user",
                            scope_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            team_ids=team_ids,
                            org_ids=org_ids,
                        )
                except Exception as _e:
                    logger.debug(f"Topic monitoring (stream chunk) skipped: {_e}")
                if not eff_policy.enabled or not eff_policy.output_enabled:
                    return s
                resolved_action = None
                sample = None
                redacted_s = None
                out_category = None
                if hasattr(moderation, "evaluate_action"):
                    try:
                        eval_res = moderation.evaluate_action(s, eff_policy, "output")
                        if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                            resolved_action, redacted_s, sample = eval_res[0], eval_res[1], eval_res[2]
                            out_category = eval_res[3] if len(eval_res) >= 4 else None
                        else:
                            resolved_action, redacted_s, sample = eval_res  # type: ignore
                    except Exception:
                        resolved_action = None
                if not resolved_action:
                    flagged, sample = moderation.check_text(s, eff_policy)
                    if not flagged:
                        return s
                    resolved_action = eff_policy.output_action
                    redacted_s = moderation.redact_text(s, eff_policy) if resolved_action == "redact" else None
                if resolved_action == "block":
                    if not stream_mod_state["block_logged"]:
                        try:
                            metrics.track_moderation_stream_block(str(req_user_id or client_id), category=(out_category or "default"))
                        except Exception:
                            pass
                        try:
                            if audit_service and audit_context:
                                import asyncio as _asyncio
                                task = _asyncio.create_task(
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
                                    )
                                )
                                _track_audit_task(task)
                        except Exception:
                            pass
                        stream_mod_state["block_logged"] = True
                    raise StopStreamWithError(message="Output violates moderation policy", error_type="output_moderation_block")
                if resolved_action == "redact":
                    if not stream_mod_state["redact_logged"]:
                        try:
                            metrics.track_moderation_output(str(req_user_id or client_id), "redact", streaming=True, category=(out_category or "default"))
                        except Exception:
                            pass
                        try:
                            if audit_service and audit_context:
                                import asyncio as _asyncio
                                task = _asyncio.create_task(
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
                                    )
                                )
                                _track_audit_task(task)
                        except Exception:
                            pass
                        stream_mod_state["redact_logged"] = True
                    return moderation.redact_text(s, eff_policy)
                return s

            async def _finalize_stream(*, success: bool, cancelled: bool, error: bool) -> None:
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
                finalize_callback=_finalize_stream if callable(rg_refund_cb) else None,
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
    except Exception:
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
            except Exception as e:
                # As a safeguard; tracked_streaming_generator typically yields error frames itself
                await sse_stream.error("internal_error", f"{e}")

        async def _gen():
            prod = asyncio.create_task(_produce())
            try:
                async for line in sse_stream.iter_sse():
                    yield line
            except asyncio.CancelledError:
                # Cancel producer promptly on client disconnect
                if not prod.done():
                    try:
                        prod.cancel()
                    except Exception:
                        pass
                    try:
                        await prod
                    except (asyncio.CancelledError, Exception):
                        pass
                raise
            else:
                # Normal shutdown: ensure producer completes cleanly
                if not prod.done():
                    try:
                        await prod
                    except Exception:
                        pass

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
    cleaned_args: Dict[str, Any],
    selected_provider: str,
    provider: str,
    model: str,
    request_json: str,
    request: Any,
    metrics: Any,
    provider_manager: Any,
    templated_llm_payload: List[Dict[str, Any]],
    should_persist: bool,
    final_conversation_id: str,
    character_card_for_context: Optional[Dict[str, Any]],
    chat_db: Any,
    save_message_fn: Callable[..., Any],
    system_message_id: Optional[str] = None,
    audit_service: Optional[Any],
    audit_context: Optional[Any],
    client_id: str,
    queue_execution_enabled: bool,
    enable_provider_fallback: bool,
    llm_call_func: Callable[[], Any],
    refresh_provider_params: Callable[[str], Any],
    moderation_getter: Optional[Callable[[], Any]] = None,
    on_success: Optional[Callable[[str], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """Execute a non-streaming LLM call with queue, failover, moderation, and persistence.

    Returns the encoded payload (dict) ready to be wrapped by JSONResponse.
    """
    llm_start_time = time.time()
    llm_response = None
    metrics_recorded = False
    queue_enabled = False
    try:
        queue_for_exec = None
        try:
            queue_for_exec = get_request_queue()
        except Exception:
            queue_for_exec = None
        queue_enabled = (
            queue_execution_enabled
            and queue_for_exec is not None
            and queue_is_active(queue_for_exec)
        )
        if queue_enabled:
            est_tokens_for_queue = max(1, len(request_json) // 4)
            def _queued_processor():
                local_start = time.time()
                try:
                    result = llm_call_func()
                    latency = time.time() - local_start
                    metrics.track_llm_call(selected_provider, model, latency, success=True)
                    if provider_manager:
                        provider_manager.record_success(selected_provider, latency)
                    if selected_provider != provider:
                        try:
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=selected_provider,
                                streaming=False,
                                queued=True,
                            )
                        except Exception:
                            pass
                    return result
                except Exception as proc_error:
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
                try:
                    metrics.track_rate_limit(str(client_id))
                except Exception:
                    pass
                detail = str(admission_error) or "Service busy. Please retry."
                status_code = (
                    status.HTTP_429_TOO_MANY_REQUESTS
                    if "rate limit" in detail.lower()
                    else status.HTTP_503_SERVICE_UNAVAILABLE
                )
                queue_exc = HTTPException(status_code=status_code, detail=detail)
                setattr(queue_exc, "_chat_queue_admission", True)
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
                try:
                    metrics.track_provider_fallback_success(
                        requested_provider=provider,
                        selected_provider=selected_provider,
                        streaming=False,
                        queued=False,
                    )
                except Exception:
                    pass
    except HTTPException as he:
        if getattr(he, "_chat_queue_admission", False):
            raise
        raise
    except Exception as e:
        llm_latency = time.time() - llm_start_time
        metrics.track_llm_call(
            selected_provider,
            model,
            llm_latency,
            success=False,
            error_type=type(e).__name__,
        )
        if provider_manager:
            provider_manager.record_failure(selected_provider, e)
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
                    except Exception as refresh_error:
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
                        try:
                            metrics.track_provider_fallback_success(
                                requested_provider=provider,
                                selected_provider=fallback_provider,
                                streaming=False,
                                queued=False,
                            )
                        except Exception:
                            pass
                    except Exception as fallback_error:
                        provider_manager.record_failure(fallback_provider, fallback_error)
                        raise fallback_error
                else:
                    raise
            else:
                raise
        else:
            raise

    content_to_save: Optional[str] = None
    tool_calls_to_save: Optional[Any] = None
    function_call_to_save: Optional[Any] = None
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
                except Exception:
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
            except Exception:
                pass
        else:
            # Estimate usage if not provided
            try:
                pt_est = 0
                try:
                    pt_est = max(0, len(_json.dumps(templated_llm_payload)) // 4)
                except Exception:
                    pt_est = 0
                ct_est = max(0, len((content_to_save or "")) // 4)
                user_id = None
                api_key_id = None
                try:
                    if request is not None and hasattr(request, "state"):
                        user_id = getattr(request.state, "user_id", None)
                        api_key_id = getattr(request.state, "api_key_id", None)
                except Exception:
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
            except Exception:
                pass
    elif isinstance(llm_response, str):
        content_to_save = llm_response
    elif llm_response is None:
        raise ChatProviderError(provider=provider, message="Provider unavailable or returned no response", status_code=502)

    # Output moderation (non-streaming)
    try:
        if content_to_save:
            _get_mod = moderation_getter or get_moderation_service
            moderation = _get_mod()
            req_user_id = None
            try:
                if request is not None and hasattr(request, "state"):
                    req_user_id = getattr(request.state, "user_id", None)
            except Exception:
                req_user_id = None
            eff_policy = moderation.get_effective_policy(str(req_user_id) if req_user_id is not None else client_id)
            if eff_policy.enabled and eff_policy.output_enabled:
                resolved_action = None
                sample = None
                redacted_val = None
                out_category2 = None
                if hasattr(moderation, "evaluate_action"):
                    try:
                        eval_res = moderation.evaluate_action(content_to_save, eff_policy, "output")
                        if isinstance(eval_res, tuple) and len(eval_res) >= 3:
                            resolved_action, redacted_val, sample = eval_res[0], eval_res[1], eval_res[2]
                            out_category2 = eval_res[3] if len(eval_res) >= 4 else None
                        else:
                            resolved_action, redacted_val, sample = eval_res  # type: ignore
                    except Exception:
                        resolved_action = None
                if not resolved_action:
                    flagged, sample = moderation.check_text(content_to_save, eff_policy)
                    if flagged:
                        resolved_action = eff_policy.output_action
                        redacted_val = moderation.redact_text(content_to_save, eff_policy) if resolved_action == "redact" else None
                # Topic monitoring (final output)
                try:
                    mon3 = None
                    try:
                        mon3 = get_topic_monitoring_service()
                    except Exception:
                        mon3 = None
                    team_ids = None
                    org_ids = None
                    try:
                        if request is not None and hasattr(request, "state"):
                            team_ids = getattr(request.state, "team_ids", None)
                            org_ids = getattr(request.state, "org_ids", None)
                    except Exception:
                        pass
                    if mon3 is not None and content_to_save:
                        mon3.schedule_evaluate_and_alert(
                            user_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            text=content_to_save,
                            source="chat.output",
                            scope_type="user",
                            scope_id=str(req_user_id or client_id) if (req_user_id or client_id) else None,
                            team_ids=team_ids,
                            org_ids=org_ids,
                        )
                except Exception as _ex:
                    logger.debug(f"Topic monitoring (non-stream final) skipped: {_ex}")

                if resolved_action == "block":
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Output violates moderation policy")
                if resolved_action == "redact":
                    try:
                        if sample is not None:
                            metrics.track_moderation_output(str(req_user_id or client_id), "redact", streaming=False, category=(out_category2 or "default"))
                    except Exception:
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
                    except Exception:
                        pass
                    content_to_save = (
                        redacted_val
                        if isinstance(redacted_val, str)
                        else moderation.redact_text(content_to_save, eff_policy)
                    )
                    # Update llm_response dict if applicable
                    try:
                        if isinstance(llm_response, dict):
                            if llm_response.get("choices") and isinstance(llm_response["choices"], list) and llm_response["choices"]:
                                msg = llm_response["choices"][0].get("message") or {}
                                if isinstance(msg, dict):
                                    msg["content"] = content_to_save
                    except Exception:
                        pass
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Moderation output processing error: {e}")

    assistant_message_id: Optional[str] = None
    should_save_response = (
        should_persist
        and final_conversation_id
        and (content_to_save or tool_calls_to_save or function_call_to_save)
    )
    if should_save_response:
        asst_name = sanitize_sender_name(
            character_card_for_context.get("name") if character_card_for_context else None
        )
        message_payload: Dict[str, Any] = {"role": "assistant", "name": asst_name}
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

    # Encode payload (large responses via CPU-bound handler)
    if llm_response and isinstance(llm_response, dict) and len(str(llm_response)) > 10000:
        encoded_json = await process_large_json_async(llm_response)
        encoded_payload = _json.loads(encoded_json)
    else:
        encoded_payload = await current_loop.run_in_executor(None, jsonable_encoder, llm_response)

    if isinstance(encoded_payload, dict):
        encoded_payload["tldw_conversation_id"] = final_conversation_id
        if assistant_message_id:
            encoded_payload["tldw_message_id"] = assistant_message_id
        if system_message_id:
            encoded_payload["tldw_system_message_id"] = system_message_id

    # Audit success
    if audit_service and audit_context:
        try:
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
        except Exception:
            pass

    # BYOK usage tracking (best-effort)
    try:
        if callable(on_success):
            await on_success(selected_provider)
    except Exception:
        pass

    return encoded_payload
