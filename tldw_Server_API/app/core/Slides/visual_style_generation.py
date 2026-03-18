"""Helpers for style-aware slide generation and fallback visual blocks."""

from __future__ import annotations

import json
from typing import Any


_STYLE_PROMPT_HINTS: dict[str, tuple[str, ...]] = {
    "timeline": (
        "Favor chronology, causality, and milestone sequencing.",
        "When helpful, emit timeline visual blocks with dated events and short explanations.",
    ),
    "exam-focused-bullet": (
        "Prefer concise, high-yield bullets over narrative paragraphs.",
        "Optimize for recall, revision, and fast scanning.",
    ),
    "diagram-map-based": (
        "Emphasize relationships, flows, regions, and conceptual structure.",
        "Use process or comparison blocks when they improve comprehension.",
    ),
    "data-visualization": (
        "Highlight metrics, trends, comparisons, and quantitative takeaways.",
        "Prefer stat groups or comparison blocks over decorative prose.",
    ),
    "storytelling": (
        "Use a narrative arc with setup, development, and payoff.",
        "Keep slides concise while preserving story progression.",
    ),
}


def build_visual_style_generation_prompt(visual_style_snapshot: dict[str, Any] | None) -> str:
    """Return style-specific prompt guidance for slide generation."""

    if not isinstance(visual_style_snapshot, dict) or not visual_style_snapshot:
        return ""

    style_id = str(visual_style_snapshot.get("id") or "").strip()
    style_name = str(visual_style_snapshot.get("name") or style_id or "selected").strip()
    generation_rules = (
        visual_style_snapshot.get("generation_rules")
        if isinstance(visual_style_snapshot.get("generation_rules"), dict)
        else {}
    )
    artifact_preferences = (
        visual_style_snapshot.get("artifact_preferences")
        if isinstance(visual_style_snapshot.get("artifact_preferences"), list)
        else []
    )

    lines = [
        f"Visual style preset: {style_name}.",
        "Adapt slide structure and emphasis to this preset instead of using a generic deck pattern.",
    ]
    lines.extend(_STYLE_PROMPT_HINTS.get(style_id, ()))
    if generation_rules:
        lines.append(
            "Generation rules: "
            + json.dumps(generation_rules, ensure_ascii=True, sort_keys=True)
        )
    if artifact_preferences:
        lines.append(
            "Preferred visual block types: "
            + ", ".join(str(item) for item in artifact_preferences)
        )
    lines.append(
        "You may include metadata.visual_blocks on slides using these supported types: "
        "timeline, comparison_matrix, process_flow, stat_group."
    )
    lines.append(
        "Every slide must remain valid in plain markdown or reveal exports, so provide meaningful content "
        "or enough structured metadata for textual fallback compilation."
    )
    lines.append(
        'Example timeline block: {"type":"timeline","items":[{"label":"1776","title":"Event","description":"Why it matters"}]}'
    )
    return "\n".join(lines)


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
        lines.append(f"- {headline}: {details}".rstrip(": "))
    return lines or _compile_generic_block(block)


def _compile_process_flow(block: dict[str, Any]) -> list[str]:
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
