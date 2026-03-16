#!/usr/bin/env python3
"""Generate bundle-driven audio setup documentation snippets."""

from __future__ import annotations

from typing import Iterable

from tldw_Server_API.app.core.Setup.audio_bundle_catalog import AudioBundle, AudioBundleStep, get_audio_bundle_catalog


def _step_labels(steps: Iterable[AudioBundleStep]) -> list[str]:
    return [step.label for step in steps]


def _plan_summary(bundle: AudioBundle, category: str, variant_key: str) -> str:
    entries = getattr(bundle, f"{category}_plan", []) or []
    parts: list[str] = []
    for entry in entries:
        engine = entry.get("engine", "unknown")
        variants = entry.get(variant_key, []) or []
        if variants:
            parts.append(f"{engine} [{', '.join(variants)}]")
        else:
            parts.append(engine)
    return ", ".join(parts) if parts else "none"


def generate_bundle_docs_text() -> str:
    """Render a markdown summary of the curated audio bundles."""

    catalog = get_audio_bundle_catalog()
    lines = [
        "## Curated Audio Bundles",
        "",
        "_Generated from `Helper_Scripts/generate_audio_bundle_docs.py` and the setup bundle catalog._",
        "",
        "| Bundle ID | Label | Offline runtime after provisioning | Default STT | Default TTS | Automatic steps | Guided prerequisites |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for bundle in catalog.bundles:
        automatic_steps = _step_labels([
            *[step for step in bundle.system_prerequisites if step.automation_tier == "automatic"],
            *bundle.python_dependencies,
            *bundle.model_assets,
        ])
        guided_steps = _step_labels([
            step for step in bundle.system_prerequisites if step.automation_tier != "automatic"
        ])
        lines.append(
            "| `{bundle_id}` | {label} | {offline} | {stt} | {tts} | {automatic} | {guided} |".format(
                bundle_id=bundle.bundle_id,
                label=bundle.label,
                offline="Yes" if bundle.offline_runtime_supported else "No",
                stt=_plan_summary(bundle, "stt", "models"),
                tts=_plan_summary(bundle, "tts", "variants"),
                automatic=", ".join(automatic_steps) or "none",
                guided=", ".join(guided_steps) or "none",
            )
        )

    for bundle in catalog.bundles:
        automatic_steps = [
            *[step for step in bundle.system_prerequisites if step.automation_tier == "automatic"],
            *bundle.python_dependencies,
            *bundle.model_assets,
        ]
        guided_steps = [
            step for step in bundle.system_prerequisites if step.automation_tier != "automatic"
        ]
        lines.extend(
            [
                "",
                f"### `{bundle.bundle_id}`",
                "",
                f"- Label: {bundle.label}",
                f"- Offline runtime after provisioning: {'Yes' if bundle.offline_runtime_supported else 'No'}",
                f"- Default STT: {_plan_summary(bundle, 'stt', 'models')}",
                f"- Default TTS: {_plan_summary(bundle, 'tts', 'variants')}",
                f"- Automatic steps: {', '.join(_step_labels(automatic_steps)) or 'none'}",
                f"- Guided prerequisites: {', '.join(_step_labels(guided_steps)) or 'none'}",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    print(generate_bundle_docs_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
