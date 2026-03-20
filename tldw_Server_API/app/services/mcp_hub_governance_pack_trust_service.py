"""Trust-policy storage and evaluation for governance-pack source resolution."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

_ALLOWED_REF_KINDS = frozenset({"branch", "tag", "commit"})
_ALLOWED_SIGNER_STATUSES = frozenset({"active", "inactive", "revoked"})
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


def _normalize_repo_binding(repo_binding: Any) -> str:
    """Normalize a signer repo binding as an exact canonical repo id or prefix binding."""
    cleaned = str(repo_binding or "").strip()
    if not cleaned:
        raise ValueError("repo binding is required")
    is_prefix = cleaned.endswith("/")
    canonical = _canonicalize_git_repository(cleaned[:-1] if is_prefix else cleaned)
    return f"{canonical}/" if is_prefix else canonical


def _normalize_trusted_signer_entry(
    signer: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize a signer entry into the canonical trust-store representation."""
    fingerprint = str(signer.get("fingerprint") or "").strip().upper()
    if not fingerprint:
        return None
    display_name = str(signer.get("display_name") or "").strip() or None
    repo_bindings: list[str] = []
    seen_bindings: set[str] = set()
    for entry in _normalize_string_list(signer.get("repo_bindings")):
        normalized_binding = _normalize_repo_binding(entry)
        if normalized_binding in seen_bindings:
            continue
        seen_bindings.add(normalized_binding)
        repo_bindings.append(normalized_binding)
    status = str(signer.get("status") or "active").strip().lower()
    if status not in _ALLOWED_SIGNER_STATUSES:
        status = "active"
    return {
        "fingerprint": fingerprint,
        "display_name": display_name,
        "repo_bindings": repo_bindings,
        "status": status,
    }


def _normalize_trusted_signers(
    signers: Any,
    legacy_fingerprints: Any,
) -> list[dict[str, Any]]:
    """Normalize structured and legacy signer inputs into a canonical signer list."""
    normalized: list[dict[str, Any]] = []
    by_fingerprint: dict[str, dict[str, Any]] = {}

    def _merge_signer_entry(entry: dict[str, Any]) -> None:
        fingerprint = str(entry.get("fingerprint") or "").strip().upper()
        if not fingerprint:
            return
        existing = by_fingerprint.get(fingerprint)
        if existing is None:
            canonical = {
                "fingerprint": fingerprint,
                "display_name": entry.get("display_name"),
                "repo_bindings": list(entry.get("repo_bindings") or []),
                "status": str(entry.get("status") or "active").strip().lower() or "active",
            }
            by_fingerprint[fingerprint] = canonical
            normalized.append(canonical)
            return

        if not existing.get("display_name") and entry.get("display_name"):
            existing["display_name"] = entry["display_name"]
        for repo_binding in entry.get("repo_bindings") or []:
            if repo_binding not in existing["repo_bindings"]:
                existing["repo_bindings"].append(repo_binding)
        if str(existing.get("status") or "").strip().lower() != "active":
            status = str(entry.get("status") or "").strip().lower()
            if status == "active":
                existing["status"] = status

    for raw_signer in signers or []:
        if not isinstance(raw_signer, dict):
            continue
        normalized_signer = _normalize_trusted_signer_entry(raw_signer)
        if normalized_signer is not None:
            _merge_signer_entry(normalized_signer)

    for fingerprint in _normalize_string_list(legacy_fingerprints):
        normalized_signer = _normalize_trusted_signer_entry(
            {
                "fingerprint": fingerprint,
                "display_name": None,
                "repo_bindings": [],
                "status": "active",
            }
        )
        if normalized_signer is not None and normalized_signer["fingerprint"] not in by_fingerprint:
            _merge_signer_entry(normalized_signer)

    return normalized


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
            "trusted_signers": [],
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
        trusted_signers = _normalize_trusted_signers(
            raw.get("trusted_signers"),
            raw.get("trusted_git_key_fingerprints"),
        )
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
            "trusted_signers": trusted_signers,
            "trusted_git_key_fingerprints": [signer["fingerprint"] for signer in trusted_signers],
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
                "trusted_git_key_fingerprints": list(policy["trusted_git_key_fingerprints"]),
                "trusted_signers": list(policy["trusted_signers"]),
            }
        if host not in set(policy["allowed_git_hosts"]):
            return {
                "allowed": False,
                "reason": "host_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
                "trusted_git_key_fingerprints": list(policy["trusted_git_key_fingerprints"]),
                "trusted_signers": list(policy["trusted_signers"]),
            }
        if canonical_repository not in set(policy["allowed_git_repositories"]):
            return {
                "allowed": False,
                "reason": "repository_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
                "trusted_git_key_fingerprints": list(policy["trusted_git_key_fingerprints"]),
                "trusted_signers": list(policy["trusted_signers"]),
            }
        if normalized_ref_kind not in set(policy["allowed_git_ref_kinds"]):
            return {
                "allowed": False,
                "reason": "ref_kind_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
                "trusted_git_key_fingerprints": list(policy["trusted_git_key_fingerprints"]),
                "trusted_signers": list(policy["trusted_signers"]),
            }
        return {
            "allowed": True,
            "reason": None,
            "canonical_repository": canonical_repository,
            "verification_required": bool(policy["require_git_signature_verification"]),
            "trusted_git_key_fingerprints": list(policy["trusted_git_key_fingerprints"]),
            "trusted_signers": list(policy["trusted_signers"]),
        }
