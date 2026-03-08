"""ACP Session persistence and admin query service.

Stores session metadata alongside the in-memory runner client state,
enabling session listing, usage tracking, and admin visibility.

The store is currently in-memory (dict-based) and is populated as sessions
are created/updated/closed through the ACP endpoints.  A future iteration
can persist to SQLite/PostgreSQL without changing the public API.
"""
from __future__ import annotations

import asyncio
import copy
import fnmatch
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SessionTokenUsage:
    """Accumulated token usage for a session."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, prompt: int = 0, completion: int = 0) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class SessionRecord:
    """Persistent metadata for an ACP session."""
    session_id: str
    user_id: int
    agent_type: str = "custom"
    name: str = ""
    status: str = "active"  # active | closed | error
    cwd: str = ""
    created_at: str = ""
    last_activity_at: str | None = None
    message_count: int = 0
    usage: SessionTokenUsage = field(default_factory=SessionTokenUsage)
    tags: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)
    persona_id: str | None = None
    workspace_id: str | None = None
    workspace_group_id: str | None = None
    scope_snapshot_id: str | None = None
    bootstrap_ready: bool = True
    needs_bootstrap: bool = False
    # Forking lineage
    forked_from: str | None = None

    def to_info_dict(self, *, has_websocket: bool = False) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "message_count": self.message_count,
            "usage": self.usage.to_dict(),
            "tags": list(self.tags),
            "has_websocket": has_websocket,
            "persona_id": self.persona_id,
            "workspace_id": self.workspace_id,
            "workspace_group_id": self.workspace_group_id,
            "scope_snapshot_id": self.scope_snapshot_id,
            "forked_from": self.forked_from,
        }

    def to_detail_dict(
        self,
        *,
        has_websocket: bool = False,
        fork_lineage: list[str] | None = None,
    ) -> dict[str, Any]:
        d = self.to_info_dict(has_websocket=has_websocket)
        d["messages"] = list(self.messages)
        d["cwd"] = self.cwd
        d["fork_lineage"] = fork_lineage or []
        return d


def _normalize_text_content(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            normalized = _normalize_text_content(item)
            if normalized:
                parts.append(normalized)
        if parts:
            return "\n".join(parts)
        return None

    if isinstance(value, dict):
        content_type = str(value.get("type") or "").strip().lower()
        if content_type in {"text", "input_text", "output_text"}:
            direct_text = value.get("text")
            if isinstance(direct_text, str) and direct_text.strip():
                return direct_text.strip()
        for key in ("content", "text", "message", "output", "detail", "value"):
            normalized = _normalize_text_content(value.get(key))
            if normalized:
                return normalized
        return None

    return None


def _normalize_prompt_messages(prompt: list[dict[str, Any]], timestamp: str) -> tuple[list[dict[str, Any]], bool]:
    entries: list[dict[str, Any]] = []
    bootstrap_ready = True
    for item in prompt:
        role = "user"
        if isinstance(item, dict):
            role = str(item.get("role") or "user")
            content = _normalize_text_content(item.get("content"))
            entry: dict[str, Any] = {"role": role, "content": content, "timestamp": timestamp}
            entry["raw_prompt"] = copy.deepcopy(item)
        else:
            content = None
            entry = {"role": role, "content": None, "timestamp": timestamp, "raw_prompt": copy.deepcopy(item)}
        if content is None:
            bootstrap_ready = False
        entries.append(entry)
    return entries, bootstrap_ready


def _normalize_result_message(result: dict[str, Any], timestamp: str) -> tuple[dict[str, Any], bool]:
    content = _normalize_text_content(result)
    entry: dict[str, Any] = {
        "role": "assistant",
        "content": content,
        "timestamp": timestamp,
        "raw_result": copy.deepcopy(result),
    }
    return entry, content is not None


def _messages_bootstrap_ready(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        if not isinstance(message, dict):
            return False
        role = str(message.get("role") or "").strip()
        content = message.get("content")
        if not role or not isinstance(content, str) or not content.strip():
            return False
    return True


# ---------------------------------------------------------------------------
# Permission Policy store
# ---------------------------------------------------------------------------

@dataclass
class PermissionPolicyRule:
    tool_pattern: str
    tier: str  # auto | batch | individual


@dataclass
class PermissionPolicy:
    id: int
    name: str
    description: str = ""
    rules: list[PermissionPolicyRule] = field(default_factory=list)
    org_id: int | None = None
    team_id: int | None = None
    priority: int = 0
    created_at: str = ""
    updated_at: str | None = None


# ---------------------------------------------------------------------------
# Agent Config store
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    id: int
    type: str
    name: str
    description: str = ""
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None
    denied_tools: list[str] | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_api_key: str | None = None
    org_id: int | None = None
    team_id: int | None = None
    enabled: bool = True
    created_at: str = ""
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        import os
        is_configured = True
        if self.requires_api_key:
            is_configured = bool(os.getenv(self.requires_api_key, ""))
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "allowed_tools": self.allowed_tools,
            "denied_tools": self.denied_tools,
            "parameters": dict(self.parameters),
            "requires_api_key": self.requires_api_key,
            "org_id": self.org_id,
            "team_id": self.team_id,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_configured": is_configured,
        }


# ---------------------------------------------------------------------------
# Singleton session store
# ---------------------------------------------------------------------------

class ACPSessionStore:
    """In-memory session metadata store with query capabilities."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()
        # Agent configs — keyed by id
        self._agent_configs: dict[int, AgentConfig] = {}
        self._agent_config_seq = 0
        # Permission policies — keyed by id
        self._permission_policies: dict[int, PermissionPolicy] = {}
        self._permission_policy_seq = 0
        # Session TTL cleanup task
        self._cleanup_task: asyncio.Task | None = None
        # Quotas (loaded from config on first use)
        self._session_ttl_seconds: int = 86400
        self._max_concurrent_per_user: int = 5
        self._max_tokens_per_session: int = 1_000_000
        self._max_session_duration_seconds: int = 14400

    def configure_quotas(
        self,
        session_ttl_seconds: int = 86400,
        max_concurrent_per_user: int = 5,
        max_tokens_per_session: int = 1_000_000,
        max_session_duration_seconds: int = 14400,
    ) -> None:
        """Set quota limits from config."""
        self._session_ttl_seconds = session_ttl_seconds
        self._max_concurrent_per_user = max_concurrent_per_user
        self._max_tokens_per_session = max_tokens_per_session
        self._max_session_duration_seconds = max_session_duration_seconds

    def start_cleanup_task(self) -> None:
        """Start background task to evict expired sessions."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.ensure_future(self._cleanup_loop())

    def stop_cleanup_task(self) -> None:
        """Cancel the cleanup background task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Periodically evict expired sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._evict_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("ACP session cleanup error: {}", exc)
                await asyncio.sleep(60)

    async def _evict_expired_sessions(self) -> int:
        """Evict sessions past TTL or max duration. Returns count evicted."""
        now = time.time()
        evicted = 0
        async with self._lock:
            to_evict: list[str] = []
            for sid, rec in self._sessions.items():
                if rec.status != "active":
                    continue
                try:
                    created = datetime.fromisoformat(rec.created_at).timestamp()
                except (ValueError, TypeError):
                    continue
                age = now - created
                if age > self._session_ttl_seconds:
                    to_evict.append(sid)
                    continue
                if age > self._max_session_duration_seconds:
                    to_evict.append(sid)
            for sid in to_evict:
                rec = self._sessions.get(sid)
                if rec:
                    rec.status = "closed"
                    rec.last_activity_at = datetime.now(timezone.utc).isoformat()
                    evicted += 1
                    logger.info("ACP session {} evicted (TTL/duration expired)", sid)
        return evicted

    async def check_session_quota(self, user_id: int) -> dict[str, Any] | None:
        """Check if user can create a new session. Returns None if ok, or error dict."""
        active_count = 0
        async with self._lock:
            for rec in self._sessions.values():
                if rec.user_id == user_id and rec.status == "active":
                    active_count += 1
        if active_count >= self._max_concurrent_per_user:
            return {
                "code": "quota_exceeded",
                "message": f"Max concurrent sessions ({self._max_concurrent_per_user}) exceeded",
                "current": active_count,
                "limit": self._max_concurrent_per_user,
            }
        return None

    async def check_token_quota(self, session_id: str) -> dict[str, Any] | None:
        """Check if a session has exceeded its token quota. Returns None if ok."""
        rec = self._sessions.get(session_id)
        if not rec:
            return None
        if rec.usage.total_tokens >= self._max_tokens_per_session:
            return {
                "code": "token_quota_exceeded",
                "message": f"Session token limit ({self._max_tokens_per_session}) exceeded",
                "current": rec.usage.total_tokens,
                "limit": self._max_tokens_per_session,
            }
        return None

    async def get_quota_status(self, user_id: int, session_id: str | None = None) -> dict[str, Any]:
        """Get current quota usage for a user/session."""
        active_count = 0
        async with self._lock:
            for rec in self._sessions.values():
                if rec.user_id == user_id and rec.status == "active":
                    active_count += 1
        result: dict[str, Any] = {
            "concurrent_sessions": {
                "current": active_count,
                "limit": self._max_concurrent_per_user,
            },
            "session_ttl_seconds": self._session_ttl_seconds,
            "max_session_duration_seconds": self._max_session_duration_seconds,
        }
        if session_id:
            rec = self._sessions.get(session_id)
            if rec:
                result["session_tokens"] = {
                    "current": rec.usage.total_tokens,
                    "limit": self._max_tokens_per_session,
                }
        return result

    # -- Session CRUD -------------------------------------------------------

    async def register_session(
        self,
        session_id: str,
        user_id: int,
        agent_type: str = "custom",
        name: str = "",
        cwd: str = "",
        tags: list[str] | None = None,
        mcp_servers: list[dict[str, Any]] | None = None,
        persona_id: str | None = None,
        workspace_id: str | None = None,
        workspace_group_id: str | None = None,
        scope_snapshot_id: str | None = None,
    ) -> SessionRecord:
        now = datetime.now(timezone.utc).isoformat()
        record = SessionRecord(
            session_id=session_id,
            user_id=user_id,
            agent_type=agent_type,
            name=name,
            cwd=cwd,
            created_at=now,
            last_activity_at=now,
            tags=tags or [],
            mcp_servers=copy.deepcopy(mcp_servers or []),
            persona_id=persona_id,
            workspace_id=workspace_id,
            workspace_group_id=workspace_group_id,
            scope_snapshot_id=scope_snapshot_id,
        )
        async with self._lock:
            self._sessions[session_id] = record
        logger.debug("Registered ACP session {} for user {}", session_id, user_id)
        return record

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            rec = self._sessions.get(session_id)
            if rec:
                rec.status = "closed"
                rec.last_activity_at = datetime.now(timezone.utc).isoformat()

    async def record_prompt(
        self,
        session_id: str,
        prompt: list[dict[str, Any]],
        result: dict[str, Any],
    ) -> SessionTokenUsage | None:
        """Record a prompt+response exchange and accumulate token usage."""
        async with self._lock:
            rec = self._sessions.get(session_id)
            if not rec:
                return None
            now = datetime.now(timezone.utc).isoformat()
            rec.last_activity_at = now
            prompt_entries, prompt_bootstrap_ready = _normalize_prompt_messages(prompt, now)
            result_entry, result_bootstrap_ready = _normalize_result_message(result, now)
            rec.messages.extend(prompt_entries)
            rec.messages.append(result_entry)
            rec.message_count = len(rec.messages)
            rec.bootstrap_ready = rec.bootstrap_ready and prompt_bootstrap_ready and result_bootstrap_ready
            # Extract token usage from result
            usage_data = result.get("usage") or {}
            prompt_tokens = int(usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0)
            completion_tokens = int(usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0)
            rec.usage.add(prompt_tokens, completion_tokens)
            return SessionTokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )

    async def get_session(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    async def get_fork_lineage(self, session_id: str, *, max_depth: int = 50) -> list[str]:
        """Walk the forked_from chain and return ancestor session IDs (oldest first)."""
        lineage: list[str] = []
        current_id = session_id
        seen: set[str] = {current_id}
        for _ in range(max_depth):
            rec = self._sessions.get(current_id)
            if not rec or not rec.forked_from:
                break
            parent_id = rec.forked_from
            if parent_id in seen:
                break  # cycle guard
            seen.add(parent_id)
            lineage.append(parent_id)
            current_id = parent_id
        lineage.reverse()  # oldest ancestor first
        return lineage

    async def build_bootstrap_prompt(
        self,
        session_id: str,
        prompt: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        async with self._lock:
            rec = self._sessions.get(session_id)
            if not rec or not rec.needs_bootstrap:
                return copy.deepcopy(prompt), False

            if not _messages_bootstrap_ready(rec.messages):
                rec.bootstrap_ready = False
                raise ValueError("fork_not_resumable")

            bootstrap_prompt = [
                {"role": str(message["role"]), "content": str(message["content"])}
                for message in rec.messages
            ]
            return bootstrap_prompt + copy.deepcopy(prompt), True

    async def clear_bootstrap(self, session_id: str) -> None:
        async with self._lock:
            rec = self._sessions.get(session_id)
            if rec:
                rec.needs_bootstrap = False
                rec.last_activity_at = datetime.now(timezone.utc).isoformat()

    async def list_sessions(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SessionRecord], int]:
        """List sessions with optional filters. Returns (records, total_count)."""
        results: list[SessionRecord] = []
        for rec in self._sessions.values():
            if user_id is not None and rec.user_id != user_id:
                continue
            if status is not None and rec.status != status:
                continue
            if agent_type is not None and rec.agent_type != agent_type:
                continue
            results.append(rec)
        # Sort by created_at descending
        results.sort(key=lambda r: r.created_at, reverse=True)
        total = len(results)
        return results[offset:offset + limit], total

    async def fork_session(
        self,
        source_session_id: str,
        new_session_id: str,
        message_index: int,
        user_id: int,
        name: str | None = None,
    ) -> SessionRecord | None:
        """Fork a session, copying messages up to message_index."""
        async with self._lock:
            source = self._sessions.get(source_session_id)
            if not source:
                return None
            if source.user_id != user_id:
                return None
            # message_index is inclusive (0-based) — copy messages 0..message_index
            forked_messages = copy.deepcopy(source.messages[:message_index + 1])
            now = datetime.now(timezone.utc).isoformat()
            fork_name = name or f"Fork of {source.name}"
            forked = SessionRecord(
                session_id=new_session_id,
                user_id=user_id,
                agent_type=source.agent_type,
                name=fork_name,
                cwd=source.cwd,
                created_at=now,
                last_activity_at=now,
                message_count=len(forked_messages),
                tags=list(source.tags),
                mcp_servers=copy.deepcopy(source.mcp_servers),
                messages=forked_messages,
                persona_id=source.persona_id,
                workspace_id=source.workspace_id,
                workspace_group_id=source.workspace_group_id,
                scope_snapshot_id=source.scope_snapshot_id,
                bootstrap_ready=_messages_bootstrap_ready(forked_messages),
                needs_bootstrap=bool(forked_messages),
                forked_from=source_session_id,
            )
            self._sessions[new_session_id] = forked
        return forked

    # -- Agent Config CRUD --------------------------------------------------

    async def create_agent_config(self, data: dict[str, Any]) -> AgentConfig:
        async with self._lock:
            self._agent_config_seq += 1
            now = datetime.now(timezone.utc).isoformat()
            config = AgentConfig(
                id=self._agent_config_seq,
                type=data["type"],
                name=data["name"],
                description=data.get("description", ""),
                system_prompt=data.get("system_prompt"),
                allowed_tools=data.get("allowed_tools"),
                denied_tools=data.get("denied_tools"),
                parameters=data.get("parameters", {}),
                requires_api_key=data.get("requires_api_key"),
                org_id=data.get("org_id"),
                team_id=data.get("team_id"),
                enabled=data.get("enabled", True),
                created_at=now,
            )
            self._agent_configs[config.id] = config
        return config

    async def update_agent_config(self, config_id: int, data: dict[str, Any]) -> AgentConfig | None:
        async with self._lock:
            config = self._agent_configs.get(config_id)
            if not config:
                return None
            for key in ("name", "description", "system_prompt", "allowed_tools",
                        "denied_tools", "parameters", "requires_api_key",
                        "org_id", "team_id", "enabled", "type"):
                if key in data:
                    setattr(config, key, data[key])
            config.updated_at = datetime.now(timezone.utc).isoformat()
        return config

    async def delete_agent_config(self, config_id: int) -> bool:
        async with self._lock:
            return self._agent_configs.pop(config_id, None) is not None

    async def get_agent_config(self, config_id: int) -> AgentConfig | None:
        return self._agent_configs.get(config_id)

    async def list_agent_configs(
        self,
        *,
        org_id: int | None = None,
        team_id: int | None = None,
        enabled_only: bool = False,
    ) -> list[AgentConfig]:
        results = []
        for cfg in self._agent_configs.values():
            if enabled_only and not cfg.enabled:
                continue
            if org_id is not None and cfg.org_id is not None and cfg.org_id != org_id:
                continue
            if team_id is not None and cfg.team_id is not None and cfg.team_id != team_id:
                continue
            results.append(cfg)
        return results

    # -- Permission Policy CRUD --------------------------------------------

    async def create_permission_policy(self, data: dict[str, Any]) -> PermissionPolicy:
        async with self._lock:
            self._permission_policy_seq += 1
            now = datetime.now(timezone.utc).isoformat()
            rules = [
                PermissionPolicyRule(tool_pattern=r["tool_pattern"], tier=r["tier"])
                for r in data.get("rules", [])
            ]
            policy = PermissionPolicy(
                id=self._permission_policy_seq,
                name=data["name"],
                description=data.get("description", ""),
                rules=rules,
                org_id=data.get("org_id"),
                team_id=data.get("team_id"),
                priority=data.get("priority", 0),
                created_at=now,
            )
            self._permission_policies[policy.id] = policy
        return policy

    async def update_permission_policy(self, policy_id: int, data: dict[str, Any]) -> PermissionPolicy | None:
        async with self._lock:
            policy = self._permission_policies.get(policy_id)
            if not policy:
                return None
            for key in ("name", "description", "org_id", "team_id", "priority"):
                if key in data:
                    setattr(policy, key, data[key])
            if "rules" in data:
                policy.rules = [
                    PermissionPolicyRule(tool_pattern=r["tool_pattern"], tier=r["tier"])
                    for r in data["rules"]
                ]
            policy.updated_at = datetime.now(timezone.utc).isoformat()
        return policy

    async def delete_permission_policy(self, policy_id: int) -> bool:
        async with self._lock:
            return self._permission_policies.pop(policy_id, None) is not None

    async def list_permission_policies(
        self,
        *,
        org_id: int | None = None,
        team_id: int | None = None,
    ) -> list[PermissionPolicy]:
        results = []
        for pol in self._permission_policies.values():
            if org_id is not None and pol.org_id is not None and pol.org_id != org_id:
                continue
            if team_id is not None and pol.team_id is not None and pol.team_id != team_id:
                continue
            results.append(pol)
        results.sort(key=lambda p: (-p.priority, p.name))
        return results

    def resolve_permission_tier(self, tool_name: str) -> str | None:
        """Consult stored policies to determine a permission tier for a tool.

        Returns None if no policy rule matches (caller should fall back to
        the default heuristic).
        """
        best_priority = -1
        best_tier: str | None = None
        for pol in self._permission_policies.values():
            for rule in pol.rules:
                if fnmatch.fnmatch(tool_name.lower(), rule.tool_pattern.lower()):
                    if pol.priority > best_priority:
                        best_priority = pol.priority
                        best_tier = rule.tier
        return best_tier


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: ACPSessionStore | None = None
_store_lock = asyncio.Lock()


async def get_acp_session_store() -> ACPSessionStore:
    global _store
    if _store is None:
        async with _store_lock:
            if _store is None:
                _store = ACPSessionStore()
    return _store
