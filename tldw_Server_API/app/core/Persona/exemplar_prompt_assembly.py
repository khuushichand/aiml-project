"""Shared prompt assembly for persona-owned exemplar guidance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tldw_Server_API.app.core.Persona.exemplar_retrieval import select_persona_exemplars

_WHITESPACE_RE = re.compile(r"\s+")
_PERSONA_BOUNDARY_SECTION_BUDGET = 120
_PERSONA_EXEMPLAR_SECTION_BUDGET = 240


@dataclass(frozen=True)
class PersonaExemplarPromptAssembly:
    """Shared prompt assembly output for persona exemplar retrieval."""

    sections: list[tuple[str, str, int]] = field(default_factory=list)
    selected_exemplars: list[dict[str, Any]] = field(default_factory=list)
    rejected_exemplars: list[dict[str, Any]] = field(default_factory=list)


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _normalize_tag_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        source = value
    else:
        source = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in source:
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_content(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _truncate_to_budget(text: str, token_budget: int) -> str:
    if not text:
        return ""
    estimated = _estimate_tokens(text)
    if estimated <= token_budget:
        return text
    max_chars = max(1, token_budget * 4)
    return f"{text[:max_chars].rstrip()}..."


def _rejected_entry(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    item = dict(candidate)
    item["reason"] = reason
    return item


def _format_boundary_section(boundary_exemplars: list[dict[str, Any]]) -> str:
    if not boundary_exemplars:
        return ""
    lines = [
        "Persona Boundary Guidance",
        "Follow these persona-specific boundaries while remaining truthful about real system capabilities and policy.",
    ]
    for idx, exemplar in enumerate(boundary_exemplars, start=1):
        content = _normalize_content(exemplar.get("content") or exemplar.get("text"))
        if not content:
            continue
        scenario_tags = exemplar.get("scenario_tags") or []
        scenario_label = ", ".join(str(tag) for tag in scenario_tags) or "general"
        tone_label = str(exemplar.get("tone") or "neutral").strip() or "neutral"
        lines.append(f"{idx}. [{scenario_label} | {tone_label}] {content}")
    return "\n".join(lines).strip()


def _format_exemplar_section(style_exemplars: list[dict[str, Any]]) -> str:
    if not style_exemplars:
        return ""
    lines = [
        "Persona Exemplar Guidance",
        "Use these persona-owned exemplars as style anchors. Synthesize them instead of copying them verbatim.",
    ]
    for idx, exemplar in enumerate(style_exemplars, start=1):
        content = _normalize_content(exemplar.get("content") or exemplar.get("text"))
        if not content:
            continue
        scenario_tags = exemplar.get("scenario_tags") or []
        scenario_label = ", ".join(str(tag) for tag in scenario_tags) or "general"
        tone_label = str(exemplar.get("tone") or "neutral").strip() or "neutral"
        kind_label = str(exemplar.get("kind") or "style").strip() or "style"
        lines.append(f"{idx}. [{kind_label} | {scenario_label} | {tone_label}] {content}")
    return "\n".join(lines).strip()


def assemble_persona_exemplar_prompt(
    *,
    persona_id: str,
    exemplars: list[dict[str, Any]],
    requested_scenario_tags: list[str] | None = None,
    requested_tone: str | None = None,
    conflicting_capability_tags: list[str] | None = None,
) -> PersonaExemplarPromptAssembly:
    """Select persona exemplars and assemble prompt sections for reuse across runtimes."""
    selection = select_persona_exemplars(
        persona_id=persona_id,
        exemplars=exemplars,
        requested_scenario_tags=requested_scenario_tags,
        requested_tone=requested_tone,
    )
    conflicting_tags = set(_normalize_tag_list(conflicting_capability_tags))
    selected: list[dict[str, Any]] = []
    rejected = list(selection.rejected)

    for exemplar in selection.selected:
        candidate = dict(exemplar)
        capability_tags = _normalize_tag_list(candidate.get("capability_tags"))
        if conflicting_tags and conflicting_tags.intersection(capability_tags):
            rejected.append(_rejected_entry(candidate, "capability_conflict"))
            continue
        content = _normalize_content(candidate.get("content") or candidate.get("text"))
        if not content:
            rejected.append(_rejected_entry(candidate, "empty_content"))
            continue
        candidate["content"] = content
        candidate["text"] = content
        candidate["capability_tags"] = capability_tags
        selected.append(candidate)

    boundary_exemplars = [item for item in selected if str(item.get("kind") or "") == "boundary"]
    style_exemplars = [item for item in selected if str(item.get("kind") or "") != "boundary"]

    sections: list[tuple[str, str, int]] = []

    boundary_section = _format_boundary_section(boundary_exemplars)
    if boundary_section:
        sections.append(
            (
                "persona_boundary",
                _truncate_to_budget(boundary_section, _PERSONA_BOUNDARY_SECTION_BUDGET),
                _PERSONA_BOUNDARY_SECTION_BUDGET,
            )
        )

    exemplar_section = _format_exemplar_section(style_exemplars)
    if exemplar_section:
        sections.append(
            (
                "persona_exemplars",
                _truncate_to_budget(exemplar_section, _PERSONA_EXEMPLAR_SECTION_BUDGET),
                _PERSONA_EXEMPLAR_SECTION_BUDGET,
            )
        )

    return PersonaExemplarPromptAssembly(
        sections=sections,
        selected_exemplars=selected,
        rejected_exemplars=rejected,
    )


__all__ = ["PersonaExemplarPromptAssembly", "assemble_persona_exemplar_prompt"]
