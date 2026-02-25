"""ACP integration adapter.

This module includes adapters for Agent Client Protocol operations:
- acp_stage: Execute a pipeline stage via ACP session prompt
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.runner_client import (
    ACPGovernanceDeniedError,
    get_runner_client,
)
from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string
from tldw_Server_API.app.core.exceptions import AdapterError
from tldw_Server_API.app.core.Workflows.adapters._common import extract_openai_content, resolve_context_user_id
from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.integration._config import ACPStageConfig

_ACP_STAGE_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    KeyError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


def _render_optional_template(value: Any, context: dict[str, Any]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    rendered = apply_template_to_string(value, context) or value
    text = str(rendered).strip()
    return text or None


def _resolve_str_field(config: dict[str, Any], context: dict[str, Any], key: str) -> str | None:
    if key in config:
        return _render_optional_template(config.get(key), context)
    return _render_optional_template(context.get(key), context)


def _normalize_error_payload(
    *,
    status: str,
    error_type: str,
    message: str,
    stage: str,
    session_id: str | None,
    workspace_id: str | None,
    workspace_group_id: str | None,
    governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "error_type": error_type,
        "error": message,
        "stage": stage,
        "session_id": session_id,
        "workspace_id": workspace_id,
        "workspace_group_id": workspace_group_id,
        "response": {},
        "usage": {},
        "governance": governance or {},
    }
    return payload


def _maybe_raise_if_configured(result: dict[str, Any], fail_on_error: bool) -> dict[str, Any]:
    if not fail_on_error:
        return result
    status = str(result.get("status") or "").strip().lower()
    if status in {"error", "blocked"}:
        err = str(result.get("error_type") or "acp_stage_error")
        raise AdapterError(err)
    return result


def _render_prompt(config: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    prompt = config.get("prompt")
    if isinstance(prompt, list):
        rendered: list[dict[str, Any]] = []
        for msg in prompt:
            if not isinstance(msg, dict):
                continue
            out_msg: dict[str, Any] = {}
            for key, value in msg.items():
                if isinstance(value, str):
                    out_msg[key] = apply_template_to_string(value, context) or value
                else:
                    out_msg[key] = value
            if out_msg:
                rendered.append(out_msg)
        if rendered:
            return rendered
    if isinstance(prompt, str):
        rendered_prompt = apply_template_to_string(prompt, context) or prompt
        return [{"role": "user", "content": rendered_prompt}]

    prompt_template = str(config.get("prompt_template") or "").strip()
    if prompt_template:
        rendered_template = apply_template_to_string(prompt_template, context) or prompt_template
        return [{"role": "user", "content": rendered_template}]

    last = context.get("last") or {}
    fallback = ""
    if isinstance(last, dict):
        fallback = str(last.get("text") or last.get("content") or "").strip()
    if not fallback:
        fallback = str((context.get("inputs") or {}).get("task") or "").strip()
    if fallback:
        return [{"role": "user", "content": fallback}]
    return []


async def _create_session(
    runner: Any,
    *,
    cwd: str,
    agent_type: str | None,
    user_id: int,
    persona_id: str | None,
    workspace_id: str | None,
    workspace_group_id: str | None,
    scope_snapshot_id: str | None,
) -> str:
    params: dict[str, Any] = {
        "cwd": cwd,
        "agent_type": agent_type,
        "user_id": user_id,
        "persona_id": persona_id,
        "workspace_id": workspace_id,
        "workspace_group_id": workspace_group_id,
        "scope_snapshot_id": scope_snapshot_id,
    }
    params = {k: v for k, v in params.items() if v is not None}
    try:
        return await runner.create_session(**params)
    except TypeError:
        # Non-sandbox ACP runner currently only accepts cwd/agent_type/user_id.
        narrowed = {
            "cwd": cwd,
            "agent_type": agent_type,
            "user_id": user_id,
        }
        narrowed = {k: v for k, v in narrowed.items() if v is not None}
        return await runner.create_session(**narrowed)


@registry.register(
    "acp_stage",
    category="integration",
    description="Execute an ACP-backed stage via session prompt",
    parallelizable=False,
    tags=["integration", "acp", "pipeline"],
    config_model=ACPStageConfig,
)
async def run_acp_stage_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute a workflow stage by prompting an ACP session."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    stage = str(config.get("stage") or "").strip()
    if not stage:
        result = _normalize_error_payload(
            status="error",
            error_type="acp_prompt_error",
            message="missing_stage",
            stage="",
            session_id=None,
            workspace_id=None,
            workspace_group_id=None,
        )
        return _maybe_raise_if_configured(result, bool(config.get("fail_on_error")))

    workspace_id = _resolve_str_field(config, context, "workspace_id")
    workspace_group_id = _resolve_str_field(config, context, "workspace_group_id")
    persona_id = _resolve_str_field(config, context, "persona_id")
    scope_snapshot_id = _resolve_str_field(config, context, "scope_snapshot_id")

    review_counter_key = str(config.get("review_counter_key") or "").strip()
    max_review_loops = config.get("max_review_loops")
    if review_counter_key and max_review_loops is not None:
        try:
            current = int(context.get(review_counter_key) or 0)
            maximum = int(max_review_loops)
            if current >= maximum:
                blocked = _normalize_error_payload(
                    status="blocked",
                    error_type="review_loop_exceeded",
                    message="review_loop_exceeded",
                    stage=stage,
                    session_id=None,
                    workspace_id=workspace_id,
                    workspace_group_id=workspace_group_id,
                )
                return _maybe_raise_if_configured(blocked, bool(config.get("fail_on_error")))
            context[review_counter_key] = current + 1
        except _ACP_STAGE_NONCRITICAL_EXCEPTIONS:
            logger.debug("ACP stage adapter: failed to evaluate review loop guard")

    user_id = resolve_context_user_id(context)
    if not user_id:
        result = _normalize_error_payload(
            status="error",
            error_type="acp_session_error",
            message="missing_user_id",
            stage=stage,
            session_id=None,
            workspace_id=workspace_id,
            workspace_group_id=workspace_group_id,
        )
        return _maybe_raise_if_configured(result, bool(config.get("fail_on_error")))

    session_context_key = str(config.get("session_context_key") or "acp_session_id").strip() or "acp_session_id"
    session_id = _render_optional_template(config.get("session_id"), context) or _render_optional_template(
        context.get(session_context_key), context
    )
    create_session = bool(config.get("create_session", True))
    runner = await get_runner_client()

    if not session_id:
        if not create_session:
            result = _normalize_error_payload(
                status="error",
                error_type="acp_session_error",
                message="missing_session_id",
                stage=stage,
                session_id=None,
                workspace_id=workspace_id,
                workspace_group_id=workspace_group_id,
            )
            return _maybe_raise_if_configured(result, bool(config.get("fail_on_error")))

        cwd = _resolve_str_field(config, context, "cwd") or "/workspace"
        agent_type = _resolve_str_field(config, context, "agent_type")
        try:
            session_id = await _create_session(
                runner,
                cwd=cwd,
                agent_type=agent_type,
                user_id=int(user_id),
                persona_id=persona_id,
                workspace_id=workspace_id,
                workspace_group_id=workspace_group_id,
                scope_snapshot_id=scope_snapshot_id,
            )
        except _ACP_STAGE_NONCRITICAL_EXCEPTIONS as exc:
            result = _normalize_error_payload(
                status="error",
                error_type="acp_session_error",
                message=str(exc) or "acp_session_error",
                stage=stage,
                session_id=None,
                workspace_id=workspace_id,
                workspace_group_id=workspace_group_id,
            )
            return _maybe_raise_if_configured(result, bool(config.get("fail_on_error")))
        context[session_context_key] = session_id

    prompt_payload = _render_prompt(config, context)
    if not prompt_payload:
        result = _normalize_error_payload(
            status="error",
            error_type="acp_prompt_error",
            message="missing_prompt",
            stage=stage,
            session_id=session_id,
            workspace_id=workspace_id,
            workspace_group_id=workspace_group_id,
        )
        return _maybe_raise_if_configured(result, bool(config.get("fail_on_error")))

    timeout_seconds = int(config.get("timeout_seconds") or 300)
    try:
        raw_response = await asyncio.wait_for(
            runner.prompt(session_id, prompt_payload),
            timeout=float(timeout_seconds),
        )
    except ACPGovernanceDeniedError as exc:
        blocked = _normalize_error_payload(
            status="blocked",
            error_type="acp_governance_blocked",
            message=str(exc) or "governance_blocked",
            stage=stage,
            session_id=session_id,
            workspace_id=workspace_id,
            workspace_group_id=workspace_group_id,
            governance=getattr(exc, "governance", None),
        )
        return _maybe_raise_if_configured(blocked, bool(config.get("fail_on_error")))
    except (asyncio.TimeoutError, TimeoutError):
        timed_out = _normalize_error_payload(
            status="error",
            error_type="acp_timeout",
            message="acp_prompt_timeout",
            stage=stage,
            session_id=session_id,
            workspace_id=workspace_id,
            workspace_group_id=workspace_group_id,
        )
        return _maybe_raise_if_configured(timed_out, bool(config.get("fail_on_error")))
    except _ACP_STAGE_NONCRITICAL_EXCEPTIONS as exc:
        failed = _normalize_error_payload(
            status="error",
            error_type="acp_prompt_error",
            message=str(exc) or "acp_prompt_error",
            stage=stage,
            session_id=session_id,
            workspace_id=workspace_id,
            workspace_group_id=workspace_group_id,
        )
        return _maybe_raise_if_configured(failed, bool(config.get("fail_on_error")))

    response = raw_response if isinstance(raw_response, dict) else {"raw_result": raw_response}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    governance = response.get("governance") if isinstance(response.get("governance"), dict) else {}

    result: dict[str, Any] = {
        "status": "ok",
        "stage": stage,
        "session_id": session_id,
        "workspace_id": workspace_id,
        "workspace_group_id": workspace_group_id,
        "response": response,
        "usage": usage,
        "governance": governance,
    }
    extracted = extract_openai_content(response)
    if extracted:
        result["text"] = extracted
    return result
