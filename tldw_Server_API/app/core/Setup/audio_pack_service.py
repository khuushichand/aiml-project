"""Offline-pack helpers for setup audio bundle manifests."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.Setup.audio_bundle_catalog import (
    AUDIO_BUNDLE_CATALOG_VERSION,
    DEFAULT_AUDIO_RESOURCE_PROFILE,
    build_audio_selection_key,
    get_audio_bundle_catalog,
)

AUDIO_PACK_FORMAT = "audio_bundle_pack_manifest_v1"

PACK_ISSUE_UNKNOWN_BUNDLE = "unknown_bundle"
PACK_ISSUE_MANIFEST_CHECKSUM = "manifest_checksum_mismatch"
PACK_ISSUE_PLATFORM_MISMATCH = "platform_mismatch"
PACK_ISSUE_ARCH_MISMATCH = "arch_mismatch"
PACK_ISSUE_PYTHON_MISMATCH = "python_version_mismatch"
PACK_ISSUE_INVALID_TTS_CHOICE = "invalid_tts_choice"
PACK_ISSUE_SELECTION_KEY_MISMATCH = "selection_key_mismatch"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_python_version(version: str | None = None) -> str:
    if version:
        parts = str(version).split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return str(version)
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _default_compatibility() -> dict[str, str]:
    return {
        "platform": platform.system().lower(),
        "arch": platform.machine().lower(),
        "python_version": _normalise_python_version(),
    }


def _canonical_manifest_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hexdigest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _copy_asset_manifest(installed_assets: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for entry in installed_assets or []:
        if isinstance(entry, dict):
            assets.append(dict(entry))
    return assets


def _append_issue(issues: list[str], issue_codes: list[str], code: str, message: str) -> None:
    issues.append(message)
    issue_codes.append(code)


def _calculate_asset_checksums(assets: list[dict[str, Any]]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for asset in assets:
        path_value = asset.get("path") or asset.get("asset_path")
        if not path_value:
            continue
        asset_path = Path(path_value)
        if not asset_path.is_file():
            continue
        checksums[str(asset_path)] = _sha256_hexdigest(asset_path.read_bytes())
    return checksums


def build_audio_pack_manifest(
    *,
    bundle_id: str,
    resource_profile: str = DEFAULT_AUDIO_RESOURCE_PROFILE,
    tts_choice: str | None = None,
    catalog_version: str = AUDIO_BUNDLE_CATALOG_VERSION,
    compatibility: dict[str, str] | None = None,
    installed_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a portable v1 audio pack manifest."""

    bundle = get_audio_bundle_catalog().bundle_by_id(bundle_id)
    profile = bundle.profile_by_id(resource_profile)
    try:
        canonical_tts_choice = profile.canonical_tts_choice(tts_choice)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    assets = _copy_asset_manifest(installed_assets)

    manifest = {
        "format": AUDIO_PACK_FORMAT,
        "bundle_id": bundle.bundle_id,
        "bundle_label": bundle.label,
        "resource_profile": profile.profile_id,
        "tts_choice": canonical_tts_choice,
        "profile_label": profile.label,
        "catalog_version": catalog_version,
        "selection_key": build_audio_selection_key(
            bundle.bundle_id,
            profile.profile_id,
            catalog_version,
            tts_choice=canonical_tts_choice,
        ),
        "compatibility": compatibility or _default_compatibility(),
        "assets": assets,
        "created_at": _utc_now(),
        "checksums": {},
    }

    manifest_without_checksums = dict(manifest)
    manifest_without_checksums["checksums"] = {}
    manifest["checksums"] = {
        "manifest_sha256": _sha256_hexdigest(_canonical_manifest_payload(manifest_without_checksums)),
        "assets": _calculate_asset_checksums(assets),
    }
    return manifest


def write_audio_pack_manifest(
    *,
    pack_path: str | Path,
    bundle_id: str,
    resource_profile: str = DEFAULT_AUDIO_RESOURCE_PROFILE,
    tts_choice: str | None = None,
    catalog_version: str = AUDIO_BUNDLE_CATALOG_VERSION,
    compatibility: dict[str, str] | None = None,
    installed_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write an audio pack manifest to disk and return the manifest."""

    manifest = build_audio_pack_manifest(
        bundle_id=bundle_id,
        resource_profile=resource_profile,
        tts_choice=tts_choice,
        catalog_version=catalog_version,
        compatibility=compatibility,
        installed_assets=installed_assets,
    )
    destination = Path(pack_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_audio_pack_manifest(pack_path: str | Path) -> dict[str, Any]:
    """Load an audio pack manifest from disk."""

    return json.loads(Path(pack_path).read_text(encoding="utf-8"))


def validate_audio_pack_manifest(
    pack_path: str | Path,
    *,
    machine_profile: dict[str, Any] | None = None,
    python_version: str | None = None,
) -> dict[str, Any]:
    """Validate manifest checksum and local compatibility for an audio pack."""

    manifest = load_audio_pack_manifest(pack_path)
    issues: list[str] = []
    issue_codes: list[str] = []
    warnings: list[str] = []

    if manifest.get("format") != AUDIO_PACK_FORMAT:
        _append_issue(issues, issue_codes, "unsupported_format", "Unsupported audio pack format.")

    bundle_id = manifest.get("bundle_id")
    resource_profile = manifest.get("resource_profile")
    catalog_version = manifest.get("catalog_version") or AUDIO_BUNDLE_CATALOG_VERSION
    canonical_tts_choice = None
    try:
        bundle = get_audio_bundle_catalog().bundle_by_id(bundle_id)
        profile = bundle.profile_by_id(resource_profile)
    except KeyError:
        bundle = None
        profile = None
        _append_issue(
            issues,
            issue_codes,
            PACK_ISSUE_UNKNOWN_BUNDLE,
            "Referenced audio bundle or resource profile is not available in this catalog.",
        )

    checksum_payload = dict(manifest)
    checksum_payload["checksums"] = {}
    expected_manifest_checksum = _sha256_hexdigest(_canonical_manifest_payload(checksum_payload))
    actual_manifest_checksum = manifest.get("checksums", {}).get("manifest_sha256")
    if actual_manifest_checksum != expected_manifest_checksum:
        _append_issue(
            issues,
            issue_codes,
            PACK_ISSUE_MANIFEST_CHECKSUM,
            "Manifest checksum mismatch.",
        )

    local_profile = machine_profile or _default_compatibility()
    compatibility = manifest.get("compatibility") or {}
    if compatibility.get("platform") and compatibility["platform"] != local_profile.get("platform"):
        _append_issue(
            issues,
            issue_codes,
            PACK_ISSUE_PLATFORM_MISMATCH,
            f"Pack platform {compatibility['platform']} does not match local platform {local_profile.get('platform')}."
        )
    if compatibility.get("arch") and compatibility["arch"] != local_profile.get("arch"):
        _append_issue(
            issues,
            issue_codes,
            PACK_ISSUE_ARCH_MISMATCH,
            f"Pack arch {compatibility['arch']} does not match local arch {local_profile.get('arch')}.",
        )

    expected_python = _normalise_python_version(compatibility.get("python_version"))
    local_python = _normalise_python_version(python_version)
    if expected_python and expected_python != local_python:
        _append_issue(
            issues,
            issue_codes,
            PACK_ISSUE_PYTHON_MISMATCH,
            f"Pack Python {expected_python} does not match local Python {local_python}.",
        )

    if profile is not None:
        try:
            expected_tts_choice = profile.canonical_tts_choice(manifest.get("tts_choice"))
        except KeyError as exc:
            _append_issue(
                issues,
                issue_codes,
                PACK_ISSUE_INVALID_TTS_CHOICE,
                str(exc),
            )
            expected_tts_choice = None
        canonical_tts_choice = expected_tts_choice

    canonical_selection_key = build_audio_selection_key(
        bundle_id,
        resource_profile,
        catalog_version,
        tts_choice=canonical_tts_choice,
    )
    manifest_selection_key = manifest.get("selection_key")
    if manifest_selection_key != canonical_selection_key:
        _append_issue(
            issues,
            issue_codes,
            PACK_ISSUE_SELECTION_KEY_MISMATCH,
            "Pack selection key does not match the canonical bundle/profile/TTS choice identity.",
        )

    for asset in manifest.get("assets", []):
        path_value = asset.get("path") or asset.get("asset_path")
        if not path_value:
            continue
        asset_path = Path(path_value)
        if not asset_path.exists():
            warnings.append(f"Referenced asset is not present locally: {asset_path}")

    return {
        "compatible": not issues,
        "issues": issues,
        "issue_codes": issue_codes,
        "warnings": warnings,
        "manifest": manifest,
        "tts_choice": canonical_tts_choice,
        "selection_key": canonical_selection_key,
        "bundle_label": bundle.label if bundle else None,
    }


def register_imported_audio_pack(
    pack_path: str | Path,
    *,
    readiness_store,
    machine_profile: dict[str, Any] | None = None,
    python_version: str | None = None,
) -> dict[str, Any]:
    """Validate an imported pack and persist its metadata into readiness."""

    validation = validate_audio_pack_manifest(
        pack_path,
        machine_profile=machine_profile,
        python_version=python_version,
    )
    readiness = readiness_store.load()
    manifest = validation["manifest"]
    blocking_codes = {
        PACK_ISSUE_INVALID_TTS_CHOICE,
        PACK_ISSUE_SELECTION_KEY_MISMATCH,
        PACK_ISSUE_MANIFEST_CHECKSUM,
        PACK_ISSUE_UNKNOWN_BUNDLE,
    }
    blocking_issue = next(
        (
            issue
            for code, issue in zip(validation["issue_codes"], validation["issues"], strict=False)
            if code in blocking_codes
        ),
        None,
    )
    if blocking_issue is not None:
        raise ValueError(blocking_issue)
    imported_packs = list(readiness.get("imported_packs") or [])
    imported_packs.append(
        {
            "pack_path": str(pack_path),
            "bundle_id": manifest.get("bundle_id"),
            "resource_profile": manifest.get("resource_profile"),
            "tts_choice": validation["tts_choice"],
            "catalog_version": manifest.get("catalog_version"),
            "selection_key": validation["selection_key"],
            "compatible": validation["compatible"],
            "issues": list(validation["issues"]),
            "warnings": list(validation["warnings"]),
            "imported_at": _utc_now(),
            "manifest_sha256": manifest.get("checksums", {}).get("manifest_sha256"),
        }
    )

    updated = readiness_store.update(
        selected_bundle_id=manifest.get("bundle_id"),
        selected_resource_profile=manifest.get("resource_profile") or DEFAULT_AUDIO_RESOURCE_PROFILE,
        tts_choice=validation["tts_choice"],
        catalog_version=manifest.get("catalog_version") or AUDIO_BUNDLE_CATALOG_VERSION,
        selection_key=validation["selection_key"],
        machine_profile=machine_profile or readiness.get("machine_profile"),
        installed_asset_manifests=manifest.get("assets", []),
        imported_packs=imported_packs,
    )
    return {
        **validation,
        "audio_readiness": updated,
    }


__all__ = [
    "AUDIO_PACK_FORMAT",
    "build_audio_pack_manifest",
    "load_audio_pack_manifest",
    "register_imported_audio_pack",
    "validate_audio_pack_manifest",
    "write_audio_pack_manifest",
]
