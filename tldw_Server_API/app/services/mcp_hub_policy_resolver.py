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
    """Return a shallow dict copy for mapping values, otherwise an empty dict."""
    return dict(value) if isinstance(value, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    """Normalize a scalar or iterable value into a list of non-empty strings."""
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
    """Preserve order while removing duplicate strings."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _collect_scope_ids(metadata: dict[str, Any], singular_key: str, plural_key: str) -> list[int]:
    """Collect integer scope ids from singular and plural metadata keys."""
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
    """Return the ordered assignment targets applicable to the runtime metadata."""
    targets: list[tuple[str, str | None]] = [("default", None)]
    group_id = str(metadata.get("group_id") or "").strip()
    if group_id:
        targets.append(("group", group_id))
    persona_id = str(metadata.get("persona_id") or "").strip()
    if persona_id:
        targets.append(("persona", persona_id))
    return targets


def _candidate_scope_filters(user_id: int | None, metadata: dict[str, Any]) -> list[tuple[str, int | None]]:
    """Build candidate owner-scope filters for assignment lookup."""
    filters: list[tuple[str, int | None]] = [("global", None)]
    filters.extend(("org", org_id) for org_id in _collect_scope_ids(metadata, "org_id", "org_ids"))
    filters.extend(("team", team_id) for team_id in _collect_scope_ids(metadata, "team_id", "team_ids"))
    if user_id is not None:
        filters.append(("user", user_id))
    return filters


def _merge_policy_documents(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge policy documents with union semantics for list-based capability fields."""
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
    """Return the effective allowed-tool pattern list from a policy document."""
    patterns = (
        _as_str_list(policy_document.get("allowed_tools"))
        + _as_str_list(policy_document.get("tool_patterns"))
        + _as_str_list(policy_document.get("tool_names"))
    )
    return _unique(patterns)


def _provenance_entries(
    *,
    layer_document: dict[str, Any],
    source_kind: str,
    assignment_id: int,
    profile_id: int | None,
    override_id: int | None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for field, value in layer_document.items():
        entries.append(
            {
                "field": str(field),
                "value": deepcopy(value),
                "source_kind": source_kind,
                "assignment_id": assignment_id,
                "profile_id": profile_id,
                "override_id": override_id,
                "effect": "merged" if field in _UNION_LIST_KEYS else "replaced",
            }
        )
    return entries


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
        provenance: list[dict[str, Any]] = []
        selected_assignment_id: int | None = None
        selected_assignment_workspace_ids: list[str] = []
        path_scope_object_cache: dict[int, dict[str, Any] | None] = {}

        for assignment in assignments:
            assignment_document: dict[str, Any] = {}
            profile_id = assignment.get("profile_id")
            profile_key: int | None = int(profile_id) if profile_id is not None else None
            assignment_id = int(assignment.get("id"))
            if profile_id is not None:
                if profile_key not in profile_cache:
                    profile_cache[profile_key] = await self.repo.get_permission_profile(profile_key)
                profile_row = profile_cache.get(profile_key) or {}
                if bool(profile_row.get("is_active", True)):
                    profile_path_scope_object_id = profile_row.get("path_scope_object_id")
                    profile_path_scope_key = (
                        int(profile_path_scope_object_id)
                        if profile_path_scope_object_id is not None
                        else None
                    )
                    if profile_path_scope_key is not None:
                        if profile_path_scope_key not in path_scope_object_cache:
                            path_scope_object_cache[profile_path_scope_key] = await self.repo.get_path_scope_object(
                                profile_path_scope_key
                            )
                        path_scope_row = path_scope_object_cache.get(profile_path_scope_key) or {}
                        if bool(path_scope_row.get("is_active", True)):
                            path_scope_document = _as_dict(path_scope_row.get("path_scope_document"))
                            assignment_document = _merge_policy_documents(
                                assignment_document,
                                path_scope_document,
                            )
                            provenance.extend(
                                _provenance_entries(
                                    layer_document=path_scope_document,
                                    source_kind="profile_path_scope_object",
                                    assignment_id=assignment_id,
                                    profile_id=profile_key,
                                    override_id=None,
                                )
                            )
                    profile_document = _as_dict(profile_row.get("policy_document"))
                    assignment_document = _merge_policy_documents(
                        assignment_document,
                        profile_document,
                    )
                    provenance.extend(
                        _provenance_entries(
                            layer_document=profile_document,
                            source_kind="profile",
                            assignment_id=assignment_id,
                            profile_id=profile_key,
                            override_id=None,
                        )
                    )

            assignment_path_scope_object_id = assignment.get("path_scope_object_id")
            assignment_path_scope_key = (
                int(assignment_path_scope_object_id)
                if assignment_path_scope_object_id is not None
                else None
            )
            if assignment_path_scope_key is not None:
                if assignment_path_scope_key not in path_scope_object_cache:
                    path_scope_object_cache[assignment_path_scope_key] = await self.repo.get_path_scope_object(
                        assignment_path_scope_key
                    )
                assignment_path_scope_row = path_scope_object_cache.get(assignment_path_scope_key) or {}
                if bool(assignment_path_scope_row.get("is_active", True)):
                    assignment_path_scope_document = _as_dict(
                        assignment_path_scope_row.get("path_scope_document")
                    )
                    assignment_document = _merge_policy_documents(
                        assignment_document,
                        assignment_path_scope_document,
                    )
                    provenance.extend(
                        _provenance_entries(
                            layer_document=assignment_path_scope_document,
                            source_kind="assignment_path_scope_object",
                            assignment_id=assignment_id,
                            profile_id=profile_key,
                            override_id=None,
                        )
                    )

            inline_policy_document = _as_dict(assignment.get("inline_policy_document"))
            assignment_document = _merge_policy_documents(
                assignment_document,
                inline_policy_document,
            )
            provenance.extend(
                _provenance_entries(
                    layer_document=inline_policy_document,
                    source_kind="assignment_inline",
                    assignment_id=assignment_id,
                    profile_id=profile_key,
                    override_id=None,
                )
            )
            override_row = await self.repo.get_policy_override_by_assignment(assignment_id)
            if override_row and bool(override_row.get("is_active", True)):
                override_document = _as_dict(override_row.get("override_policy_document"))
                assignment_document = _merge_policy_documents(
                    assignment_document,
                    override_document,
                )
                provenance.extend(
                    _provenance_entries(
                        layer_document=override_document,
                        source_kind="assignment_override",
                        assignment_id=assignment_id,
                        profile_id=profile_key,
                        override_id=int(override_row.get("id")),
                    )
                )
            merged_policy_document = _merge_policy_documents(merged_policy_document, assignment_document)
            approval_policy_id = assignment.get("approval_policy_id")
            if approval_policy_id is not None:
                resolved_approval_policy_id = int(approval_policy_id)
            selected_assignment_id = assignment_id
            selected_assignment_workspace_ids = _unique(
                _as_str_list(
                    [
                        row.get("workspace_id")
                        for row in await self.repo.list_policy_assignment_workspaces(assignment_id)
                    ]
                )
            )
            sources.append(
                {
                    "assignment_id": assignment_id,
                    "target_type": str(assignment.get("target_type") or "default"),
                    "target_id": assignment.get("target_id"),
                    "owner_scope_type": str(assignment.get("owner_scope_type") or "global"),
                    "owner_scope_id": assignment.get("owner_scope_id"),
                    "profile_id": assignment.get("profile_id"),
                    "path_scope_object_id": assignment.get("path_scope_object_id"),
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
            "selected_assignment_id": selected_assignment_id,
            "selected_assignment_workspace_ids": selected_assignment_workspace_ids,
            "sources": sources,
            "provenance": provenance,
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
            "selected_assignment_id": None,
            "selected_assignment_workspace_ids": [],
            "sources": [],
            "provenance": [],
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
