from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
import re
from typing import Any

from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

_FILESYSTEM_CAPABILITIES = frozenset({"filesystem.read", "filesystem.write", "filesystem.delete"})
_SUPPORTED_PATH_ARGUMENT_HINTS = frozenset(
    {"path", "file_path", "target_path", "cwd", "paths", "file_paths", "files[].path"}
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if not isinstance(value, Iterable) or isinstance(value, (bytes, bytearray, dict)):
        return []
    out: list[str] = []
    for entry in value:
        cleaned = str(entry or "").strip()
        if cleaned:
            out.append(cleaned)
    return out


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _normalize_candidate_path(raw_path: str, *, base_path: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base_path / candidate
    return candidate.resolve(strict=False)


def _scope_root_from_scope(scope: dict[str, Any]) -> Path | None:
    workspace_root = str(scope.get("workspace_root") or "").strip()
    if not workspace_root:
        return None
    if str(scope.get("path_scope_mode") or "").strip() == "cwd_descendants":
        cwd = str(scope.get("cwd") or "").strip()
        if not cwd:
            return None
        return Path(cwd).expanduser().resolve(strict=False)
    return Path(workspace_root).expanduser().resolve(strict=False)


def _normalize_allowlist_prefix(raw_value: Any) -> str | None:
    value = str(raw_value or "").strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    value = re.sub(r"/+", "/", value)
    if not value or value.startswith("/") or _WINDOWS_ABSOLUTE_PATH_RE.match(value):
        return None
    parts: list[str] = []
    for part in value.split("/"):
        cleaned = str(part or "").strip()
        if not cleaned or cleaned == ".":
            continue
        if cleaned == "..":
            return None
        parts.append(cleaned)
    if not parts:
        return None
    return "/".join(parts)


def _policy_allowlist_prefixes(effective_policy: dict[str, Any] | None) -> list[str]:
    policy_document = _as_dict((effective_policy or {}).get("policy_document"))
    out: list[str] = []
    seen: set[str] = set()
    for raw_entry in _as_str_list(policy_document.get("path_allowlist_prefixes")):
        normalized = _normalize_allowlist_prefix(raw_entry)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return sorted(out)


def _allowlist_roots(*, workspace_root: Path, allowlist_prefixes: list[str]) -> list[Path]:
    return [(workspace_root / prefix).resolve(strict=False) for prefix in allowlist_prefixes]


def _tool_metadata(tool_def: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(tool_def, dict):
        return {}
    return _as_dict(tool_def.get("metadata"))


def _tool_uses_filesystem(metadata: dict[str, Any]) -> bool:
    explicit = _as_bool(metadata.get("uses_filesystem"))
    if explicit is not None:
        return explicit
    capabilities = {cap for cap in _as_str_list(metadata.get("capabilities")) if cap}
    return any(capability in _FILESYSTEM_CAPABILITIES for capability in capabilities)


def _path_boundable(metadata: dict[str, Any]) -> bool:
    return bool(_as_bool(metadata.get("path_boundable")))


def _path_argument_hints(metadata: dict[str, Any]) -> list[str]:
    return [
        hint
        for hint in _unique(_as_str_list(metadata.get("path_argument_hints")))
        if hint in _SUPPORTED_PATH_ARGUMENT_HINTS
    ]


def _extract_candidate_paths(tool_args: Any, hints: list[str]) -> list[str]:
    if not isinstance(tool_args, dict):
        return []
    out: list[str] = []
    for hint in hints:
        if hint in {"path", "file_path", "target_path", "cwd"}:
            value = str(tool_args.get(hint) or "").strip()
            if value:
                out.append(value)
            continue
        if hint in {"paths", "file_paths"}:
            values = tool_args.get(hint)
            if isinstance(values, list):
                out.extend(str(item or "").strip() for item in values if str(item or "").strip())
            continue
        if hint == "files[].path":
            files = tool_args.get("files")
            if isinstance(files, list):
                out.extend(
                    str(item.get("path") or "").strip()
                    for item in files
                    if isinstance(item, dict) and str(item.get("path") or "").strip()
                )
    return _unique(out)


class McpHubPathEnforcementService:
    """Evaluate path-scoped MCP Hub policy for a concrete tool call."""

    def __init__(self, path_scope_service: McpHubPathScopeService | Any | None = None) -> None:
        self._path_scope_service = path_scope_service or McpHubPathScopeService()

    async def evaluate_tool_call(
        self,
        *,
        effective_policy: dict[str, Any] | None,
        context: Any | None,
        tool_name: str,
        tool_args: Any,
        tool_def: dict[str, Any] | None,
    ) -> dict[str, Any]:
        scope = await self._path_scope_service.resolve_for_context(
            effective_policy=effective_policy,
            context=context,
        )
        result = {
            "enabled": bool(scope.get("enabled")),
            "within_scope": True,
            "reason": None,
            "force_approval": False,
            "normalized_paths": [],
            "scope_payload": None,
        }
        if not result["enabled"]:
            return result

        reason = str(scope.get("reason") or "").strip() or None
        if reason:
            return self._blocked_result(scope=scope, reason=reason)

        metadata = _tool_metadata(tool_def)
        if not _tool_uses_filesystem(metadata):
            return result

        if not _path_boundable(metadata):
            return self._blocked_result(scope=scope, reason="tool_not_path_boundable")

        hints = _path_argument_hints(metadata)
        raw_paths = _extract_candidate_paths(tool_args, hints)
        if not raw_paths:
            return self._blocked_result(scope=scope, reason="path_unresolvable")

        workspace_root_text = str(scope.get("workspace_root") or "").strip()
        scope_root = _scope_root_from_scope(scope)
        if not workspace_root_text or scope_root is None:
            return self._blocked_result(scope=scope, reason="workspace_root_unavailable")
        workspace_root = Path(workspace_root_text).expanduser().resolve(strict=False)
        base_path = Path(str(scope.get("cwd") or workspace_root)).expanduser().resolve(strict=False)
        path_allowlist_prefixes = _policy_allowlist_prefixes(effective_policy)
        allowlist_roots = _allowlist_roots(
            workspace_root=workspace_root,
            allowlist_prefixes=path_allowlist_prefixes,
        )

        normalized_paths: list[str] = []
        for raw_path in raw_paths:
            normalized = _normalize_candidate_path(raw_path, base_path=base_path)
            normalized_paths.append(str(normalized))
            if not _is_within(workspace_root, normalized):
                return self._blocked_result(
                    scope=scope,
                    reason="path_outside_workspace_scope",
                    normalized_paths=normalized_paths,
                )
            if not _is_within(scope_root, normalized):
                return self._blocked_result(
                    scope=scope,
                    reason="path_outside_current_folder_scope",
                    normalized_paths=normalized_paths,
                    path_allowlist_prefixes=path_allowlist_prefixes,
                )
            if allowlist_roots and not any(_is_within(root, normalized) for root in allowlist_roots):
                return self._blocked_result(
                    scope=scope,
                    reason="path_outside_allowlist_scope",
                    normalized_paths=normalized_paths,
                    path_allowlist_prefixes=path_allowlist_prefixes,
                )

        result["normalized_paths"] = normalized_paths
        result["scope_payload"] = self._scope_payload(
            scope=scope,
            normalized_paths=normalized_paths,
            path_allowlist_prefixes=path_allowlist_prefixes,
        )
        return result

    @staticmethod
    def _scope_payload(
        *,
        scope: dict[str, Any],
        normalized_paths: list[str] | None = None,
        reason: str | None = None,
        path_allowlist_prefixes: list[str] | None = None,
    ) -> dict[str, Any]:
        scope_root = _scope_root_from_scope(scope)
        payload = {
            "path_scope_mode": str(scope.get("path_scope_mode") or "none").strip() or "none",
            "workspace_root": str(scope.get("workspace_root") or "").strip() or None,
            "scope_root": str(scope_root) if scope_root is not None else None,
        }
        if normalized_paths:
            payload["normalized_paths"] = list(normalized_paths)
        if path_allowlist_prefixes:
            payload["path_allowlist_prefixes"] = list(path_allowlist_prefixes)
        if reason:
            payload["reason"] = reason
        return {key: value for key, value in payload.items() if value not in (None, "", [])}

    def _blocked_result(
        self,
        *,
        scope: dict[str, Any],
        reason: str,
        normalized_paths: list[str] | None = None,
        path_allowlist_prefixes: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "enabled": bool(scope.get("enabled")),
            "within_scope": False,
            "reason": reason,
            "force_approval": True,
            "normalized_paths": list(normalized_paths or []),
            "scope_payload": self._scope_payload(
                scope=scope,
                normalized_paths=list(normalized_paths or []),
                reason=reason,
                path_allowlist_prefixes=path_allowlist_prefixes,
            ),
        }


async def get_mcp_hub_path_enforcement_service() -> McpHubPathEnforcementService:
    """Create a path enforcement service backed by the current sandbox scope resolver."""
    return McpHubPathEnforcementService()
