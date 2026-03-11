from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

_SENSITIVE_ARGUMENT_KEYS = {
    "api_key",
    "authorization",
    "content",
    "content_b64",
    "cookie",
    "cookies",
    "env",
    "headers",
    "secret",
    "token",
}
_SUMMARY_MAX_ITEMS = 8
_SUMMARY_MAX_STRING = 160


def _context_metadata(context: Any | None) -> dict[str, Any]:
    """Return a shallow metadata mapping from an MCP request context."""
    metadata = getattr(context, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _context_key_for_request(context: Any | None) -> str:
    """Build the approval context key from the active request context."""
    metadata = _context_metadata(context)
    user_id = str(getattr(context, "user_id", "") or "").strip()
    group_id = str(metadata.get("group_id") or "").strip()
    persona_id = str(metadata.get("persona_id") or "").strip()
    return f"user:{user_id}|group:{group_id}|persona:{persona_id}"


def _conversation_id_for_request(context: Any | None) -> str | None:
    """Extract the active conversation/session identifier from the request context."""
    metadata = _context_metadata(context)
    for key in ("conversation_id", "session_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    session_id = str(getattr(context, "session_id", "") or "").strip()
    return session_id or None


def _truncate_summary_text(value: Any) -> str:
    """Return a bounded string for approval summaries."""
    text = str(value or "")
    if len(text) <= _SUMMARY_MAX_STRING:
        return text
    return f"{text[: _SUMMARY_MAX_STRING - 3]}..."


def _normalized_command(value: Any) -> str | None:
    """Normalize string or list command inputs for stable approval scoping."""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (list, tuple)):
        parts = [str(part).strip() for part in value if str(part).strip()]
        return " ".join(parts) if parts else None
    return None


def _scope_fingerprint_payload(
    tool_args: Any,
    *,
    scope_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select a small canonical subset of tool args for scope hashing."""
    if not isinstance(tool_args, dict):
        payload = {}
    else:
        payload = {}
        for key in ("command", "cmd", "args", "arguments"):
            command = _normalized_command(tool_args.get(key))
            if command:
                payload["command"] = command
                break
        for key in ("path", "file_path", "url"):
            value = str(tool_args.get(key) or "").strip()
            if value:
                payload[key] = value
        for key in ("paths", "file_paths"):
            raw = tool_args.get(key)
            if isinstance(raw, (list, tuple)):
                values = [str(entry).strip() for entry in raw if str(entry).strip()]
                if values:
                    payload[key] = values[:_SUMMARY_MAX_ITEMS]
        files = tool_args.get("files")
        if isinstance(files, list):
            file_paths = [
                str(item.get("path") or "").strip()
                for item in files
                if isinstance(item, dict) and str(item.get("path") or "").strip()
            ]
            if file_paths:
                payload["files"] = file_paths[:_SUMMARY_MAX_ITEMS]
    if isinstance(scope_payload, dict):
        scope_context: dict[str, Any] = {}
        for key in (
            "path_scope_mode",
            "workspace_id",
            "workspace_root",
            "scope_root",
            "selected_workspace_trust_source",
            "workspace_source_mode",
            "server_id",
            "server_name",
            "reason",
        ):
            value = str(scope_payload.get(key) or "").strip()
            if value:
                scope_context[key] = value
        assignment_id = scope_payload.get("selected_assignment_id")
        if assignment_id not in (None, ""):
            scope_context["selected_assignment_id"] = str(assignment_id).strip()
        blocked_reason = str(scope_payload.get("blocked_reason") or "").strip()
        if blocked_reason:
            scope_context["blocked_reason"] = blocked_reason
        normalized_paths = scope_payload.get("normalized_paths")
        if isinstance(normalized_paths, list):
            values = [str(entry).strip() for entry in normalized_paths if str(entry).strip()]
            if values:
                scope_context["normalized_paths"] = values[:_SUMMARY_MAX_ITEMS]
        path_allowlist_prefixes = scope_payload.get("path_allowlist_prefixes")
        if isinstance(path_allowlist_prefixes, list):
            values = [str(entry).strip() for entry in path_allowlist_prefixes if str(entry).strip()]
            if values:
                scope_context["path_allowlist_prefixes"] = sorted(values)[:_SUMMARY_MAX_ITEMS]
        allowed_workspace_ids = scope_payload.get("allowed_workspace_ids")
        if isinstance(allowed_workspace_ids, list):
            values = [str(entry).strip() for entry in allowed_workspace_ids if str(entry).strip()]
            if values:
                scope_context["allowed_workspace_ids"] = sorted(values)[:_SUMMARY_MAX_ITEMS]
        for key in ("requested_slots", "bound_slots", "missing_bound_slots", "missing_secret_slots"):
            raw = scope_payload.get(key)
            if isinstance(raw, list):
                values = [str(entry).strip() for entry in raw if str(entry).strip()]
                if values:
                    scope_context[key] = sorted(values)[:_SUMMARY_MAX_ITEMS]
        if scope_context:
            payload["scope_context"] = scope_context
    return payload


def _scope_key_for_tool_call(
    tool_name: str,
    tool_args: Any,
    *,
    scope_payload: dict[str, Any] | None = None,
) -> str:
    """Build a stable scope key for a tool invocation."""
    fingerprint_payload = _scope_fingerprint_payload(tool_args, scope_payload=scope_payload)
    if fingerprint_payload:
        canonical = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        return f"tool:{tool_name}|args:{digest}"
    return f"tool:{tool_name}"


def _redacted_env_summary(value: Any) -> dict[str, Any]:
    """Return env metadata without exposing values."""
    if not isinstance(value, dict):
        return {"redacted": True}
    keys = [
        str(key).strip()
        for key in value.keys()
        if str(key).strip()
    ][: _SUMMARY_MAX_ITEMS]
    return {"redacted": True, "keys": keys}


def _summarize_files(value: Any) -> list[dict[str, Any]]:
    """Summarize file inputs by path only."""
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value[:_SUMMARY_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        out.append({"path": path})
    return out


def _arguments_summary(tool_args: Any) -> dict[str, Any]:
    """Build a redacted, bounded preview of tool arguments for approval prompts."""
    if not isinstance(tool_args, dict):
        return {}
    summary: dict[str, Any] = {}
    for key, value in list(tool_args.items())[:_SUMMARY_MAX_ITEMS]:
        clean_key = str(key or "").strip()
        if not clean_key:
            continue
        lowered = clean_key.lower()
        if lowered in _SENSITIVE_ARGUMENT_KEYS or lowered.endswith("_b64"):
            if lowered == "env":
                summary[clean_key] = _redacted_env_summary(value)
            continue
        if lowered == "files":
            file_summary = _summarize_files(value)
            if file_summary:
                summary[clean_key] = file_summary
            continue
        if lowered in {"command", "cmd", "args", "arguments"}:
            command = _normalized_command(value)
            if command is not None:
                summary[clean_key] = value if isinstance(value, list) else _truncate_summary_text(command)
            continue
        if isinstance(value, str):
            summary[clean_key] = _truncate_summary_text(value)
            continue
        if isinstance(value, (int, float, bool)) or value is None:
            summary[clean_key] = value
            continue
        if isinstance(value, (list, tuple)):
            items = [_truncate_summary_text(item) for item in list(value)[:_SUMMARY_MAX_ITEMS]]
            summary[clean_key] = items
            continue
        if isinstance(value, dict):
            summary[clean_key] = {
                "keys": [
                    str(item_key).strip()
                    for item_key in list(value.keys())[:_SUMMARY_MAX_ITEMS]
                    if str(item_key).strip()
                ]
            }
            continue
        summary[clean_key] = _truncate_summary_text(value)
    return summary


def _duration_options(rules: dict[str, Any]) -> list[str]:
    """Return supported approval durations from stored rules."""
    raw = rules.get("duration_options")
    if not isinstance(raw, list):
        return ["once", "session"]
    out: list[str] = []
    for entry in raw:
        value = str(entry or "").strip().lower()
        if value in {"once", "session", "conversation"}:
            out.append(value)
    return out or ["once", "session"]


class McpHubApprovalService:
    """Evaluate and persist runtime MCP Hub approval requirements."""

    def __init__(self, repo: McpHubRepo):
        self.repo = repo

    async def record_decision(
        self,
        *,
        approval_policy_id: int | None,
        context_key: str,
        conversation_id: str | None,
        tool_name: str,
        scope_key: str,
        decision: str,
        consume_on_match: bool = False,
        expires_at: datetime | None = None,
        actor_id: int | None = None,
    ) -> dict[str, Any]:
        return await self.repo.create_approval_decision(
            approval_policy_id=approval_policy_id,
            context_key=context_key,
            conversation_id=conversation_id,
            tool_name=tool_name,
            scope_key=scope_key,
            decision=decision,
            consume_on_match=consume_on_match,
            expires_at=expires_at,
            actor_id=actor_id,
        )

    async def evaluate_tool_call(
        self,
        *,
        effective_policy: dict[str, Any] | None,
        tool_name: str,
        tool_args: Any,
        context: Any | None,
        tool_def: dict[str, Any] | None,
        is_write: bool | None,
        within_effective_policy: bool,
        force_approval: bool = False,
        approval_reason: str | None = None,
        scope_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        policy = dict(effective_policy or {})
        approval_policy_id = policy.get("approval_policy_id")
        approval_mode = str(policy.get("approval_mode") or "").strip() or None
        rules: dict[str, Any] = {}

        if approval_policy_id is not None:
            policy_row = await self.repo.get_approval_policy(int(approval_policy_id))
            if policy_row and bool(policy_row.get("is_active", True)):
                approval_mode = str(policy_row.get("mode") or approval_mode or "").strip() or approval_mode
                rules = dict(policy_row.get("rules") or {})

        if not approval_mode or approval_mode == "allow_silently":
            return {"status": "allow" if within_effective_policy else "deny", "reason": "no_approval_policy"}

        metadata = tool_def.get("metadata") if isinstance(tool_def, dict) and isinstance(tool_def.get("metadata"), dict) else {}
        category = str(metadata.get("category") or "").strip().lower()
        sensitive = bool(is_write) or bool(metadata.get("sensitive")) or category in {
            "admin",
            "execution",
            "ingestion",
            "management",
        }

        context_key = _context_key_for_request(context)
        conversation_id = _conversation_id_for_request(context)
        scope_key = _scope_key_for_tool_call(tool_name, tool_args, scope_payload=scope_payload)
        existing = await self.repo.find_active_approval_decision(
            approval_policy_id=int(approval_policy_id) if approval_policy_id is not None else None,
            context_key=context_key,
            conversation_id=conversation_id,
            tool_name=tool_name,
            scope_key=scope_key,
            decision="approved",
            now=datetime.now(timezone.utc),
        )
        if existing:
            if bool(existing.get("consume_on_match")):
                consumed = await self.repo.consume_active_approval_decision(
                    approval_policy_id=int(approval_policy_id) if approval_policy_id is not None else None,
                    context_key=context_key,
                    conversation_id=conversation_id,
                    tool_name=tool_name,
                    scope_key=scope_key,
                    now=datetime.now(timezone.utc),
                )
                if consumed:
                    return {"status": "allow", "reason": "active_approval", "decision": consumed}
            else:
                return {"status": "allow", "reason": "active_approval", "decision": existing}

        should_require = False
        reason = str(approval_reason or "outside_profile").strip() or "outside_profile"
        if force_approval:
            should_require = True
        elif approval_mode == "ask_every_time":
            should_require = True
            reason = "always_require_approval"
        elif approval_mode == "ask_on_sensitive_actions":
            should_require = sensitive
            reason = "sensitive_action"
        elif approval_mode in {"ask_outside_profile", "temporary_elevation_allowed"}:
            should_require = not within_effective_policy
            reason = "outside_profile"

        if not should_require:
            return {"status": "allow" if within_effective_policy else "deny", "reason": "policy_not_triggered"}

        return {
            "status": "approval_required",
            "approval": {
                "approval_policy_id": approval_policy_id,
                "mode": approval_mode,
                "tool_name": tool_name,
                "context_key": context_key,
                "conversation_id": conversation_id,
                "scope_key": scope_key,
                "reason": reason,
                "duration_options": _duration_options(rules),
                "arguments_summary": _arguments_summary(tool_args),
                "scope_context": dict(scope_payload or {}) if isinstance(scope_payload, dict) else None,
            },
        }


async def get_mcp_hub_approval_service() -> McpHubApprovalService:
    """Create an approval service backed by the current AuthNZ database."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    return McpHubApprovalService(repo=repo)
