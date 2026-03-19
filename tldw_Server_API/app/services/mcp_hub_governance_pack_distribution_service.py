from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess  # nosec B404
from typing import Any
from urllib.parse import urlparse
import tempfile

from packaging.version import InvalidVersion, Version

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
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


def _manifest_summary(pack: GovernancePack) -> dict[str, Any]:
    """Return a stable manifest payload for governance-pack API responses."""
    return pack.manifest.model_dump(exclude_none=True)


class McpHubGovernancePackDistributionService:
    """Resolve governance packs from trusted local-path and Git sources."""

    def __init__(self, *, trust_service: Any, repo: McpHubRepo | None = None) -> None:
        self.trust_service = trust_service
        self.repo = repo

    def _require_repo(self) -> McpHubRepo:
        if self.repo is None:
            raise ValueError("governance-pack source candidate storage is unavailable")
        return self.repo

    @staticmethod
    def _candidate_ref_kind(candidate: dict[str, Any]) -> str:
        source_ref_kind = str(candidate.get("source_ref_kind") or "").strip().lower()
        if source_ref_kind:
            return source_ref_kind
        source_ref_requested = str(candidate.get("source_ref_requested") or "").strip()
        source_commit_resolved = str(candidate.get("source_commit_resolved") or "").strip()
        if source_ref_requested and source_ref_requested == source_commit_resolved:
            return "commit"
        return "branch"

    @staticmethod
    def _pack_document(pack: GovernancePack) -> dict[str, Any]:
        return {
            "manifest": pack.manifest.model_dump(exclude_none=True),
            "profiles": [dict(item) for item in pack.raw_profiles],
            "approvals": [dict(item) for item in pack.raw_approvals],
            "personas": [dict(item) for item in pack.raw_personas],
            "assignments": [dict(item) for item in pack.raw_assignments],
        }

    async def _persist_prepared_candidate(
        self,
        *,
        pack: GovernancePack,
        actor_id: int | None,
    ) -> dict[str, Any]:
        repo = self._require_repo()
        candidate = await repo.create_governance_pack_source_candidate(
            source_type=pack.source_type,
            source_location=str(pack.source_location or "").strip(),
            source_ref_requested=pack.source_ref_requested,
            source_ref_kind=pack.source_ref_kind,
            source_subpath=pack.source_subpath,
            source_commit_resolved=pack.source_commit_resolved,
            pack_content_digest=str(pack.pack_content_digest or "").strip(),
            pack_document=self._pack_document(pack),
            source_verified=pack.source_verified,
            source_verification_mode=pack.source_verification_mode,
            fetched_by=actor_id,
        )
        if not candidate:
            raise ValueError("Failed to persist governance-pack source candidate")
        return {
            "candidate": candidate,
            "manifest": _manifest_summary(pack),
        }

    async def _reauthorize_prepared_candidate(
        self,
        *,
        candidate: dict[str, Any],
        actor_id: int | None,
        revalidate_trust: bool,
    ) -> None:
        if actor_id is not None:
            fetched_by = candidate.get("fetched_by")
            if fetched_by is not None and int(fetched_by) != int(actor_id):
                raise ValueError("Prepared governance-pack source candidate belongs to a different actor")
        if not revalidate_trust:
            return

        source_type = str(candidate.get("source_type") or "").strip().lower()
        if source_type == "local_path":
            decision = await self.trust_service.evaluate_local_path(str(candidate.get("source_location") or ""))
            if not bool(decision.get("allowed")):
                raise ValueError("Prepared governance-pack source candidate no longer satisfies trust policy")
            return
        if source_type != "git":
            raise ValueError("Unsupported governance-pack source type")

        source_location = str(candidate.get("source_location") or "").strip()
        ref_kind = self._candidate_ref_kind(candidate)
        decision = await self.trust_service.evaluate_git_source(source_location, ref_kind=ref_kind)
        if not bool(decision.get("allowed")):
            raise ValueError("Prepared governance-pack source candidate no longer satisfies trust policy")
        if not bool(decision.get("verification_required")):
            return

        resolved_commit = str(candidate.get("source_commit_resolved") or "").strip()
        if not resolved_commit:
            raise ValueError("Prepared governance-pack source candidate lacks a pinned Git commit")
        trusted_fingerprints = list(decision.get("trusted_git_key_fingerprints") or [])
        with tempfile.TemporaryDirectory(prefix="tldw_governance_pack_git_verify_") as tmp_dir:
            checkout_root = Path(tmp_dir) / "checkout"
            commit = await self._checkout_git_source(
                repo_url=source_location,
                ref=resolved_commit,
                ref_kind="commit",
                checkout_root=checkout_root,
            )
            verified = await self._verify_git_revision(
                checkout_root=checkout_root,
                ref=resolved_commit,
                ref_kind="commit",
                commit=commit,
                trusted_git_key_fingerprints=trusted_fingerprints,
            )
            if not verified:
                raise ValueError("Prepared governance-pack source candidate no longer satisfies Git verification requirements")

    async def _resolve_update_candidate(self, governance_pack_id: int) -> dict[str, Any]:
        repo = self._require_repo()
        installed = await repo.get_governance_pack(int(governance_pack_id))
        if not installed:
            raise ValueError("Installed governance pack was not found")
        if str(installed.get("source_type") or "").strip().lower() != "git":
            raise ValueError("Update checks are only supported for Git-backed governance packs")

        source_location = str(installed.get("source_location") or "").strip()
        source_ref_requested = str(installed.get("source_ref_requested") or "").strip()
        source_ref_kind = str(installed.get("source_ref_kind") or "").strip().lower() or None
        source_subpath = str(installed.get("source_subpath") or "").strip() or None
        source_commit_resolved = str(installed.get("source_commit_resolved") or "").strip()
        installed_manifest = dict(installed.get("manifest") or {})
        if not source_location:
            raise ValueError("Installed governance pack does not record a Git source")

        if not source_ref_requested or source_ref_requested == source_commit_resolved:
            return {
                "governance_pack_id": int(governance_pack_id),
                "status": "no_update",
                "installed_manifest": installed_manifest,
                "candidate_manifest": None,
                "candidate_pack": None,
                "source_request": None,
                "source_commit_resolved": source_commit_resolved or None,
                "pack_content_digest": installed.get("pack_content_digest"),
            }

        candidate_pack: GovernancePack | None = None
        candidate_ref_kind: str | None = None
        last_error: Exception | None = None
        ref_kinds = (source_ref_kind,) if source_ref_kind else ("branch", "tag")
        for ref_kind in ref_kinds:
            if ref_kind is None:
                continue
            try:
                candidate_pack = await self.resolve_git_source(
                    source_location,
                    ref=source_ref_requested,
                    ref_kind=ref_kind,
                    subpath=source_subpath,
                )
                candidate_ref_kind = ref_kind
                break
            except (ValueError, subprocess.CalledProcessError) as exc:
                last_error = exc
        if candidate_pack is None:
            raise ValueError(
                f"Unable to resolve governance-pack source update: {last_error}"
            ) from last_error
        if candidate_pack.manifest.pack_id != str(installed.get("pack_id") or "").strip():
            raise ValueError("Resolved governance-pack update candidate pack_id does not match installed pack")

        try:
            installed_version = Version(str(installed.get("pack_version") or "").strip())
            candidate_version = Version(candidate_pack.manifest.pack_version)
        except InvalidVersion as exc:
            raise ValueError("Governance-pack update version is not valid semantic versioning") from exc

        status = "no_update"
        if candidate_version > installed_version:
            status = "newer_version_available"
        elif candidate_version == installed_version:
            if (
                str(candidate_pack.pack_content_digest or "").strip()
                != str(installed.get("pack_content_digest") or "").strip()
                or str(candidate_pack.source_commit_resolved or "").strip()
                != source_commit_resolved
            ):
                status = "source_drift_same_version"

        return {
            "governance_pack_id": int(governance_pack_id),
            "status": status,
            "installed_manifest": installed_manifest,
            "candidate_manifest": _manifest_summary(candidate_pack),
            "candidate_pack": candidate_pack,
            "source_request": {
                "source_type": "git",
                "repo_url": source_location,
                "ref": source_ref_requested,
                "ref_kind": candidate_ref_kind,
                "subpath": source_subpath,
            },
            "source_commit_resolved": candidate_pack.source_commit_resolved,
            "pack_content_digest": candidate_pack.pack_content_digest,
        }

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
                source_location=str(repo_url).strip(),
                source_ref_requested=normalized_ref,
                source_ref_kind=ref_kind,
                source_subpath=normalized_subpath,
                source_commit_resolved=commit,
                source_verified=verified,
                source_verification_mode="git_signature" if verification_required else None,
            )
            pack.source_path = None
            pack.pack_content_digest = _pack_content_digest(pack)
            return pack

    async def prepare_source_candidate(
        self,
        *,
        source: dict[str, Any],
        actor_id: int | None,
    ) -> dict[str, Any]:
        self._require_repo()
        source_type = str(source.get("source_type") or "").strip().lower()
        if source_type == "local_path":
            path = str(source.get("local_path") or source.get("source_location") or "").strip()
            if not path:
                raise ValueError("local_path is required for local-path governance-pack sources")
            pack = await self.resolve_local_path(path)
        elif source_type == "git":
            repo_url = str(source.get("repo_url") or source.get("source_location") or "").strip()
            ref_kind = str(source.get("ref_kind") or "").strip().lower()
            if not repo_url:
                raise ValueError("repo_url is required for Git governance-pack sources")
            if not ref_kind:
                raise ValueError("ref_kind is required for Git governance-pack sources")
            pack = await self.resolve_git_source(
                repo_url,
                ref=str(source.get("ref") or "").strip() or None,
                ref_kind=ref_kind,
                subpath=str(source.get("subpath") or "").strip() or None,
            )
        else:
            raise ValueError("Unsupported governance-pack source type")
        return await self._persist_prepared_candidate(pack=pack, actor_id=actor_id)

    async def load_prepared_candidate(
        self,
        candidate_id: int,
        *,
        actor_id: int | None = None,
        revalidate_trust: bool = False,
    ) -> dict[str, Any]:
        repo = self._require_repo()
        candidate = await repo.get_governance_pack_source_candidate(int(candidate_id))
        if not candidate:
            raise ValueError("Prepared governance-pack source candidate was not found")
        await self._reauthorize_prepared_candidate(
            candidate=candidate,
            actor_id=actor_id,
            revalidate_trust=revalidate_trust,
        )
        pack_document = candidate.get("pack_document")
        if not isinstance(pack_document, dict):
            raise ValueError("Prepared governance-pack source candidate is invalid")
        return {
            "candidate": candidate,
            "pack_document": pack_document,
        }

    async def check_for_updates(self, governance_pack_id: int) -> dict[str, Any]:
        """Check whether a Git-backed governance-pack install has a newer trusted candidate."""
        update = await self._resolve_update_candidate(int(governance_pack_id))
        return {
            "governance_pack_id": int(governance_pack_id),
            "status": str(update.get("status") or "no_update"),
            "installed_manifest": dict(update.get("installed_manifest") or {}),
            "candidate_manifest": (
                dict(update["candidate_manifest"])
                if isinstance(update.get("candidate_manifest"), dict)
                else None
            ),
            "source_commit_resolved": update.get("source_commit_resolved"),
            "pack_content_digest": update.get("pack_content_digest"),
        }

    async def prepare_upgrade_candidate(
        self,
        *,
        governance_pack_id: int,
        actor_id: int | None,
    ) -> dict[str, Any]:
        """Prepare and persist a pinned candidate for a newer Git-backed governance-pack update."""
        update = await self._resolve_update_candidate(int(governance_pack_id))
        if str(update.get("status") or "") != "newer_version_available":
            raise ValueError("No newer governance-pack source update is available")
        candidate_pack = update.get("candidate_pack")
        if not isinstance(candidate_pack, GovernancePack):
            raise ValueError("Resolved governance-pack update candidate is invalid")
        prepared = await self._persist_prepared_candidate(
            pack=candidate_pack,
            actor_id=actor_id,
        )
        return {
            "status": "newer_version_available",
            "installed_manifest": dict(update.get("installed_manifest") or {}),
            "candidate_manifest": dict(update.get("candidate_manifest") or {}),
            "candidate": prepared["candidate"],
            "manifest": prepared["manifest"],
        }

    async def validate_prepared_upgrade_candidate(
        self,
        *,
        governance_pack_id: int,
        candidate_id: int,
        actor_id: int | None = None,
    ) -> dict[str, Any]:
        """Reject stale prepared upgrade candidates when the tracked Git source has moved."""
        prepared = await self.load_prepared_candidate(
            int(candidate_id),
            actor_id=actor_id,
            revalidate_trust=True,
        )
        update = await self._resolve_update_candidate(int(governance_pack_id))
        if str(update.get("status") or "") != "newer_version_available":
            raise ValueError("Prepared governance-pack upgrade candidate is stale")
        candidate_row = dict(prepared.get("candidate") or {})
        if (
            str(candidate_row.get("source_commit_resolved") or "").strip()
            != str(update.get("source_commit_resolved") or "").strip()
            or str(candidate_row.get("pack_content_digest") or "").strip()
            != str(update.get("pack_content_digest") or "").strip()
        ):
            raise ValueError("Prepared governance-pack upgrade candidate is stale")
        return prepared
