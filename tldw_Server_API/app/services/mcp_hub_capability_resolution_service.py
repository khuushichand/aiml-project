from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

_UNION_LIST_KEYS = {"allowed_tools", "denied_tools", "tool_names", "tool_patterns", "capabilities"}
_SUPPORTED_ENVIRONMENT_REQUIREMENTS = frozenset(
    {
        "local_mapping_required",
        "no_external_secrets",
        "workspace_bounded_read",
        "workspace_bounded_write",
    }
)


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
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _collect_scope_ids(metadata: dict[str, Any], singular_key: str, plural_key: str) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()

    def _maybe_add(raw: Any) -> None:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return
        if value in seen:
            return
        seen.add(value)
        out.append(value)

    if singular_key in metadata:
        _maybe_add(metadata.get(singular_key))
    plural = metadata.get(plural_key)
    if isinstance(plural, (list, tuple, set)):
        for raw in plural:
            _maybe_add(raw)
    return out


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


class CapabilityResolutionResult(BaseModel):
    resolved_capabilities: list[str] = Field(default_factory=list)
    unresolved_capabilities: list[str] = Field(default_factory=list)
    resolved_policy_document: dict[str, Any] = Field(default_factory=dict)
    mapping_summaries: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    supported_environment_requirements: list[str] = Field(default_factory=list)
    unsupported_environment_requirements: list[str] = Field(default_factory=list)


class McpHubCapabilityResolutionService:
    """Resolve portable capability names into concrete policy effects via scope-aware mappings."""

    def __init__(self, *, repo: McpHubRepo) -> None:
        self.repo = repo

    async def resolve_capabilities(
        self,
        *,
        capability_names: list[str],
        metadata: dict[str, Any] | None,
    ) -> CapabilityResolutionResult:
        metadata_map = dict(metadata or {})
        resolved_capabilities: list[str] = []
        unresolved_capabilities: list[str] = []
        resolved_policy_document: dict[str, Any] = {}
        mapping_summaries: list[dict[str, Any]] = []
        warnings: list[str] = []
        supported_environment_requirements: list[str] = []
        unsupported_environment_requirements: list[str] = []

        for capability_name in _unique(_as_str_list(capability_names)):
            mapping = await self._find_best_mapping(
                capability_name=capability_name,
                metadata=metadata_map,
            )
            if mapping is None:
                unresolved_capabilities.append(capability_name)
                warnings.append(f"No active capability adapter mapping found for '{capability_name}'")
                continue

            resolved_capabilities.append(capability_name)
            resolved_policy_document = _merge_policy_documents(
                resolved_policy_document,
                _as_dict(mapping.get("resolved_policy_document")),
            )
            supported, unsupported = self._split_environment_requirements(
                mapping.get("supported_environment_requirements")
            )
            supported_environment_requirements = _unique(
                supported_environment_requirements + supported
            )
            unsupported_environment_requirements = _unique(
                unsupported_environment_requirements + unsupported
            )
            mapping_summaries.append(
                {
                    "capability_name": capability_name,
                    "mapping_id": mapping.get("mapping_id"),
                    "mapping_scope_type": mapping.get("owner_scope_type"),
                    "mapping_scope_id": mapping.get("owner_scope_id"),
                    "resolved_effects": deepcopy(
                        _as_dict(mapping.get("resolved_policy_document"))
                    ),
                    "supported_environment_requirements": supported,
                    "unsupported_environment_requirements": unsupported,
                }
            )

        return CapabilityResolutionResult(
            resolved_capabilities=resolved_capabilities,
            unresolved_capabilities=unresolved_capabilities,
            resolved_policy_document=resolved_policy_document,
            mapping_summaries=mapping_summaries,
            warnings=warnings,
            supported_environment_requirements=supported_environment_requirements,
            unsupported_environment_requirements=unsupported_environment_requirements,
        )

    async def _find_best_mapping(
        self,
        *,
        capability_name: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        for team_id in _collect_scope_ids(metadata, "team_id", "team_ids"):
            mapping = await self.repo.find_active_capability_mapping(
                owner_scope_type="team",
                owner_scope_id=team_id,
                capability_name=capability_name,
            )
            if mapping is not None:
                return mapping

        for org_id in _collect_scope_ids(metadata, "org_id", "org_ids"):
            mapping = await self.repo.find_active_capability_mapping(
                owner_scope_type="org",
                owner_scope_id=org_id,
                capability_name=capability_name,
            )
            if mapping is not None:
                return mapping

        return await self.repo.find_active_capability_mapping(
            owner_scope_type="global",
            owner_scope_id=None,
            capability_name=capability_name,
        )

    @staticmethod
    def _split_environment_requirements(values: Any) -> tuple[list[str], list[str]]:
        supported: list[str] = []
        unsupported: list[str] = []
        for requirement in _unique(_as_str_list(values)):
            if requirement in _SUPPORTED_ENVIRONMENT_REQUIREMENTS:
                supported.append(requirement)
            else:
                unsupported.append(requirement)
        return supported, unsupported
