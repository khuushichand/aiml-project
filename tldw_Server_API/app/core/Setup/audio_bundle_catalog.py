"""Curated audio setup bundle definitions for the setup workflow."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AutomationTier(str, Enum):
    """How much of a setup step the product can automate."""

    AUTOMATIC = "automatic"
    GUIDED = "guided"
    MANUAL_BLOCKED = "manual_blocked"


class AudioBundleStep(BaseModel):
    """A single bundle setup step or prerequisite."""

    step_id: str
    label: str
    automation_tier: AutomationTier
    detail: str | None = None
    linux_hint: str | None = None
    macos_hint: str | None = None
    windows_hint: str | None = None


class AudioBundle(BaseModel):
    """Operator-facing definition for a curated audio setup bundle."""

    bundle_id: str
    label: str
    description: str
    offline_runtime_supported: bool = True
    system_prerequisites: list[AudioBundleStep] = Field(default_factory=list)
    python_dependencies: list[AudioBundleStep] = Field(default_factory=list)
    model_assets: list[AudioBundleStep] = Field(default_factory=list)
    verification_targets: list[str] = Field(default_factory=list)


class AudioBundleCatalog(BaseModel):
    """Collection of available curated audio bundles."""

    bundles: list[AudioBundle] = Field(default_factory=list)

    def bundle_by_id(self, bundle_id: str) -> AudioBundle:
        for bundle in self.bundles:
            if bundle.bundle_id == bundle_id:
                return bundle
        raise KeyError(f"Unknown audio bundle '{bundle_id}'")


def _guided_prerequisites() -> list[AudioBundleStep]:
    return [
        AudioBundleStep(
            step_id="ffmpeg",
            label="Install FFmpeg",
            automation_tier=AutomationTier.GUIDED,
            detail="Required for audio decoding and transcoding.",
            macos_hint="brew install ffmpeg",
            linux_hint="sudo apt-get install -y ffmpeg",
        ),
        AudioBundleStep(
            step_id="espeak_ng",
            label="Install eSpeak NG",
            automation_tier=AutomationTier.GUIDED,
            detail="Required for Kokoro phonemizer support.",
            macos_hint="brew install espeak-ng",
            linux_hint="sudo apt-get install -y espeak-ng",
        ),
    ]


def get_audio_bundle_catalog() -> AudioBundleCatalog:
    """Return the current curated audio setup bundles."""

    bundles = [
        AudioBundle(
            bundle_id="cpu_local",
            label="CPU Local",
            description="Conservative local bundle for CPU-only machines.",
            system_prerequisites=_guided_prerequisites(),
            python_dependencies=[
                AudioBundleStep(
                    step_id="python_deps_cpu_local",
                    label="Install CPU-local Python dependencies",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            model_assets=[
                AudioBundleStep(
                    step_id="models_cpu_local",
                    label="Download CPU-local speech model assets",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            verification_targets=["stt_default", "tts_default"],
        ),
        AudioBundle(
            bundle_id="apple_silicon_local",
            label="Apple Silicon Local",
            description="Local bundle for Apple Silicon machines with on-device acceleration where available.",
            system_prerequisites=_guided_prerequisites(),
            python_dependencies=[
                AudioBundleStep(
                    step_id="python_deps_apple_local",
                    label="Install Apple Silicon Python dependencies",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            model_assets=[
                AudioBundleStep(
                    step_id="models_apple_local",
                    label="Download Apple Silicon speech model assets",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            verification_targets=["stt_default", "tts_default"],
        ),
        AudioBundle(
            bundle_id="nvidia_local",
            label="NVIDIA Local",
            description="Local bundle for machines with working CUDA.",
            system_prerequisites=_guided_prerequisites(),
            python_dependencies=[
                AudioBundleStep(
                    step_id="python_deps_nvidia_local",
                    label="Install NVIDIA local Python dependencies",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            model_assets=[
                AudioBundleStep(
                    step_id="models_nvidia_local",
                    label="Download NVIDIA speech model assets",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            verification_targets=["stt_default", "tts_default"],
        ),
        AudioBundle(
            bundle_id="hosted_plus_local_backup",
            label="Hosted With Local Backup",
            description="Hybrid bundle for fast hosted defaults with a local fallback path.",
            offline_runtime_supported=False,
            system_prerequisites=_guided_prerequisites(),
            python_dependencies=[
                AudioBundleStep(
                    step_id="python_deps_hosted_local_backup",
                    label="Install hybrid Python dependencies",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            model_assets=[
                AudioBundleStep(
                    step_id="models_hosted_local_backup",
                    label="Download local fallback speech model assets",
                    automation_tier=AutomationTier.AUTOMATIC,
                )
            ],
            verification_targets=["stt_default", "tts_default"],
        ),
    ]

    return AudioBundleCatalog(bundles=bundles)


__all__ = [
    "AudioBundle",
    "AudioBundleCatalog",
    "AudioBundleStep",
    "AutomationTier",
    "get_audio_bundle_catalog",
]
