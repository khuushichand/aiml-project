"""ACP Session persistence and admin query service.

Stores session metadata alongside the in-memory runner client state,
enabling session listing, usage tracking, and admin visibility.

The store is currently in-memory (dict-based) and is populated as sessions
are created/updated/closed through the ACP endpoints.  A future iteration
can persist to SQLite/PostgreSQL without changing the public API.
"""
from __future__ import annotations

import asyncio
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
    persona_id: str | None = None
    workspace_id: str | None = None
    workspace_group_id: str | None = None
    scope_snapshot_id: str | None = None
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
        }

    def to_detail_dict(self, *, has_websocket: bool = False) -> dict[str, Any]:
        d = self.to_info_dict(has_websocket=has_websocket)
        d["messages"] = list(self.messages)
        d["cwd"] = self.cwd
        return d


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

    # -- Session CRUD -------------------------------------------------------

    async def register_session(
        self,
        session_id: str,
        user_id: int,
        agent_type: str = "custom",
        name: str = "",
        cwd: str = "",
        tags: list[str] | None = None,
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
            rec.message_count += 1
            # Store message for fork support
            rec.messages.append({
                "role": "user",
                "content": prompt,
                "timestamp": now,
            })
            rec.messages.append({
                "role": "assistant",
                "content": result,
                "timestamp": now,
            })
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
            forked_messages = list(source.messages[:message_index + 1])
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
                messages=forked_messages,
                persona_id=source.persona_id,
                workspace_id=source.workspace_id,
                workspace_group_id=source.workspace_group_id,
                scope_snapshot_id=source.scope_snapshot_id,
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
