"""Trust-policy storage and evaluation for governance-pack source resolution."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

_ALLOWED_REF_KINDS = frozenset({"branch", "tag", "commit"})
_ALLOWED_SIGNER_STATUSES = frozenset({"active", "inactive", "revoked"})
_SSH_REPO_RE = re.compile(r"^(?:[^@]+@)?(?P<host>[^:]+):(?P<path>.+)$")


class GovernancePackTrustPolicyStaleError(ValueError):
    """Raised when a trust-policy update uses a stale fingerprint."""


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


def _normalize_required_string_list(value: Any, *, field_name: str) -> list[str]:
    """Normalize a string collection while rejecting whitespace-only entries."""
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
            raise ValueError(f"{field_name} entries cannot be blank")
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


def _normalize_signer_status(raw_status: Any) -> str:
    """Normalize a signer status or reject invalid values."""
    status = str(raw_status or "active").strip().lower()
    if status not in _ALLOWED_SIGNER_STATUSES:
        raise ValueError(f"invalid signer status: {raw_status}")
    return status


def _normalize_trusted_signer_entry(
    signer: dict[str, Any],
    *,
    default_repo_bindings: list[str] | None = None,
) -> dict[str, Any] | None:
    """Normalize a signer entry into the canonical trust-store representation."""
    fingerprint = str(signer.get("fingerprint") or "").strip().upper()
    if not fingerprint:
        raise ValueError("fingerprint is required")
    display_name = str(signer.get("display_name") or "").strip() or None
    repo_bindings: list[str] = []
    seen_bindings: set[str] = set()
    for entry in _normalize_required_string_list(signer.get("repo_bindings"), field_name="repo binding"):
        normalized_binding = _normalize_repo_binding(entry)
        if normalized_binding in seen_bindings:
            continue
        seen_bindings.add(normalized_binding)
        repo_bindings.append(normalized_binding)
    if not repo_bindings:
        repo_bindings = list(default_repo_bindings or [])
    if not repo_bindings:
        raise ValueError("trusted signer repo_bindings must not be empty")
    return {
        "fingerprint": fingerprint,
        "display_name": display_name,
        "repo_bindings": repo_bindings,
        "status": _normalize_signer_status(signer.get("status")),
    }


def _normalize_trusted_signers(
    signers: Any,
    legacy_fingerprints: Any,
    *,
    default_repo_bindings: list[str],
    allow_empty_structured_bindings: bool = False,
) -> list[dict[str, Any]]:
    """Normalize structured and legacy signer inputs into a canonical signer list."""
    normalized: list[dict[str, Any]] = []
    by_fingerprint: dict[str, dict[str, Any]] = {}

    def _merge_signer_entry(entry: dict[str, Any]) -> None:
        fingerprint = str(entry.get("fingerprint") or "").strip().upper()
        if not fingerprint:
            return
        if fingerprint in by_fingerprint:
            raise ValueError(f"duplicate trusted signer fingerprint: {fingerprint}")
        canonical = {
            "fingerprint": fingerprint,
            "display_name": entry.get("display_name"),
            "repo_bindings": list(entry.get("repo_bindings") or []),
            "status": _normalize_signer_status(entry.get("status")),
        }
        by_fingerprint[fingerprint] = canonical
        normalized.append(canonical)

    for raw_signer in signers or []:
        if not isinstance(raw_signer, dict):
            continue
        normalized_signer = _normalize_trusted_signer_entry(
            raw_signer,
            default_repo_bindings=default_repo_bindings if allow_empty_structured_bindings else None,
        )
        if normalized_signer is not None:
            _merge_signer_entry(normalized_signer)

    for fingerprint in _normalize_required_string_list(legacy_fingerprints, field_name="fingerprint"):
        normalized_signer = _normalize_trusted_signer_entry(
            {
                "fingerprint": fingerprint,
                "display_name": None,
                "repo_bindings": list(default_repo_bindings),
                "status": "active",
            },
            default_repo_bindings=default_repo_bindings,
        )
        if normalized_signer is not None and normalized_signer["fingerprint"] not in by_fingerprint:
            _merge_signer_entry(normalized_signer)

    return normalized


def _repo_binding_matches(canonical_repository: str, repo_binding: str) -> bool:
    """Return whether a canonical repository matches an exact or prefix repo binding."""
    binding = str(repo_binding or "").strip()
    if not binding:
        return False
    if binding.endswith("/"):
        return canonical_repository.startswith(binding)
    return canonical_repository == binding


def _match_trusted_signers_for_repository(
    trusted_signers: list[dict[str, Any]],
    canonical_repository: str,
) -> list[dict[str, Any]]:
    """Filter active trusted signers by canonical repository bindings."""
    matched: list[dict[str, Any]] = []
    for signer in trusted_signers:
        if str(signer.get("status") or "").strip().lower() != "active":
            continue
        repo_bindings = list(signer.get("repo_bindings") or [])
        if any(
            _repo_binding_matches(canonical_repository, binding)
            for binding in repo_bindings
        ):
            matched.append(dict(signer))
    return matched


def _stable_policy_fingerprint(policy: dict[str, Any]) -> str:
    """Build a deterministic trust-policy fingerprint from the normalized policy document."""
    encoded = json.dumps(policy, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
        }

    def _normalize_policy(self, policy: dict[str, Any] | None, *, for_write: bool) -> dict[str, Any]:
        """Normalize persisted or requested trust-policy content."""
        raw = dict(policy or {})
        ref_kinds = [
            kind
            for kind in (entry.strip().lower() for entry in _normalize_string_list(raw.get("allowed_git_ref_kinds")))
            if kind in _ALLOWED_REF_KINDS
        ]
        allowed_git_repositories = [
            _canonicalize_git_repository(entry) for entry in _normalize_string_list(raw.get("allowed_git_repositories"))
        ]
        trusted_signers = _normalize_trusted_signers(
            raw.get("trusted_signers"),
            raw.get("trusted_git_key_fingerprints"),
            default_repo_bindings=allowed_git_repositories,
            allow_empty_structured_bindings=not for_write,
        )
        return {
            "allow_local_path_sources": bool(raw.get("allow_local_path_sources", False)),
            "allowed_local_roots": [str(Path(entry).resolve()) for entry in _normalize_string_list(raw.get("allowed_local_roots"))],
            "allow_git_sources": bool(raw.get("allow_git_sources", False)),
            "allowed_git_hosts": [entry.lower() for entry in _normalize_string_list(raw.get("allowed_git_hosts"))],
            "allowed_git_repositories": allowed_git_repositories,
            "allowed_git_ref_kinds": ref_kinds,
            "require_git_signature_verification": bool(raw.get("require_git_signature_verification", False)),
            "trusted_signers": trusted_signers,
        }

    async def get_policy(self) -> dict[str, Any]:
        """Load and normalize the deployment-wide governance-pack trust policy."""
        row = await self.repo.get_governance_pack_trust_policy()
        try:
            policy = self._normalize_policy(row.get("policy_document"), for_write=False)
            policy["policy_fingerprint"] = _stable_policy_fingerprint(policy)
            return policy
        except ValueError as exc:
            raise ValueError(f"invalid persisted governance pack trust policy: {exc}") from exc

    async def update_policy(self, policy: dict[str, Any], *, actor_id: int | None) -> dict[str, Any]:
        """Persist a normalized deployment-wide trust policy."""
        requested_fingerprint = str(policy.get("policy_fingerprint") or "").strip()
        if not requested_fingerprint:
            raise GovernancePackTrustPolicyStaleError("policy_fingerprint is required for trust policy updates")
        current_policy = await self.get_policy()
        current_fingerprint = str(current_policy.get("policy_fingerprint") or "").strip()
        if current_fingerprint and requested_fingerprint != current_fingerprint:
            raise GovernancePackTrustPolicyStaleError("stale governance pack trust policy write")
        normalized = self._normalize_policy(policy, for_write=True)
        response_payload = dict(normalized)
        response_payload["policy_fingerprint"] = _stable_policy_fingerprint(normalized)
        await self.repo.upsert_governance_pack_trust_policy(
            policy_document=normalized,
            actor_id=actor_id,
        )
        return response_payload

    async def evaluate_local_path(self, path: str) -> dict[str, Any]:
        """Evaluate whether a local filesystem source path is allowed."""
        resolved_path = str(Path(path).resolve())
        try:
            policy = await self.get_policy()
        except ValueError:
            return {"allowed": False, "reason": "invalid_trust_policy", "resolved_path": resolved_path}
        if not policy["allow_local_path_sources"]:
            return {"allowed": False, "reason": "local_path_disabled", "resolved_path": resolved_path}
        allowed_roots = [str(Path(root).resolve()) for root in policy["allowed_local_roots"]]
        for root in allowed_roots:
            if resolved_path == root or resolved_path.startswith(f"{root}{os.sep}"):
                return {"allowed": True, "reason": None, "resolved_path": resolved_path}
        return {"allowed": False, "reason": "path_not_allowed", "resolved_path": resolved_path}

    async def evaluate_git_source(self, repo_url: str, *, ref_kind: str) -> dict[str, Any]:
        """Evaluate whether a Git source is allowed under the current trust policy."""
        canonical_repository = _canonicalize_git_repository(repo_url)
        host = _canonicalize_git_host(repo_url)
        normalized_ref_kind = str(ref_kind or "").strip().lower()
        try:
            policy = await self.get_policy()
        except ValueError:
            return {
                "allowed": False,
                "reason": "invalid_trust_policy",
                "canonical_repository": canonical_repository,
                "verification_required": False,
                "trusted_git_key_fingerprints": [],
                "trusted_signers": [],
            }
        matched_signers = _match_trusted_signers_for_repository(
            list(policy.get("trusted_signers") or []),
            canonical_repository,
        )
        matched_fingerprints = [signer["fingerprint"] for signer in matched_signers]
        if not policy["allow_git_sources"]:
            return {
                "allowed": False,
                "reason": "git_source_disabled",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
                "trusted_git_key_fingerprints": matched_fingerprints,
                "trusted_signers": matched_signers,
            }
        if host not in set(policy["allowed_git_hosts"]):
            return {
                "allowed": False,
                "reason": "host_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
                "trusted_git_key_fingerprints": matched_fingerprints,
                "trusted_signers": matched_signers,
            }
        if canonical_repository not in set(policy["allowed_git_repositories"]):
            return {
                "allowed": False,
                "reason": "repository_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
                "trusted_git_key_fingerprints": matched_fingerprints,
                "trusted_signers": matched_signers,
            }
        if normalized_ref_kind not in set(policy["allowed_git_ref_kinds"]):
            return {
                "allowed": False,
                "reason": "ref_kind_not_allowed",
                "canonical_repository": canonical_repository,
                "verification_required": bool(policy["require_git_signature_verification"]),
                "trusted_git_key_fingerprints": matched_fingerprints,
                "trusted_signers": matched_signers,
            }
        return {
            "allowed": True,
            "reason": None,
            "canonical_repository": canonical_repository,
            "verification_required": bool(policy["require_git_signature_verification"]),
            "trusted_git_key_fingerprints": matched_fingerprints,
            "trusted_signers": matched_signers,
        }

    async def evaluate_signer_for_repository(
        self,
        signer_fingerprint: str,
        repo_url: str,
    ) -> dict[str, Any]:
        """Evaluate a signer against the current deployment trust policy for a repository."""
        canonical_repository = _canonicalize_git_repository(repo_url)
        canonical_fingerprint = str(signer_fingerprint or "").strip().upper()
        try:
            policy = await self.get_policy()
        except ValueError:
            return {
                "allowed": False,
                "reason": "invalid_trust_policy",
                "result_code": "signer_not_allowed_for_repo",
                "canonical_repository": canonical_repository,
                "signer_fingerprint": canonical_fingerprint,
            }

        trusted_signers = list(policy.get("trusted_signers") or [])
        signer = next(
            (
                dict(entry)
                for entry in trusted_signers
                if str(entry.get("fingerprint") or "").strip().upper() == canonical_fingerprint
            ),
            None,
        )
        if signer is None:
            return {
                "allowed": False,
                "reason": "signer_not_allowed_for_repo",
                "result_code": "signer_not_allowed_for_repo",
                "canonical_repository": canonical_repository,
                "signer_fingerprint": canonical_fingerprint,
            }
        if str(signer.get("status") or "").strip().lower() == "revoked":
            return {
                "allowed": False,
                "reason": "signer_revoked",
                "result_code": "signer_revoked",
                "canonical_repository": canonical_repository,
                "signer_fingerprint": canonical_fingerprint,
            }
        if str(signer.get("status") or "").strip().lower() != "active":
            return {
                "allowed": False,
                "reason": "signer_not_allowed_for_repo",
                "result_code": "signer_not_allowed_for_repo",
                "canonical_repository": canonical_repository,
                "signer_fingerprint": canonical_fingerprint,
            }
        if any(_repo_binding_matches(canonical_repository, binding) for binding in signer.get("repo_bindings") or []):
            return {
                "allowed": True,
                "reason": None,
                "result_code": "signer_trusted_for_repo",
                "canonical_repository": canonical_repository,
                "signer_fingerprint": canonical_fingerprint,
                "signer_display_name": signer.get("display_name"),
            }
        return {
            "allowed": False,
            "reason": "signer_not_allowed_for_repo",
            "result_code": "signer_not_allowed_for_repo",
            "canonical_repository": canonical_repository,
            "signer_fingerprint": canonical_fingerprint,
        }
