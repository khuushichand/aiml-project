from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo


def _context_metadata(context: Any | None) -> dict[str, Any]:
    metadata = getattr(context, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _context_key_for_request(context: Any | None) -> str:
    metadata = _context_metadata(context)
    user_id = str(getattr(context, "user_id", "") or "").strip()
    group_id = str(metadata.get("group_id") or "").strip()
    persona_id = str(metadata.get("persona_id") or "").strip()
    return f"user:{user_id}|group:{group_id}|persona:{persona_id}"


def _conversation_id_for_request(context: Any | None) -> str | None:
    metadata = _context_metadata(context)
    for key in ("conversation_id", "session_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    session_id = str(getattr(context, "session_id", "") or "").strip()
    return session_id or None


def _scope_key_for_tool_call(tool_name: str, tool_args: Any) -> str:
    command: str | None = None
    if isinstance(tool_args, dict):
        for key in ("command", "cmd"):
            value = tool_args.get(key)
            if isinstance(value, str) and value.strip():
                command = value.strip()
                break
    if command:
        digest = hashlib.sha256(command.encode("utf-8")).hexdigest()[:16]
        return f"tool:{tool_name}|command:{digest}"
    return f"tool:{tool_name}"


def _arguments_summary(tool_args: Any) -> dict[str, Any]:
    if not isinstance(tool_args, dict):
        return {}
    try:
        payload = json.loads(json.dumps(tool_args, default=str))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _duration_options(rules: dict[str, Any]) -> list[str]:
    raw = rules.get("duration_options")
    if not isinstance(raw, list):
        return ["once", "session"]
    out: list[str] = []
    for entry in raw:
        value = str(entry or "").strip()
        if value:
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
        expires_at: datetime | None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        return await self.repo.create_approval_decision(
            approval_policy_id=approval_policy_id,
            context_key=context_key,
            conversation_id=conversation_id,
            tool_name=tool_name,
            scope_key=scope_key,
            decision=decision,
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
        scope_key = _scope_key_for_tool_call(tool_name, tool_args)
        existing = await self.repo.find_active_approval_decision(
            approval_policy_id=int(approval_policy_id) if approval_policy_id is not None else None,
            context_key=context_key,
            conversation_id=conversation_id,
            tool_name=tool_name,
            scope_key=scope_key,
            now=datetime.now(timezone.utc),
        )
        if existing:
            normalized_decision = str(existing.get("decision") or "").strip().lower()
            if normalized_decision == "approved":
                return {"status": "allow", "reason": "active_approval", "decision": existing}
            if normalized_decision == "denied":
                return {"status": "deny", "reason": "approval_denied", "decision": existing}

        should_require = False
        reason = "outside_profile"
        if approval_mode == "ask_every_time":
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
            },
        }


async def get_mcp_hub_approval_service() -> McpHubApprovalService:
    """Create an approval service backed by the current AuthNZ database."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    return McpHubApprovalService(repo=repo)
