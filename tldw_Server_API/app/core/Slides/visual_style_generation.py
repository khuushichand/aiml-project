"""Helpers for style-aware slide generation and fallback visual blocks."""

from __future__ import annotations

import json
from typing import Any

from tldw_Server_API.app.core.Slides.visual_style_catalog import (
    get_builtin_visual_style_definition,
)
from tldw_Server_API.app.core.Slides.visual_style_profiles import (
    build_prompt_profile_prompt_lines,
)


_SUPPORTED_VISUAL_BLOCK_TYPES: tuple[str, ...] = (
    "timeline",
    "comparison_matrix",
    "process_flow",
    "stat_group",
)


def _coerce_dict(value: Any) -> dict[str, Any]:
    """Return a shallow dict copy when the incoming value is dict-like."""

    if isinstance(value, dict):
        return dict(value)
    return {}


def _coerce_string_tuple(value: Any) -> tuple[str, ...]:
    """Normalize a list-like value into a trimmed tuple of strings."""

    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _resolve_visual_style_prompt_source(
    visual_style_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Resolve prompt-driving style metadata from a snapshot or builtin catalog entry."""

    style_id = str(visual_style_snapshot.get("id") or "").strip()
    style_scope = str(visual_style_snapshot.get("scope") or "").strip().lower()
    style_name = str(visual_style_snapshot.get("name") or style_id or "selected").strip()
    resolved = {
        "id": style_id,
        "scope": style_scope,
        "name": style_name,
        "description": str(visual_style_snapshot.get("description") or "").strip(),
        "prompt_profile": str(visual_style_snapshot.get("prompt_profile") or "").strip(),
        "generation_rules": _coerce_dict(visual_style_snapshot.get("generation_rules")),
        "artifact_preferences": _coerce_string_tuple(
            visual_style_snapshot.get("artifact_preferences")
        ),
        "fallback_policy": _coerce_dict(visual_style_snapshot.get("fallback_policy")),
        "prompt_notes": _coerce_string_tuple(visual_style_snapshot.get("prompt_notes")),
        "builtin": False,
    }

    if style_scope == "builtin" and style_id:
        definition = get_builtin_visual_style_definition(style_id)
        if definition is not None:
            resolved.update(
                {
                    "name": definition.name,
                    "description": definition.description,
                    "prompt_profile": definition.prompt_profile,
                    "generation_rules": dict(definition.generation_rules),
                    "artifact_preferences": tuple(definition.artifact_preferences),
                    "fallback_policy": dict(definition.fallback_policy),
                    "prompt_notes": tuple(definition.prompt_notes),
                    "builtin": True,
                }
            )
    return resolved


def _format_fallback_policy(fallback_policy: dict[str, Any]) -> str:
    """Format fallback policy metadata into a compact prompt line."""

    if not fallback_policy:
        return "Keep slides readable in plain markdown if a structured block does not fit."

    parts: list[str] = []
    if "mode" in fallback_policy and str(fallback_policy["mode"]).strip():
        parts.append(f"mode={fallback_policy['mode']}")
    if "preserve_key_stats" in fallback_policy:
        parts.append(f"preserve_key_stats={fallback_policy['preserve_key_stats']}")

    extra_keys = sorted(key for key in fallback_policy if key not in {"mode", "preserve_key_stats"})
    for key in extra_keys:
        value = fallback_policy.get(key)
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            parts.append(f"{key}={value}")

    return "; ".join(parts) if parts else "Keep slides readable in plain markdown."


def _build_prompt_sections(visual_style_snapshot: dict[str, Any]) -> list[str]:
    """Build the prompt sections that steer slide generation toward the selected style."""

    source = _resolve_visual_style_prompt_source(visual_style_snapshot)

    lines = [
        f"Visual style preset: {source['name']}.",
        "Adapt slide structure and emphasis to this preset instead of using a generic deck pattern.",
    ]

    if source["description"]:
        lines.append(f"Style description: {source['description']}")

    if source["prompt_notes"]:
        lines.append("Style notes:")
        lines.extend(f"- {note}" for note in source["prompt_notes"])

    profile_lines = build_prompt_profile_prompt_lines(str(source["prompt_profile"]))
    if profile_lines:
        lines.extend(profile_lines)

    if source["generation_rules"]:
        lines.append(
            "Generation rules: "
            + json.dumps(source["generation_rules"], ensure_ascii=True, sort_keys=True)
        )
    if source["artifact_preferences"]:
        lines.append(
            "Preferred visual block types: "
            + ", ".join(str(item) for item in source["artifact_preferences"])
        )

    lines.append("Fallback instructions: " + _format_fallback_policy(source["fallback_policy"]))
    lines.append(
        "You may include metadata.visual_blocks on slides using these supported types: "
        + ", ".join(_SUPPORTED_VISUAL_BLOCK_TYPES)
        + "."
    )
    lines.append(
        "Every slide must remain valid in plain markdown or reveal exports, so provide meaningful content "
        "or enough structured metadata for textual fallback compilation."
    )
    lines.append(
        'Example timeline block: {"type":"timeline","items":[{"label":"1776","title":"Event","description":"Why it matters"}]}'
    )
    return lines


def build_visual_style_generation_prompt(visual_style_snapshot: dict[str, Any] | None) -> str:
    """Return style-specific prompt guidance for slide generation."""

    if not isinstance(visual_style_snapshot, dict) or not visual_style_snapshot:
        return ""
    return "\n".join(_build_prompt_sections(visual_style_snapshot))


def apply_visual_block_fallback(slide: dict[str, Any]) -> dict[str, Any]:
    """Compile structured visual blocks into plain slide content when needed."""

    metadata = slide.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    blocks = metadata.get("visual_blocks")
    if not isinstance(blocks, list) or not blocks:
        slide["metadata"] = metadata
        return slide

    normalized_blocks: list[dict[str, Any]] = []
    fallback_lines: list[str] = []
    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            continue
        block = dict(raw_block)
        block_type = str(block.get("type") or "generic").strip() or "generic"
        block["type"] = block_type
        normalized_blocks.append(block)
        fallback_lines.extend(_compile_block_fallback(block))

    metadata["visual_blocks"] = normalized_blocks
    slide["metadata"] = metadata
    if not str(slide.get("content") or "").strip() and fallback_lines:
        slide["content"] = "\n".join(fallback_lines)
    return slide


def _compile_block_fallback(block: dict[str, Any]) -> list[str]:
    """Compile a structured visual block into readable markdown fallback lines."""

    block_type = block.get("type")
    if block_type == "timeline":
        return _compile_timeline(block)
    if block_type == "comparison_matrix":
        return _compile_comparison_matrix(block)
    if block_type == "process_flow":
        return _compile_process_flow(block)
    if block_type == "stat_group":
        return _compile_stat_group(block)
    return _compile_generic_block(block)


def _compile_timeline(block: dict[str, Any]) -> list[str]:
    """Compile a timeline block into ordered markdown bullets."""

    items = block.get("items")
    if not isinstance(items, list):
        return _compile_generic_block(block)
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("date") or item.get("year") or "").strip()
        title = str(item.get("title") or item.get("name") or "").strip()
        description = str(item.get("description") or item.get("summary") or "").strip()
        headline = ": ".join(part for part in (label, title) if part)
        if not headline:
            headline = "Timeline event"
        line = f"- {headline}"
        if description:
            line += f" - {description}"
        lines.append(line)
    return lines or _compile_generic_block(block)


def _compile_comparison_matrix(block: dict[str, Any]) -> list[str]:
    """Compile a comparison matrix block into readable comparison bullets."""

    rows = block.get("rows")
    if not isinstance(rows, list):
        return _compile_generic_block(block)
    lines: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("name") or row.get("topic") or "").strip()
        values = row.get("values")
        summary = str(row.get("summary") or row.get("description") or "").strip()
        value_text = ", ".join(str(item) for item in values) if isinstance(values, list) else ""
        details = summary or value_text
        headline = label or "Comparison"
        line = f"- {headline}"
        if details:
            line += f": {details}"
        lines.append(line)
    return lines or _compile_generic_block(block)


def _compile_process_flow(block: dict[str, Any]) -> list[str]:
    """Compile a process flow block into numbered markdown steps."""

    steps = block.get("steps")
    if not isinstance(steps, list):
        return _compile_generic_block(block)
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        title = str(step.get("title") or step.get("name") or f"Step {index}").strip()
        description = str(step.get("description") or step.get("summary") or "").strip()
        line = f"{index}. {title}"
        if description:
            line += f" - {description}"
        lines.append(line)
    return lines or _compile_generic_block(block)


def _compile_stat_group(block: dict[str, Any]) -> list[str]:
    """Compile a stat group block into metric bullets."""

    items = block.get("items")
    if not isinstance(items, list):
        return _compile_generic_block(block)
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or "Metric").strip()
        value = str(item.get("value") or item.get("stat") or "").strip()
        context = str(item.get("context") or item.get("description") or "").strip()
        line = f"- {label}"
        if value:
            line += f": {value}"
        if context:
            line += f" - {context}"
        lines.append(line)
    return lines or _compile_generic_block(block)


def _compile_generic_block(block: dict[str, Any]) -> list[str]:
    """Compile an unknown block into a generic markdown fallback."""

    title = str(block.get("title") or block.get("name") or "").strip()
    description = str(block.get("description") or block.get("summary") or "").strip()
    if title and description:
        return [f"- {title}: {description}"]
    if title:
        return [f"- {title}"]
    if description:
        return [f"- {description}"]
    scalars: list[str] = []
    for key, value in block.items():
        if key == "type":
            continue
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            scalars.append(f"{key}: {value}")
    if scalars:
        return [f"- {item}" for item in scalars]
    return []
