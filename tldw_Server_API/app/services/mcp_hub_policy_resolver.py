from __future__ import annotations

from copy import deepcopy
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

_TARGET_ORDER = {"default": 0, "group": 1, "persona": 2}
_SCOPE_ORDER = {"global": 0, "org": 1, "team": 2, "user": 3}
_UNION_LIST_KEYS = {"allowed_tools", "denied_tools", "tool_names", "tool_patterns", "capabilities"}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for entry in value:
        cleaned = str(entry or "").strip()
        if cleaned:
            out.append(cleaned)
    return out


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _collect_scope_ids(metadata: dict[str, Any], singular_key: str, plural_key: str) -> list[int]:
    raw_values: list[Any] = []
    if singular_key in metadata:
        raw_values.append(metadata.get(singular_key))
    plural_value = metadata.get(plural_key)
    if isinstance(plural_value, (list, tuple, set)):
        raw_values.extend(list(plural_value))

    out: set[int] = set()
    for raw in raw_values:
        try:
            out.add(int(raw))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def _extract_targets(metadata: dict[str, Any]) -> list[tuple[str, str | None]]:
    targets: list[tuple[str, str | None]] = [("default", None)]
    group_id = str(metadata.get("group_id") or "").strip()
    if group_id:
        targets.append(("group", group_id))
    persona_id = str(metadata.get("persona_id") or "").strip()
    if persona_id:
        targets.append(("persona", persona_id))
    return targets


def _candidate_scope_filters(user_id: int | None, metadata: dict[str, Any]) -> list[tuple[str, int | None]]:
    filters: list[tuple[str, int | None]] = [("global", None)]
    filters.extend(("org", org_id) for org_id in _collect_scope_ids(metadata, "org_id", "org_ids"))
    filters.extend(("team", team_id) for team_id in _collect_scope_ids(metadata, "team_id", "team_ids"))
    if user_id is not None:
        filters.append(("user", user_id))
    return filters


def _merge_policy_documents(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if key in _UNION_LIST_KEYS:
            merged[key] = _unique(_as_str_list(merged.get(key)) + _as_str_list(value))
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_policy_documents(_as_dict(merged.get(key)), value)
            continue
        merged[key] = deepcopy(value)
    return merged


def _allowed_tool_patterns(policy_document: dict[str, Any]) -> list[str]:
    patterns = (
        _as_str_list(policy_document.get("allowed_tools"))
        + _as_str_list(policy_document.get("tool_patterns"))
        + _as_str_list(policy_document.get("tool_names"))
    )
    return _unique(patterns)


class McpHubPolicyResolver:
    """Resolve effective MCP Hub policy for a runtime request context."""

    def __init__(self, repo: McpHubRepo):
        self.repo = repo

    async def resolve_for_context(
        self,
        *,
        user_id: int | str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata_map = dict(metadata or {})
        if not metadata_map.get("mcp_policy_context_enabled"):
            return self._disabled_policy()

        user_id_int: int | None = None
        try:
            if user_id is not None:
                user_id_int = int(str(user_id))
        except (TypeError, ValueError):
            user_id_int = None

        assignments = await self._load_applicable_assignments(
            user_id=user_id_int,
            metadata=metadata_map,
        )
        if not assignments:
            return self._disabled_policy()

        merged_policy_document: dict[str, Any] = {}
        sources: list[dict[str, Any]] = []
        profile_cache: dict[int, dict[str, Any] | None] = {}
        resolved_approval_policy_id: int | None = None

        for assignment in assignments:
            assignment_document: dict[str, Any] = {}
            profile_id = assignment.get("profile_id")
            if profile_id is not None:
                profile_key = int(profile_id)
                if profile_key not in profile_cache:
                    profile_cache[profile_key] = await self.repo.get_permission_profile(profile_key)
                profile_row = profile_cache.get(profile_key) or {}
                if bool(profile_row.get("is_active", True)):
                    assignment_document = _merge_policy_documents(
                        assignment_document,
                        _as_dict(profile_row.get("policy_document")),
                    )

            assignment_document = _merge_policy_documents(
                assignment_document,
                _as_dict(assignment.get("inline_policy_document")),
            )
            merged_policy_document = _merge_policy_documents(merged_policy_document, assignment_document)
            approval_policy_id = assignment.get("approval_policy_id")
            if approval_policy_id is not None:
                resolved_approval_policy_id = int(approval_policy_id)
            sources.append(
                {
                    "assignment_id": int(assignment.get("id")),
                    "target_type": str(assignment.get("target_type") or "default"),
                    "target_id": assignment.get("target_id"),
                    "owner_scope_type": str(assignment.get("owner_scope_type") or "global"),
                    "owner_scope_id": assignment.get("owner_scope_id"),
                    "profile_id": assignment.get("profile_id"),
                }
            )

        return {
            "enabled": True,
            "allowed_tools": _allowed_tool_patterns(merged_policy_document),
            "denied_tools": _unique(_as_str_list(merged_policy_document.get("denied_tools"))),
            "capabilities": _unique(_as_str_list(merged_policy_document.get("capabilities"))),
            "approval_policy_id": resolved_approval_policy_id,
            "approval_mode": str(merged_policy_document.get("approval_mode") or "").strip() or None,
            "policy_document": merged_policy_document,
            "sources": sources,
        }

    async def _load_applicable_assignments(
        self,
        *,
        user_id: int | None,
        metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for scope_type, scope_id in _candidate_scope_filters(user_id, metadata):
            for target_type, target_id in _extract_targets(metadata):
                rows.extend(
                    await self.repo.list_policy_assignments(
                        owner_scope_type=scope_type,
                        owner_scope_id=scope_id,
                        target_type=target_type,
                        target_id=target_id,
                    )
                )

        filtered = [
            row
            for row in rows
            if bool(row.get("is_active", True))
            and str(row.get("target_type") or "").strip().lower() in _TARGET_ORDER
            and str(row.get("owner_scope_type") or "").strip().lower() in _SCOPE_ORDER
        ]
        deduped: dict[int, dict[str, Any]] = {}
        for row in filtered:
            deduped[int(row.get("id"))] = row

        return sorted(
            deduped.values(),
            key=lambda row: (
                _TARGET_ORDER.get(str(row.get("target_type") or "").strip().lower(), 99),
                _SCOPE_ORDER.get(str(row.get("owner_scope_type") or "").strip().lower(), 99),
                int(row.get("id") or 0),
            ),
        )

    @staticmethod
    def _disabled_policy() -> dict[str, Any]:
        return {
            "enabled": False,
            "allowed_tools": [],
            "denied_tools": [],
            "capabilities": [],
            "approval_policy_id": None,
            "approval_mode": None,
            "policy_document": {},
            "sources": [],
        }


async def get_mcp_hub_policy_resolver() -> McpHubPolicyResolver:
    """Create a policy resolver backed by the current AuthNZ database."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    try:
        await repo.ensure_tables()
    except Exception as exc:
        logger.debug("MCP Hub policy resolver table ensure failed: {}", exc)
        raise
    return McpHubPolicyResolver(repo=repo)
