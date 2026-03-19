#!/usr/bin/env python3
"""Generate bundle-driven audio setup documentation snippets."""

from __future__ import annotations

from collections.abc import Iterable

from tldw_Server_API.app.core.Setup.audio_bundle_catalog import (
    AutomationTier,
    AudioBundle,
    AudioBundleStep,
    AudioResourceProfile,
    get_audio_bundle_catalog,
)

PROFILE_ORDER = ["light", "balanced", "performance"]


def _step_labels(steps: Iterable[AudioBundleStep]) -> list[str]:
    return [step.label for step in steps]


def _plan_summary(resource: AudioBundle | AudioResourceProfile, category: str, variant_key: str) -> str:
    entries = getattr(resource, f"{category}_plan", []) or []
    parts: list[str] = []
    for entry in entries:
        engine = entry.get("engine", "unknown")
        variants = entry.get(variant_key, []) or []
        if variants:
            parts.append(f"{engine} [{', '.join(variants)}]")
        else:
            parts.append(engine)
    return ", ".join(parts) if parts else "none"


def _iter_profiles(bundle: AudioBundle) -> list[AudioResourceProfile]:
    return sorted(
        bundle.resource_profiles.values(),
        key=lambda profile: (
            PROFILE_ORDER.index(profile.profile_id)
            if profile.profile_id in PROFILE_ORDER
            else len(PROFILE_ORDER)
        ),
    )


def _offline_pack_compatibility(bundle: AudioBundle) -> str:
    if bundle.offline_runtime_supported:
        return "v1 manifest import + model portability"
    return "v1 manifest import only"


def generate_bundle_docs_text() -> str:
    """Render a markdown summary of the curated audio bundles."""

    catalog = get_audio_bundle_catalog()
    lines = [
        "## Curated Audio Bundles",
        "",
        "_Generated from `Helper_Scripts/generate_audio_bundle_docs.py` and the setup bundle catalog._",
        "",
        "| Bundle ID | Label | Profiles | Offline runtime after provisioning | Offline pack compatibility | Default STT | Default TTS | Automatic steps | Guided prerequisites |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for bundle in catalog.bundles:
        profiles = ", ".join(profile.label for profile in _iter_profiles(bundle))
        automatic_steps = _step_labels([
            *[step for step in bundle.system_prerequisites if step.automation_tier == AutomationTier.AUTOMATIC],
            *bundle.python_dependencies,
            *bundle.model_assets,
        ])
        guided_steps = _step_labels([
            step for step in bundle.system_prerequisites if step.automation_tier != AutomationTier.AUTOMATIC
        ])
        lines.append(
            "| `{bundle_id}` | {label} | {profiles} | {offline} | {pack_compatibility} | {stt} | {tts} | {automatic} | {guided} |".format(
                bundle_id=bundle.bundle_id,
                label=bundle.label,
                profiles=profiles,
                offline="Yes" if bundle.offline_runtime_supported else "No",
                pack_compatibility=_offline_pack_compatibility(bundle),
                stt=_plan_summary(bundle, "stt", "models"),
                tts=_plan_summary(bundle, "tts", "variants"),
                automatic=", ".join(automatic_steps) or "none",
                guided=", ".join(guided_steps) or "none",
            )
        )

    for bundle in catalog.bundles:
        automatic_steps = [
            *[step for step in bundle.system_prerequisites if step.automation_tier == AutomationTier.AUTOMATIC],
            *bundle.python_dependencies,
            *bundle.model_assets,
        ]
        guided_steps = [
            step for step in bundle.system_prerequisites if step.automation_tier != AutomationTier.AUTOMATIC
        ]
        lines.extend(
            [
                "",
                f"### `{bundle.bundle_id}`",
                "",
                f"- Label: {bundle.label}",
                f"- Resource profiles: {', '.join(profile.label for profile in _iter_profiles(bundle))}",
                f"- Offline runtime after provisioning: {'Yes' if bundle.offline_runtime_supported else 'No'}",
                f"- Offline pack compatibility: {_offline_pack_compatibility(bundle)}",
                f"- Default STT: {_plan_summary(bundle, 'stt', 'models')}",
                f"- Default TTS: {_plan_summary(bundle, 'tts', 'variants')}",
                f"- Automatic steps: {', '.join(_step_labels(automatic_steps)) or 'none'}",
                f"- Guided prerequisites: {', '.join(_step_labels(guided_steps)) or 'none'}",
                "",
                "| Profile | Resource class | Estimated disk | STT plan | TTS plan |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for profile in _iter_profiles(bundle):
            lines.append(
                "| {label} | {resource_class} | {disk} GB | {stt} | {tts} |".format(
                    label=profile.label,
                    resource_class=profile.resource_class or "unspecified",
                    disk=profile.estimated_disk_gb or "n/a",
                    stt=_plan_summary(profile, "stt", "models"),
                    tts=_plan_summary(profile, "tts", "variants"),
                )
            )

    lines.extend(
        [
            "",
            "## Provisioning Modes",
            "",
            "- `Online provisioning`: `/setup` installs Python dependencies, downloads model assets, and verifies the selected bundle/profile on the current machine.",
            "- `Offline pack import`: `/setup` validates a previously exported manifest against local platform, arch, and Python compatibility, then registers the imported pack in the readiness report.",
            "- `Offline pack` v1 scope: manifest + model portability only. It does not install Python dependencies or OS prerequisites on the target machine.",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    print(generate_bundle_docs_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
