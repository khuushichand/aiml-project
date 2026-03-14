from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.exceptions import BadRequestError, ResourceNotFoundError
from tldw_Server_API.app.services.mcp_hub_tool_registry import McpHubToolRegistryService

_SUPPORTED_SCOPE_TYPES = frozenset({"global", "org", "team"})
_SUPPORTED_ADAPTER_CONTRACT_VERSION = 1
_SUPPORTED_ENVIRONMENT_REQUIREMENTS = frozenset(
    {
        "local_mapping_required",
        "no_external_secrets",
        "workspace_bounded_read",
        "workspace_bounded_write",
    }
)
_LIST_POLICY_KEYS = frozenset(
    {
        "allowed_tools",
        "denied_tools",
        "tool_names",
        "tool_patterns",
        "capabilities",
        "tool_modules",
        "module_ids",
    }
)
_EXACT_TOOL_REF_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


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


def _looks_like_exact_tool_reference(value: str) -> bool:
    candidate = str(value or "").strip()
    if not candidate:
        return False
    return bool(_EXACT_TOOL_REF_RE.fullmatch(candidate))


class McpHubCapabilityAdapterService:
    """Validate, preview, and persist scope-aware capability adapter mappings."""

    def __init__(
        self,
        *,
        repo: McpHubRepo,
        tool_registry: McpHubToolRegistryService,
    ) -> None:
        self.repo = repo
        self.tool_registry = tool_registry

    async def preview_mapping(
        self,
        *,
        mapping_id: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        capability_name: str,
        adapter_contract_version: int,
        resolved_policy_document: dict[str, Any],
        supported_environment_requirements: list[str],
        title: str | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        normalized_scope_type, normalized_scope_id, display_scope = self._normalize_scope(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )
        normalized_mapping_id = str(mapping_id or "").strip()
        if not normalized_mapping_id:
            raise BadRequestError("mapping_id is required")
        normalized_capability_name = str(capability_name or "").strip()
        if not normalized_capability_name:
            raise BadRequestError("capability_name is required")
        normalized_title = str(title or normalized_mapping_id).strip()
        normalized_policy_document = self._normalize_policy_document(resolved_policy_document)
        module_to_tool_names = await self._validate_policy_document_against_registry(
            normalized_policy_document
        )
        normalized_policy_document = self._expand_module_policy_effects(
            normalized_policy_document,
            module_to_tool_names=module_to_tool_names,
        )
        normalized_requirements, warnings = self._normalize_environment_requirements(
            supported_environment_requirements
        )
        normalized_mapping = {
            "mapping_id": normalized_mapping_id,
            "title": normalized_title,
            "description": description,
            "owner_scope_type": normalized_scope_type,
            "owner_scope_id": normalized_scope_id,
            "capability_name": normalized_capability_name,
            "adapter_contract_version": self._normalize_adapter_contract_version(
                adapter_contract_version
            ),
            "resolved_policy_document": normalized_policy_document,
            "supported_environment_requirements": normalized_requirements,
            "is_active": bool(is_active),
        }
        return {
            "normalized_mapping": normalized_mapping,
            "warnings": warnings,
            "affected_scope_summary": {
                "owner_scope_type": normalized_scope_type,
                "owner_scope_id": normalized_scope_id,
                "display_scope": display_scope,
            },
        }

    async def preview_update(
        self,
        capability_adapter_mapping_id: int,
        *,
        mapping_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        capability_name: str | None = None,
        adapter_contract_version: int | None = None,
        resolved_policy_document: dict[str, Any] | None = None,
        supported_environment_requirements: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        existing = await self.repo.get_capability_adapter_mapping(capability_adapter_mapping_id)
        if existing is None:
            raise ResourceNotFoundError(
                "mcp_capability_adapter_mapping",
                identifier=str(capability_adapter_mapping_id),
            )
        return await self.preview_mapping(
            mapping_id=mapping_id if mapping_id is not None else str(existing["mapping_id"]),
            owner_scope_type=owner_scope_type if owner_scope_type is not None else str(existing["owner_scope_type"]),
            owner_scope_id=owner_scope_id if owner_scope_type is not None or owner_scope_id is not None else existing.get("owner_scope_id"),
            capability_name=capability_name if capability_name is not None else str(existing["capability_name"]),
            adapter_contract_version=(
                adapter_contract_version
                if adapter_contract_version is not None
                else int(existing["adapter_contract_version"])
            ),
            resolved_policy_document=(
                resolved_policy_document
                if resolved_policy_document is not None
                else dict(existing.get("resolved_policy_document") or {})
            ),
            supported_environment_requirements=(
                supported_environment_requirements
                if supported_environment_requirements is not None
                else list(existing.get("supported_environment_requirements") or [])
            ),
            title=title if title is not None else str(existing.get("title") or existing["mapping_id"]),
            description=description if description is not None else existing.get("description"),
            is_active=bool(existing.get("is_active")) if is_active is None else bool(is_active),
        )

    async def create_mapping(
        self,
        *,
        mapping_id: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        capability_name: str,
        adapter_contract_version: int,
        resolved_policy_document: dict[str, Any],
        supported_environment_requirements: list[str],
        actor_id: int | None,
        title: str | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        preview = await self.preview_mapping(
            mapping_id=mapping_id,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            capability_name=capability_name,
            adapter_contract_version=adapter_contract_version,
            resolved_policy_document=resolved_policy_document,
            supported_environment_requirements=supported_environment_requirements,
            title=title,
            description=description,
            is_active=is_active,
        )
        normalized = dict(preview["normalized_mapping"])
        try:
            return await self.repo.create_capability_adapter_mapping(
                mapping_id=normalized["mapping_id"],
                owner_scope_type=normalized["owner_scope_type"],
                owner_scope_id=normalized["owner_scope_id"],
                capability_name=normalized["capability_name"],
                adapter_contract_version=normalized["adapter_contract_version"],
                resolved_policy_document=normalized["resolved_policy_document"],
                supported_environment_requirements=normalized["supported_environment_requirements"],
                actor_id=actor_id,
                title=normalized["title"],
                description=normalized.get("description"),
                is_active=normalized["is_active"],
            )
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

    async def list_capability_adapter_mappings(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.repo.list_capability_adapter_mappings(
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )

    async def update_mapping(
        self,
        capability_adapter_mapping_id: int,
        *,
        mapping_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        capability_name: str | None = None,
        adapter_contract_version: int | None = None,
        resolved_policy_document: dict[str, Any] | None = None,
        supported_environment_requirements: list[str] | None = None,
        actor_id: int | None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        preview = await self.preview_update(
            capability_adapter_mapping_id,
            mapping_id=mapping_id,
            title=title,
            description=description,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
            capability_name=capability_name,
            adapter_contract_version=adapter_contract_version,
            resolved_policy_document=resolved_policy_document,
            supported_environment_requirements=supported_environment_requirements,
            is_active=is_active,
        )
        normalized = dict(preview["normalized_mapping"])
        try:
            updated = await self.repo.update_capability_adapter_mapping(
                capability_adapter_mapping_id,
                mapping_id=normalized["mapping_id"],
                title=normalized["title"],
                description=normalized.get("description"),
                owner_scope_type=normalized["owner_scope_type"],
                owner_scope_id=normalized["owner_scope_id"],
                capability_name=normalized["capability_name"],
                adapter_contract_version=normalized["adapter_contract_version"],
                resolved_policy_document=normalized["resolved_policy_document"],
                supported_environment_requirements=normalized["supported_environment_requirements"],
                is_active=normalized["is_active"],
                actor_id=actor_id,
            )
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
        if updated is None:
            raise ResourceNotFoundError(
                "mcp_capability_adapter_mapping",
                identifier=str(capability_adapter_mapping_id),
            )
        return updated

    async def delete_capability_adapter_mapping(self, capability_adapter_mapping_id: int) -> bool:
        deleted = await self.repo.delete_capability_adapter_mapping(capability_adapter_mapping_id)
        if not deleted:
            raise ResourceNotFoundError(
                "mcp_capability_adapter_mapping",
                identifier=str(capability_adapter_mapping_id),
            )
        return True

    @staticmethod
    def _normalize_scope(
        *,
        owner_scope_type: str,
        owner_scope_id: int | None,
    ) -> tuple[str, int | None, str]:
        normalized_scope_type = str(owner_scope_type or "").strip().lower()
        if normalized_scope_type not in _SUPPORTED_SCOPE_TYPES:
            raise BadRequestError("owner_scope_type must be one of: global, org, team")
        if normalized_scope_type == "global":
            if owner_scope_id is not None:
                raise BadRequestError("global scope cannot include owner_scope_id")
            return "global", None, "global"
        if owner_scope_id is None:
            raise BadRequestError(f"{normalized_scope_type} scope requires owner_scope_id")
        normalized_scope_id = int(owner_scope_id)
        return normalized_scope_type, normalized_scope_id, f"{normalized_scope_type}:{normalized_scope_id}"

    @staticmethod
    def _normalize_adapter_contract_version(value: int) -> int:
        normalized = int(value)
        if normalized != _SUPPORTED_ADAPTER_CONTRACT_VERSION:
            raise BadRequestError(
                f"adapter_contract_version must be {_SUPPORTED_ADAPTER_CONTRACT_VERSION}"
            )
        return normalized

    @staticmethod
    def _normalize_policy_document(policy_document: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(policy_document, dict):
            raise BadRequestError("resolved_policy_document must be an object")
        normalized = deepcopy(dict(policy_document))
        for key in _LIST_POLICY_KEYS:
            if key not in normalized:
                continue
            normalized[key] = _unique(_as_str_list(normalized.get(key)))
        return normalized

    @staticmethod
    def _normalize_environment_requirements(values: list[str]) -> tuple[list[str], list[str]]:
        normalized = _unique(_as_str_list(values))
        supported: list[str] = []
        warnings: list[str] = []
        for requirement in normalized:
            if requirement in _SUPPORTED_ENVIRONMENT_REQUIREMENTS:
                supported.append(requirement)
            else:
                warnings.append(
                    f"unsupported environment requirement '{requirement}' will be ignored"
                )
        return supported, warnings

    async def _validate_policy_document_against_registry(
        self,
        policy_document: dict[str, Any],
    ) -> dict[str, list[str]]:
        entries = await self.tool_registry.list_entries()
        known_tool_names = {
            str(entry.get("tool_name") or "").strip()
            for entry in entries
            if str(entry.get("tool_name") or "").strip()
        }
        known_module_ids = {
            str(entry.get("module") or "").strip()
            for entry in entries
            if str(entry.get("module") or "").strip()
        }
        module_to_tool_names: dict[str, list[str]] = {}
        for entry in entries:
            module_id = str(entry.get("module") or "").strip()
            tool_name = str(entry.get("tool_name") or "").strip()
            if not module_id or not tool_name:
                continue
            module_to_tool_names.setdefault(module_id, []).append(tool_name)
        for module_row in await self.tool_registry.list_modules():
            module_id = str(module_row.get("module") or "").strip()
            if module_id:
                known_module_ids.add(module_id)

        for key in ("tool_names",):
            for tool_name in _as_str_list(policy_document.get(key)):
                if tool_name not in known_tool_names:
                    raise BadRequestError(f"unknown tool '{tool_name}'")

        for key in ("tool_modules", "module_ids"):
            for module_id in _as_str_list(policy_document.get(key)):
                if module_id not in known_module_ids:
                    raise BadRequestError(f"unknown module '{module_id}'")

        for key in ("allowed_tools", "denied_tools"):
            for tool_ref in _as_str_list(policy_document.get(key)):
                if _looks_like_exact_tool_reference(tool_ref) and tool_ref not in known_tool_names:
                    raise BadRequestError(f"unknown tool '{tool_ref}'")
        return {
            module_id: _unique(tool_names)
            for module_id, tool_names in module_to_tool_names.items()
        }

    @staticmethod
    def _expand_module_policy_effects(
        policy_document: dict[str, Any],
        *,
        module_to_tool_names: dict[str, list[str]],
    ) -> dict[str, Any]:
        expanded = deepcopy(policy_document)
        module_ids = _unique(
            _as_str_list(expanded.get("tool_modules")) + _as_str_list(expanded.get("module_ids"))
        )
        if not module_ids:
            return expanded
        expanded_tool_names = _as_str_list(expanded.get("tool_names"))
        for module_id in module_ids:
            expanded_tool_names.extend(module_to_tool_names.get(module_id, []))
        expanded["tool_names"] = _unique(expanded_tool_names)
        return expanded
