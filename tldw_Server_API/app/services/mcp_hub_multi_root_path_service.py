from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any

from tldw_Server_API.app.services.mcp_hub_workspace_root_resolver import (
    McpHubWorkspaceRootResolver,
)

_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _normalize_workspace_root(path_value: str) -> str:
    return str(Path(path_value).expanduser().resolve(strict=False))


def _normalize_candidate_path(raw_path: str, *, base_path: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base_path / candidate
    return candidate.resolve(strict=False)


def _is_absolute_path(raw_path: str) -> bool:
    candidate = Path(str(raw_path or "").strip()).expanduser()
    return candidate.is_absolute() or bool(_WINDOWS_ABSOLUTE_PATH_RE.match(str(raw_path or "").strip()))


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


class McpHubMultiRootPathService:
    """Resolve exact path-to-workspace mappings for narrow multi-root execution."""

    def __init__(self, workspace_root_resolver: McpHubWorkspaceRootResolver | Any | None = None) -> None:
        self._workspace_root_resolver = workspace_root_resolver or McpHubWorkspaceRootResolver()

    async def resolve_path_bundle(
        self,
        *,
        raw_paths: list[str],
        active_workspace_id: str | None,
        active_workspace_root: str | None = None,
        active_base_path: str | None,
        allowed_workspace_ids: list[str],
        workspace_roots_by_id: Mapping[str, str] | None = None,
        user_id: str | None = None,
        workspace_trust_source: str | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_allowed_ids = _unique(list(allowed_workspace_ids or []))
        if not normalized_allowed_ids:
            return {
                "ok": False,
                "reason": "path_outside_workspace_bundle",
                "normalized_paths": [],
                "workspace_bundle_ids": [],
                "workspace_bundle_roots": [],
                "path_workspace_map": {},
            }

        resolved_roots_by_id: dict[str, str] = {}
        for workspace_id, root_value in dict(workspace_roots_by_id or {}).items():
            workspace_key = str(workspace_id or "").strip()
            root_text = str(root_value or "").strip()
            if not workspace_key or not root_text:
                continue
            resolved_roots_by_id[workspace_key] = _normalize_workspace_root(root_text)

        active_workspace_key = str(active_workspace_id or "").strip() or None
        if active_workspace_key and str(active_workspace_root or "").strip():
            resolved_roots_by_id[active_workspace_key] = _normalize_workspace_root(str(active_workspace_root or ""))

        for workspace_id in normalized_allowed_ids:
            if workspace_id in resolved_roots_by_id:
                continue
            resolution = await self._workspace_root_resolver.resolve_for_context(
                session_id=None,
                user_id=user_id,
                workspace_id=workspace_id,
                workspace_trust_source=workspace_trust_source,
                owner_scope_type=owner_scope_type,
                owner_scope_id=owner_scope_id,
            )
            workspace_root = str(resolution.get("workspace_root") or "").strip()
            if workspace_root:
                resolved_roots_by_id[workspace_id] = _normalize_workspace_root(workspace_root)

        base_text = str(active_base_path or active_workspace_root or "").strip()
        if not base_text:
            return {
                "ok": False,
                "reason": "workspace_root_unavailable",
                "normalized_paths": [],
                "workspace_bundle_ids": [],
                "workspace_bundle_roots": [],
                "path_workspace_map": {},
            }
        base_path = Path(base_text).expanduser().resolve(strict=False)

        normalized_paths: list[str] = []
        path_workspace_map: dict[str, str] = {}
        matched_workspace_ids: list[str] = []

        for raw_path in _unique(list(raw_paths or [])):
            normalized = _normalize_candidate_path(raw_path, base_path=base_path)
            normalized_text = str(normalized)
            normalized_paths.append(normalized_text)

            candidate_matches: list[str] = []
            if _is_absolute_path(raw_path):
                candidate_matches = [
                    workspace_id
                    for workspace_id in normalized_allowed_ids
                    if workspace_id in resolved_roots_by_id
                    and _is_within(
                        Path(resolved_roots_by_id[workspace_id]).expanduser().resolve(strict=False),
                        normalized,
                    )
                ]
            else:
                if active_workspace_key and active_workspace_key in resolved_roots_by_id:
                    candidate_matches = [active_workspace_key]

            if not candidate_matches:
                return {
                    "ok": False,
                    "reason": "path_outside_workspace_bundle",
                    "normalized_paths": normalized_paths,
                    "workspace_bundle_ids": sorted(_unique(matched_workspace_ids)),
                    "workspace_bundle_roots": [
                        resolved_roots_by_id[workspace_id]
                        for workspace_id in sorted(_unique(matched_workspace_ids))
                        if workspace_id in resolved_roots_by_id
                    ],
                    "path_workspace_map": dict(path_workspace_map),
                }

            if len(candidate_matches) > 1:
                return {
                    "ok": False,
                    "reason": "path_matches_multiple_workspace_roots",
                    "normalized_paths": normalized_paths,
                    "workspace_bundle_ids": sorted(_unique(candidate_matches)),
                    "workspace_bundle_roots": [
                        resolved_roots_by_id[workspace_id]
                        for workspace_id in sorted(_unique(candidate_matches))
                        if workspace_id in resolved_roots_by_id
                    ],
                    "path_workspace_map": dict(path_workspace_map),
                }

            matched_workspace_id = candidate_matches[0]
            path_workspace_map[normalized_text] = matched_workspace_id
            matched_workspace_ids.append(matched_workspace_id)

        unique_bundle_ids = sorted(_unique(matched_workspace_ids))
        return {
            "ok": True,
            "reason": None,
            "normalized_paths": normalized_paths,
            "workspace_bundle_ids": unique_bundle_ids,
            "workspace_bundle_roots": [
                resolved_roots_by_id[workspace_id]
                for workspace_id in unique_bundle_ids
                if workspace_id in resolved_roots_by_id
            ],
            "path_workspace_map": dict(path_workspace_map),
            "resolved_workspace_roots_by_id": dict(resolved_roots_by_id),
        }
