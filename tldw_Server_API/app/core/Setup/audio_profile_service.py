"""Machine profile detection and audio bundle recommendation helpers."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from pydantic import BaseModel

from tldw_Server_API.app.core.Setup.audio_bundle_catalog import get_audio_bundle_catalog
from tldw_Server_API.app.core.Setup import install_manager


class MachineProfile(BaseModel):
    """Best-effort local machine capability snapshot for setup recommendations."""

    platform: str
    arch: str
    apple_silicon: bool
    cuda_available: bool
    ffmpeg_available: bool
    espeak_available: bool
    free_disk_gb: float
    network_available_for_downloads: bool


class BundleRecommendation(BaseModel):
    """A scored audio bundle recommendation."""

    bundle_id: str
    label: str
    reasons: list[str]
    score: int


def detect_machine_profile() -> MachineProfile:
    """Build a best-effort machine profile from local signals."""

    system_name = platform.system().lower()
    machine_arch = platform.machine().lower()
    project_root = Path.cwd()

    try:
        disk_usage = shutil.disk_usage(project_root)
        free_disk_gb = round(disk_usage.free / (1024 ** 3), 1)
    except Exception:
        free_disk_gb = 0.0

    espeak_present = bool(shutil.which("espeak-ng") or shutil.which("espeak"))
    if not espeak_present:
        espeak_library = os.getenv("PHONEMIZER_ESPEAK_LIBRARY")
        espeak_present = bool(espeak_library and os.path.exists(espeak_library))

    force_offline = os.getenv("TLDW_SETUP_FORCE_OFFLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return MachineProfile(
        platform=system_name,
        arch=machine_arch,
        apple_silicon=system_name == "darwin" and machine_arch in {"arm64", "aarch64"},
        cuda_available=install_manager._cuda_available(),  # noqa: SLF001
        ffmpeg_available=bool(shutil.which("ffmpeg")),
        espeak_available=espeak_present,
        free_disk_gb=free_disk_gb,
        network_available_for_downloads=not force_offline and install_manager._downloads_allowed(),  # noqa: SLF001
    )


def rank_audio_bundles(
    profile: MachineProfile,
    *,
    prefer_offline_runtime: bool,
    allow_hosted_fallbacks: bool,
) -> list[BundleRecommendation]:
    """Return ranked bundle recommendations for the supplied machine profile."""

    catalog = get_audio_bundle_catalog()
    recommendations: list[BundleRecommendation] = []

    for bundle in catalog.bundles:
        if bundle.bundle_id == "hosted_plus_local_backup" and not allow_hosted_fallbacks:
            continue
        if bundle.bundle_id == "nvidia_local" and not profile.cuda_available:
            continue
        if bundle.bundle_id == "apple_silicon_local" and not profile.apple_silicon:
            continue

        score = 50
        reasons: list[str] = []

        if prefer_offline_runtime and bundle.offline_runtime_supported:
            score += 15
            reasons.append("Supports offline runtime after provisioning")

        if bundle.bundle_id == "nvidia_local":
            if profile.cuda_available:
                score += 40
                reasons.append("CUDA detected")
            else:
                score -= 30
                reasons.append("CUDA not detected")
        elif bundle.bundle_id == "apple_silicon_local":
            if profile.apple_silicon:
                score += 40
                reasons.append("Apple Silicon detected")
            else:
                score -= 20
                reasons.append("Apple Silicon not detected")
        elif bundle.bundle_id == "cpu_local":
            score += 20
            reasons.append("Conservative local-first default")
        elif bundle.bundle_id == "hosted_plus_local_backup":
            if allow_hosted_fallbacks:
                score += 10
                reasons.append("Hosted fallbacks allowed")
            if prefer_offline_runtime:
                score -= 15
                reasons.append("Offline runtime preferred")

        if not profile.ffmpeg_available:
            score -= 5
            reasons.append("FFmpeg prerequisite still needed")
        if not profile.espeak_available:
            score -= 5
            reasons.append("eSpeak prerequisite still needed")

        recommendations.append(
            BundleRecommendation(
                bundle_id=bundle.bundle_id,
                label=bundle.label,
                reasons=reasons,
                score=score,
            )
        )

    return sorted(recommendations, key=lambda item: item.score, reverse=True)


def recommend_audio_bundles(
    profile: MachineProfile,
    *,
    prefer_offline_runtime: bool,
    allow_hosted_fallbacks: bool,
) -> dict[str, list[dict[str, object]]]:
    """Return ranked and excluded bundles for the current machine profile."""

    ranked = rank_audio_bundles(
        profile,
        prefer_offline_runtime=prefer_offline_runtime,
        allow_hosted_fallbacks=allow_hosted_fallbacks,
    )
    excluded: list[dict[str, object]] = []

    if not profile.cuda_available:
        excluded.append(
            {
                "bundle_id": "nvidia_local",
                "reasons": ["CUDA not detected"],
            }
        )
    if not profile.apple_silicon:
        excluded.append(
            {
                "bundle_id": "apple_silicon_local",
                "reasons": ["Apple Silicon not detected"],
            }
        )
    if not allow_hosted_fallbacks:
        excluded.append(
            {
                "bundle_id": "hosted_plus_local_backup",
                "reasons": ["Hosted fallbacks disabled by operator preference"],
            }
        )

    return {
        "recommendations": [recommendation.model_dump() for recommendation in ranked],
        "excluded": excluded,
    }


__all__ = [
    "BundleRecommendation",
    "MachineProfile",
    "detect_machine_profile",
    "rank_audio_bundles",
    "recommend_audio_bundles",
]
