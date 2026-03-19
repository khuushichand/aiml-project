from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

_ALLOWED_REF_KINDS = frozenset({"branch", "tag", "commit"})
_SSH_REPO_RE = re.compile(r"^(?:[^@]+@)?(?P<host>[^:]+):(?P<path>.+)$")


def _normalize_string_list(value: Any) -> list[str]:
    """Return a stable, de-duplicated list of non-empty string values."""
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = str(item or "").strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _canonicalize_git_repository(repo_url: str) -> str:
    """Normalize supported Git repository identifiers to host/org/repo form."""
    cleaned = str(repo_url or "").strip()
    if not cleaned:
        raise ValueError("repo_url is required")
    if "://" not in cleaned and "/" in cleaned and ":" not in cleaned.split("/", 1)[0]:
        host, path = cleaned.split("/", 1)
        host = host.strip().lower()
        path = path.strip().strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        if not host or not path:
            raise ValueError("Unsupported git repository format")
        return f"{host}/{path}"
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.split("@")[-1].lower()
        path = parsed.path.strip().strip("/")
    else:
        match = _SSH_REPO_RE.match(cleaned)
        if not match:
            raise ValueError("Unsupported git repository format")
        host = str(match.group("host") or "").strip().lower()
        path = str(match.group("path") or "").strip().strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")
    if not host or not path:
        raise ValueError("Unsupported git repository format")
    return f"{host}/{path}"


def _canonicalize_git_host(repo_url: str) -> str:
    """Extract the canonical Git host name from a repository identifier."""
    return _canonicalize_git_repository(repo_url).split("/", 1)[0]


class McpHubGovernancePackTrustService:
    """Deployment-wide trust-policy storage and evaluation for governance-pack sources."""

    def __init__(self, *, repo: McpHubRepo) -> None:
        self.repo = repo

    @staticmethod
    def _default_policy() -> dict[str, Any]:
        """Return the fail-closed default trust policy."""
        return {
            "allow_local_path_sources": False,
            "allowed_local_roots": [],
            "allow_git_sources": False,
            "allowed_git_hosts": [],
            "allowed_git_repositories": [],
            "allowed_git_ref_kinds": [],
            "require_git_signature_verification": False,
            "trusted_git_key_fingerprints": [],
        }

    def _normalize_policy(self, policy: dict[str, Any] | None) -> dict[str, Any]:
        """Normalize persisted or requested trust-policy content."""
        raw = dict(policy or {})
        ref_kinds = [
            kind
            for kind in (entry.strip().lower() for entry in _normalize_string_list(raw.get("allowed_git_ref_kinds")))
            if kind in _ALLOWED_REF_KINDS
        ]
        return {
            "allow_local_path_sources": bool(raw.get("allow_local_path_sources", False)),
            "allowed_local_roots": [str(Path(entry).resolve()) for entry in _normalize_string_list(raw.get("allowed_local_roots"))],
            "allow_git_sources": bool(raw.get("allow_git_sources", False)),
            "allowed_git_hosts": [entry.lower() for entry in _normalize_string_list(raw.get("allowed_git_hosts"))],
            "allowed_git_repositories": [
                _canonicalize_git_repository(entry) for entry in _normalize_string_list(raw.get("allowed_git_repositories"))
            ],
            "allowed_git_ref_kinds": ref_kinds,
            "require_git_signature_verification": bool(raw.get("require_git_signature_verification", False)),
            "trusted_git_key_fingerprints": _normalize_string_list(raw.get("trusted_git_key_fingerprints")),
        }

    async def get_policy(self) -> dict[str, Any]:
        """Load and normalize the deployment-wide governance-pack trust policy."""
        row = await self.repo.get_governance_pack_trust_policy()
        return self._normalize_policy(row.get("policy_document"))

    async def update_policy(self, policy: dict[str, Any], *, actor_id: int | None) -> dict[str, Any]:
        """Persist a normalized deployment-wide trust policy."""
        normalized = self._normalize_policy(policy)
        await self.repo.upsert_governance_pack_trust_policy(
            policy_document=normalized,
            actor_id=actor_id,
        )
        return normalized

    async def evaluate_local_path(self, path: str) -> dict[str, Any]:
        """Evaluate whether a local filesystem source path is allowed."""
        policy = await self.get_policy()
        resolved_path = str(Path(path).resolve())
        if not policy["allow_local_path_sources"]:
            return {"allowed": False, "reason": "local_path_disabled", "resolved_path": resolved_path}
        allowed_roots = [str(Path(root).resolve()) for root in policy["allowed_local_roots"]]
        for root in allowed_roots:
            if resolved_path == root or resolved_path.startswith(f"{root}{os.sep}"):
                return {"allowed": True, "reason": None, "resolved_path": resolved_path}
        return {"allowed": False, "reason": "path_not_allowed", "resolved_path": resolved_path}

    async def evaluate_git_source(self, repo_url: str, *, ref_kind: str) -> dict[str, Any]:
        """Evaluate whether a Git source is allowed under the current trust policy."""
        policy = await self.get_policy()
        canonical_repository = _canonicalize_git_repository(repo_url)
        host = _canonicalize_git_host(repo_url)
        normalized_ref_kind = str(ref_kind or "").strip().lower()
        if not policy["allow_git_sources"]:
            return {
                "allowed": False,
                "reason": "git_source_disabled",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
            }
        if host not in set(policy["allowed_git_hosts"]):
            return {
                "allowed": False,
                "reason": "host_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
            }
        if canonical_repository not in set(policy["allowed_git_repositories"]):
            return {
                "allowed": False,
                "reason": "repository_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
            }
        if normalized_ref_kind not in set(policy["allowed_git_ref_kinds"]):
            return {
                "allowed": False,
                "reason": "ref_kind_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
            }
        return {
            "allowed": True,
            "reason": None,
            "canonical_repository": canonical_repository,
            "verification_required": bool(policy["require_git_signature_verification"]),
        }
