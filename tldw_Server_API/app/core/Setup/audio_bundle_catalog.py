"""Curated audio setup bundle definitions for the setup workflow."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

AUDIO_BUNDLE_CATALOG_VERSION = "v2"
DEFAULT_AUDIO_RESOURCE_PROFILE = "balanced"


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


class AudioResourceProfile(BaseModel):
    """Concrete install-time plan for a bundle resource tier."""

    profile_id: str
    label: str
    description: str | None = None
    stt_plan: list[dict[str, Any]] = Field(default_factory=list)
    tts_plan: list[dict[str, Any]] = Field(default_factory=list)
    embeddings_plan: dict[str, list[str]] = Field(
        default_factory=lambda: {"huggingface": [], "custom": [], "onnx": []}
    )
    default_config_updates: dict[str, dict[str, str]] = Field(default_factory=dict)
    verification_targets: list[str] = Field(default_factory=list)
    estimated_disk_gb: float | None = None
    resource_class: str | None = None

    class CuratedTTSChoice(BaseModel):
        """Curated TTS engine choice metadata for a profile."""

        choice_id: str
        label: str
        description: str | None = None
        tts_plan: list[dict[str, Any]] = Field(default_factory=list)

    tts_choices: list[CuratedTTSChoice] = Field(default_factory=list)
    default_tts_choice: str | None = None

    @model_validator(mode="after")
    def populate_default_tts_choice_plan(self) -> "AudioResourceProfile":
        """Keep legacy tts_plan aligned to the stable default curated choice."""

        if not self.tts_choices:
            return self

        choice_ids = [choice.choice_id for choice in self.tts_choices]
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError(
                f"Duplicate curated TTS choice IDs for profile '{self.profile_id}'"
            )

        available_choices = {choice.choice_id: choice for choice in self.tts_choices}
        selected_choice = self.default_tts_choice or self.tts_choices[0].choice_id
        try:
            choice = available_choices[selected_choice]
        except KeyError as exc:
            raise ValueError(
                f"Unknown curated TTS choice '{selected_choice}' for profile '{self.profile_id}'"
            ) from exc

        self.default_tts_choice = selected_choice
        self.tts_plan = deepcopy(choice.tts_plan)
        return self


def _build_curated_cpu_tts_choices() -> list[AudioResourceProfile.CuratedTTSChoice]:
    return [
        AudioResourceProfile.CuratedTTSChoice(
            choice_id="kokoro",
            label="Kokoro",
            tts_plan=[{"engine": "kokoro", "variants": []}],
        ),
        AudioResourceProfile.CuratedTTSChoice(
            choice_id="kitten_tts",
            label="KittenTTS",
            tts_plan=[{"engine": "kitten_tts", "variants": []}],
        ),
    ]


class AudioBundle(BaseModel):
    """Operator-facing definition for a curated audio setup bundle."""

    bundle_id: str
    label: str
    description: str
    catalog_version: str = AUDIO_BUNDLE_CATALOG_VERSION
    default_resource_profile: str = DEFAULT_AUDIO_RESOURCE_PROFILE
    offline_runtime_supported: bool = True
    system_prerequisites: list[AudioBundleStep] = Field(default_factory=list)
    python_dependencies: list[AudioBundleStep] = Field(default_factory=list)
    model_assets: list[AudioBundleStep] = Field(default_factory=list)
    resource_profiles: dict[str, AudioResourceProfile] = Field(default_factory=dict)
    stt_plan: list[dict[str, Any]] = Field(default_factory=list)
    tts_plan: list[dict[str, Any]] = Field(default_factory=list)
    embeddings_plan: dict[str, list[str]] = Field(
        default_factory=lambda: {"huggingface": [], "custom": [], "onnx": []}
    )
    default_config_updates: dict[str, dict[str, str]] = Field(default_factory=dict)
    verification_targets: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_profile_compatibility_fields(self) -> "AudioBundle":
        """Keep the legacy bundle shape populated from the default profile."""

        if not self.resource_profiles:
            self.resource_profiles = {
                self.default_resource_profile: AudioResourceProfile(
                    profile_id=self.default_resource_profile,
                    label=self.default_resource_profile.replace("_", " ").title(),
                    stt_plan=list(self.stt_plan),
                    tts_plan=list(self.tts_plan),
                    embeddings_plan=dict(self.embeddings_plan),
                    default_config_updates=dict(self.default_config_updates),
                    verification_targets=list(self.verification_targets),
                )
            }

        default_profile = self.profile_by_id(self.default_resource_profile)
        self.stt_plan = list(default_profile.stt_plan)
        self.tts_plan = list(default_profile.tts_plan)
        self.embeddings_plan = dict(default_profile.embeddings_plan)
        self.default_config_updates = dict(default_profile.default_config_updates)
        self.verification_targets = list(default_profile.verification_targets)
        return self

    def profile_by_id(self, profile_id: str | None = None) -> AudioResourceProfile:
        selected_profile = profile_id or self.default_resource_profile
        try:
            return self.resource_profiles[selected_profile]
        except KeyError as exc:
            raise KeyError(
                f"Unknown resource profile '{selected_profile}' for audio bundle '{self.bundle_id}'"
            ) from exc


class AudioBundleCatalog(BaseModel):
    """Collection of available curated audio bundles."""

    bundles: list[AudioBundle] = Field(default_factory=list)

    def bundle_by_id(self, bundle_id: str) -> AudioBundle:
        for bundle in self.bundles:
            if bundle.bundle_id == bundle_id:
                return bundle
        raise KeyError(f"Unknown audio bundle '{bundle_id}'")


def build_audio_selection_key(
    bundle_id: str,
    resource_profile: str = DEFAULT_AUDIO_RESOURCE_PROFILE,
    catalog_version: str = AUDIO_BUNDLE_CATALOG_VERSION,
) -> str:
    """Build a stable identity key for a bundle/profile selection."""

    return f"{catalog_version}:{bundle_id}:{resource_profile}"


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


def _local_resource_profiles(
    *,
    light_model: str,
    balanced_model: str,
    performance_model: str,
    disk_estimates_gb: tuple[float, float, float],
) -> dict[str, AudioResourceProfile]:
    return {
        "light": AudioResourceProfile(
            profile_id="light",
            label="Light",
            description="Lowest-footprint local speech profile.",
            stt_plan=[{"engine": "faster_whisper", "models": [light_model]}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            tts_choices=_build_curated_cpu_tts_choices(),
            default_tts_choice="kokoro",
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=disk_estimates_gb[0],
            resource_class="low",
        ),
        "balanced": AudioResourceProfile(
            profile_id="balanced",
            label="Balanced",
            description="Default local speech profile for most machines.",
            stt_plan=[{"engine": "faster_whisper", "models": [balanced_model]}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            tts_choices=_build_curated_cpu_tts_choices(),
            default_tts_choice="kokoro",
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=disk_estimates_gb[1],
            resource_class="medium",
        ),
        "performance": AudioResourceProfile(
            profile_id="performance",
            label="Performance",
            description="Higher-quality local speech profile for stronger machines.",
            stt_plan=[{"engine": "faster_whisper", "models": [performance_model]}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=disk_estimates_gb[2],
            resource_class="high",
        ),
    }


def _hybrid_resource_profiles() -> dict[str, AudioResourceProfile]:
    return {
        "balanced": AudioResourceProfile(
            profile_id="balanced",
            label="Balanced",
            description="Hybrid hosted-first profile with a local backup path.",
            stt_plan=[{"engine": "faster_whisper", "models": ["small"]}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=2.5,
            resource_class="medium",
        )
    }


def _apple_silicon_resource_profiles() -> dict[str, AudioResourceProfile]:
    return {
        "light": AudioResourceProfile(
            profile_id="light",
            label="Light",
            description="Lowest-footprint local speech profile for Apple Silicon.",
            stt_plan=[{"engine": "faster_whisper", "models": ["tiny"]}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=1.0,
            resource_class="low",
        ),
        "balanced": AudioResourceProfile(
            profile_id="balanced",
            label="Balanced",
            description="Recommended Apple Silicon profile using MLX Parakeet for STT.",
            stt_plan=[{"engine": "nemo_parakeet_mlx", "models": []}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=3.0,
            resource_class="medium",
        ),
        "performance": AudioResourceProfile(
            profile_id="performance",
            label="Performance",
            description="Higher-throughput Apple Silicon speech profile using MLX Parakeet.",
            stt_plan=[{"engine": "nemo_parakeet_mlx", "models": []}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=4.5,
            resource_class="high",
        ),
    }


def _nvidia_resource_profiles() -> dict[str, AudioResourceProfile]:
    return {
        "light": AudioResourceProfile(
            profile_id="light",
            label="Light",
            description="Lowest-footprint CUDA-capable speech profile.",
            stt_plan=[{"engine": "faster_whisper", "models": ["small"]}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=2.0,
            resource_class="low",
        ),
        "balanced": AudioResourceProfile(
            profile_id="balanced",
            label="Balanced",
            description="Recommended NVIDIA profile using Parakeet with Kokoro TTS.",
            stt_plan=[{"engine": "nemo_parakeet_onnx", "models": []}],
            tts_plan=[{"engine": "kokoro", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=4.5,
            resource_class="medium",
        ),
        "performance": AudioResourceProfile(
            profile_id="performance",
            label="Performance",
            description="Higher-quality NVIDIA speech profile using Parakeet and Dia TTS.",
            stt_plan=[{"engine": "nemo_parakeet_standard", "models": []}],
            tts_plan=[{"engine": "dia", "variants": []}],
            verification_targets=["stt_default", "tts_default"],
            estimated_disk_gb=9.0,
            resource_class="high",
        ),
    }


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
            resource_profiles=_local_resource_profiles(
                light_model="tiny",
                balanced_model="small",
                performance_model="medium",
                disk_estimates_gb=(1.0, 2.0, 4.5),
            ),
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
            resource_profiles=_apple_silicon_resource_profiles(),
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
            resource_profiles=_nvidia_resource_profiles(),
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
            resource_profiles=_hybrid_resource_profiles(),
        ),
    ]

    return AudioBundleCatalog(bundles=bundles)


__all__ = [
    "AudioBundle",
    "AudioBundleCatalog",
    "AudioBundleStep",
    "AudioResourceProfile",
    "AUDIO_BUNDLE_CATALOG_VERSION",
    "AutomationTier",
    "DEFAULT_AUDIO_RESOURCE_PROFILE",
    "build_audio_selection_key",
    "get_audio_bundle_catalog",
]
