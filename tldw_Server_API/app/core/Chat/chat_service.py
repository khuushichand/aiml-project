"""
chat_service.py
Lightweight helpers to keep the chat endpoint readable and testable without changing behavior.

These functions encapsulate small, deterministic pieces of logic used by
the /api/v1/chat/completions endpoint so the endpoint can orchestrate at a
higher level. The goal is to reduce duplication and cognitive load while
keeping the wire behavior identical.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List, Callable, AsyncIterator, Iterator
from fastapi import HTTPException, status
from loguru import logger
import base64
import uuid as _uuid
import asyncio
import time
import json as _json
import os

# Reuse existing helpers from chat_helpers and prompt templating
from tldw_Server_API.app.core.Chat.chat_helpers import (
    get_or_create_character_context,
    get_or_create_conversation,
)
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import replace_placeholders
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

    Accepts model strings like "anthropic/claude-3-opus" and an optional
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
    provider = (api_provider or default_provider).lower()
    if "/" in model_str:
        parts = model_str.split("/", 1)
        if len(parts) == 2:
            model_provider, actual_model = parts
            if not api_provider:
                provider = model_provider.lower()
            # Update the request in place so downstream code sees the stripped model
            setattr(request_data, "model", actual_model)
    return provider


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
                mon.evaluate_and_alert(
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
            redacted = moderation_service.redact_text(text, eff_policy) if resolved_action == "redact" else None

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
        if resolved_action == "redact" and redacted is not None:
            return redacted
        return text

    # Apply moderation across request messages
    try:
        if eff_policy.enabled and eff_policy.input_enabled and request_data and request_data.messages:
            for m in request_data.messages:
                if getattr(m, "role", None) != "user":
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

    # History loading (configurable limit/order)
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
            role = "user" if db_msg.get("sender", "").lower() == "user" else "assistant"
            char_name_hist = character_card.get("name", "Char") if character_card else "Char"
            text_content = db_msg.get("content", "")
            if text_content:
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
                hist_entry = {"role": role, "content": msg_parts}
                if role == "assistant" and character_card and character_card.get("name"):
                    name = character_card.get("name", "").replace(" ", "_").replace("<", "").replace(">", "").replace("|", "").replace("\\", "").replace("/", "")
                    if name:
                        hist_entry["name"] = name

                metadata = None
                try:
                    metadata = await loop.run_in_executor(None, chat_db.get_message_metadata, db_msg.get("id"))
                except Exception as meta_err:
                    logger.debug("Metadata lookup failed for message %s: %s", db_msg.get("id"), meta_err)

                tool_calls_meta = None
                function_call_meta = None
                content_placeholder_reason = None
                if metadata:
                    tool_calls_meta = metadata.get("tool_calls")
                    extra_meta = metadata.get("extra") or {}
                    if isinstance(extra_meta, dict):
                        function_call_meta = extra_meta.get("function_call")
                        content_placeholder_reason = extra_meta.get("content_placeholder_reason")
                if tool_calls_meta is not None:
                    hist_entry["tool_calls"] = tool_calls_meta
                if function_call_meta and not hist_entry.get("tool_calls"):
                    hist_entry["function_call"] = function_call_meta
                if content_placeholder_reason in {"tool_calls", "function_call"}:
                    hist_entry["content"] = ""
                historical_msgs.append(hist_entry)
        logger.info(f"Loaded {len(historical_msgs)} historical messages for conv_id '{conv_id}'.")

    # Process current turn messages (persist if needed)
    current_turn: List[Dict[str, Any]] = []
    for msg_model in request_data.messages:
        if msg_model.role == "system":
            continue
        msg_dict = msg_model.model_dump(exclude_none=True)
        msg_for_db = msg_dict.copy()
        if msg_model.role == "assistant" and character_card:
            msg_for_db["name"] = character_card.get("name", "Assistant")
        if should_persist:
            await save_message_fn(chat_db, conv_id, msg_for_db, use_transaction=True)
        msg_for_llm = msg_dict.copy()
        if msg_model.role == "assistant" and character_card and character_card.get("name"):
            name = character_card.get("name", "").replace(" ", "_").replace("<", "").replace(">", "").replace("|", "").replace("\\", "").replace("/", "")
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
    audit_service: Optional[Any],
    audit_context: Optional[Any],
    client_id: str,
    queue_execution_enabled: bool,
    enable_provider_fallback: bool,
    llm_call_func: Callable[[], Any],
    refresh_provider_params: Callable[[str], Tuple[Dict[str, Any], Optional[str]]],
    moderation_getter: Optional[Callable[[], Any]] = None,
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
            stream_channel: asyncio.Queue = asyncio.Queue(maxsize=100)
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
                    item = await stream_channel.get()
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
        raise
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
                        refreshed_args, refreshed_model = refresh_provider_params(fallback_provider)
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
                    raise
            else:
                raise
        else:
            raise

    if not (hasattr(raw_stream_iter, "__aiter__") or hasattr(raw_stream_iter, "__iter__")):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Provider did not return a valid stream.")

    async def save_callback(
        full_reply: str,
        tool_calls: Optional[List[Dict[str, Any]]],
        function_call: Optional[Dict[str, Any]],
    ):
        if should_persist and final_conversation_id and (
            full_reply or tool_calls or function_call
        ):
            asst_name = character_card_for_context.get("name", "Assistant") if character_card_for_context else "Assistant"
            asst_name = (
                asst_name.replace(" ", "_")
                .replace("<", "")
                .replace(">", "")
                .replace("|", "")
                .replace("\\", "")
                .replace("/", "")
            )
            message_payload: Dict[str, Any] = {
                "role": "assistant",
                "name": asst_name,
            }
            if full_reply is not None:
                message_payload["content"] = full_reply
            if tool_calls:
                message_payload["tool_calls"] = tool_calls
            if function_call:
                message_payload["function_call"] = function_call
            await save_message_fn(
                chat_db,
                final_conversation_id,
                message_payload,
                use_transaction=True,
            )
        # Usage logging (estimated) after stream completes
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
                total_tokens=int(pt_est + ct_est),
                request_id=(request.headers.get("X-Request-ID") if request else None) or (get_request_id() or None),
                estimated=True,
            )
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

            stream_block_logged = False
            stream_redact_logged = False
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
                nonlocal stream_block_logged, stream_redact_logged
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
                        mon.evaluate_and_alert(
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
                    if not stream_block_logged:
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
                        stream_block_logged = True
                    raise StopStreamWithError(message="Output violates moderation policy", error_type="output_moderation_block")
                if resolved_action == "redact":
                    if not stream_redact_logged:
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
                        stream_redact_logged = True
                    return redacted_s or moderation.redact_text(s, eff_policy)
                return s

            generator = create_streaming_response_with_timeout(
                stream=raw_stream_iter,  # type: ignore[arg-type]
                conversation_id=final_conversation_id,
                model_name=model,
                save_callback=save_callback,
                idle_timeout=300,
                heartbeat_interval=30,
                text_transform=_out_transform if (eff_policy.enabled and eff_policy.output_enabled) else None,
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
    audit_service: Optional[Any],
    audit_context: Optional[Any],
    client_id: str,
    queue_execution_enabled: bool,
    enable_provider_fallback: bool,
    llm_call_func: Callable[[], Any],
    refresh_provider_params: Callable[[str], Tuple[Dict[str, Any], Optional[str]]],
    moderation_getter: Optional[Callable[[], Any]] = None,
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
                        refreshed_args, refreshed_model = refresh_provider_params(fallback_provider)
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
                        mon3.evaluate_and_alert(
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
                    content_to_save = redacted_val or moderation.redact_text(content_to_save, eff_policy)
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

    should_save_response = (
        should_persist
        and final_conversation_id
        and (content_to_save or tool_calls_to_save or function_call_to_save)
    )
    if should_save_response:
        asst_name = character_card_for_context.get("name", "Assistant") if character_card_for_context else "Assistant"
        asst_name = (
            asst_name.replace(" ", "_")
            .replace("<", "")
            .replace(">", "")
            .replace("|", "")
            .replace("\\", "")
            .replace("/", "")
        )
        message_payload: Dict[str, Any] = {"role": "assistant", "name": asst_name}
        if content_to_save is not None:
            message_payload["content"] = content_to_save
        if tool_calls_to_save is not None:
            message_payload["tool_calls"] = tool_calls_to_save
        if function_call_to_save is not None:
            message_payload["function_call"] = function_call_to_save
        await save_message_fn(
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

    return encoded_payload
