from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess  # nosec B404
import tempfile
from typing import Any
from urllib.parse import urlparse

from tldw_Server_API.app.core.MCP_unified.governance_packs import (
    GovernancePack,
    load_governance_pack_directory,
    normalize_governance_pack,
)

_VALIDSIG_RE = re.compile(r"\bVALIDSIG\s+([0-9A-Fa-f]+)\b")


def _canonical_json(value: Any) -> str:
    """Serialize pack content deterministically for digest generation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _git_executable() -> str:
    """Resolve the Git executable path required for local source operations."""
    resolved = shutil.which("git")
    if not resolved:
        raise ValueError("git executable is required to resolve governance-pack Git sources")
    return resolved


def _pack_content_digest(pack: GovernancePack) -> str:
    """Compute a stable digest for normalized governance-pack content."""
    normalized = normalize_governance_pack(pack).to_dict()
    return hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()


def _normalize_git_subpath(subpath: str | None) -> str | None:
    """Normalize a requested Git pack subpath and reject traversal."""
    raw = str(subpath or "").strip().replace("\\", "/")
    if not raw:
        return None
    candidate = PurePosixPath(raw.strip("/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Git source subpath must stay within the repository root")
    normalized = candidate.as_posix()
    return normalized or None


def _normalize_git_ref(ref: str | None) -> str | None:
    """Normalize a Git ref while rejecting option-like values."""
    cleaned = str(ref or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith("-"):
        raise ValueError("Git source refs must not start with '-'")
    return cleaned


def _reject_git_url_credentials(repo_url: str) -> None:
    """Reject Git transport URLs that embed user credentials."""
    cleaned = str(repo_url or "").strip()
    if not cleaned:
        raise ValueError("repo_url is required")
    if "://" not in cleaned:
        return
    parsed = urlparse(cleaned)
    if parsed.username or parsed.password:
        raise ValueError("Git source URLs must not embed credentials")


def _resolve_pack_root(root: Path, subpath: str | None) -> Path:
    """Resolve the pack directory within a checkout while rejecting escapes."""
    root = root.resolve()
    if not subpath:
        return root
    candidate = (root / subpath).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Git source subpath must stay within the repository root") from exc
    return candidate


def _normalize_fingerprints(values: list[str] | tuple[str, ...] | set[str]) -> set[str]:
    """Normalize configured signer fingerprints for comparison."""
    normalized: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip().upper()
        if cleaned:
            normalized.add(cleaned)
    return normalized


def _verified_signature_fingerprints(output: str) -> set[str]:
    """Extract trusted signer fingerprints from raw Git verification output."""
    return {match.upper() for match in _VALIDSIG_RE.findall(output or "")}


class McpHubGovernancePackDistributionService:
    """Resolve governance packs from trusted local-path and Git sources."""

    def __init__(self, *, trust_service: Any) -> None:
        self.trust_service = trust_service

    async def _checkout_git_source(
        self,
        *,
        repo_url: str,
        ref: str | None,
        ref_kind: str,
        checkout_root: Path,
    ) -> str:
        """Clone and check out a trusted Git source, returning the resolved commit."""
        subprocess.run(  # nosec B603
            [_git_executable(), "clone", str(repo_url), str(checkout_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        if ref:
            target = str(ref).strip()
            if ref_kind == "tag":
                target = f"refs/tags/{target}"
            elif ref_kind == "branch":
                target = f"origin/{target}"
            subprocess.run(  # nosec B603
                [_git_executable(), "-C", str(checkout_root), "checkout", "--detach", target],
                check=True,
                capture_output=True,
                text=True,
            )
        commit = subprocess.run(  # nosec B603
            [_git_executable(), "-C", str(checkout_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return commit

    async def _verify_git_revision(
        self,
        *,
        checkout_root: Path,
        ref: str | None,
        ref_kind: str,
        commit: str,
        trusted_git_key_fingerprints: list[str] | None = None,
    ) -> bool:
        """Verify the checked-out Git revision and optionally enforce trusted fingerprints."""
        command = [_git_executable(), "-C", str(checkout_root)]
        if ref_kind == "tag" and ref:
            command.extend(["verify-tag", "--raw", "--", str(ref).strip()])
        else:
            command.extend(["verify-commit", "--raw", "--", commit])
        completed = subprocess.run(  # nosec B603
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return False
        trusted_fingerprints = _normalize_fingerprints(trusted_git_key_fingerprints or [])
        if not trusted_fingerprints:
            return True
        observed = _verified_signature_fingerprints(
            "\n".join(
                part
                for part in (
                    str(completed.stdout or ""),
                    str(completed.stderr or ""),
                )
                if part
            )
        )
        return bool(observed & trusted_fingerprints)

    async def resolve_local_path(self, path: str) -> GovernancePack:
        """Resolve a governance pack from a trusted local filesystem path."""
        decision = await self.trust_service.evaluate_local_path(path)
        if not bool(decision.get("allowed")):
            raise ValueError(str(decision.get("reason") or "local_path_not_allowed"))
        resolved_path = Path(str(decision.get("resolved_path") or path))
        pack = load_governance_pack_directory(
            resolved_path,
            source_type="local_path",
            source_location=str(resolved_path.resolve()),
        )
        pack.pack_content_digest = _pack_content_digest(pack)
        return pack

    async def resolve_git_source(
        self,
        repo_url: str,
        *,
        ref: str | None,
        ref_kind: str,
        subpath: str | None,
    ) -> GovernancePack:
        """Resolve a governance pack from a trusted Git source and pinned revision."""
        _reject_git_url_credentials(repo_url)
        normalized_subpath = _normalize_git_subpath(subpath)
        normalized_ref = _normalize_git_ref(ref)
        decision = await self.trust_service.evaluate_git_source(repo_url, ref_kind=ref_kind)
        if not bool(decision.get("allowed")):
            raise ValueError(str(decision.get("reason") or "git_source_not_allowed"))

        verification_required = bool(decision.get("verification_required"))
        trusted_fingerprints = list(decision.get("trusted_git_key_fingerprints") or [])
        with tempfile.TemporaryDirectory(prefix="tldw_governance_pack_git_") as tmp_dir:
            checkout_root = Path(tmp_dir) / "checkout"
            commit = await self._checkout_git_source(
                repo_url=repo_url,
                ref=normalized_ref,
                ref_kind=ref_kind,
                checkout_root=checkout_root,
            )
            verified: bool | None = None
            if verification_required:
                verified = await self._verify_git_revision(
                    checkout_root=checkout_root,
                    ref=normalized_ref,
                    ref_kind=ref_kind,
                    commit=commit,
                    trusted_git_key_fingerprints=trusted_fingerprints,
                )
                if not verified:
                    raise ValueError("Git source verification failed")
            pack_root = _resolve_pack_root(checkout_root, normalized_subpath)
            pack = load_governance_pack_directory(
                pack_root,
                source_type="git",
                source_location=str(
                    decision.get("canonical_repository") or str(repo_url).strip()
                ),
                source_ref_requested=normalized_ref,
                source_subpath=normalized_subpath,
                source_commit_resolved=commit,
                source_verified=verified,
                source_verification_mode="git_signature" if verification_required else None,
            )
            pack.source_path = None
            pack.pack_content_digest = _pack_content_digest(pack)
            return pack
