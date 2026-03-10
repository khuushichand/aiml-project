"""Transcript-driven candidate exemplar generation for Persona Garden."""

from __future__ import annotations

import re
from typing import Any

_SPEAKER_PREFIX_RE = re.compile(r"^[A-Za-z0-9 _-]{1,40}:\s*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE_RE = re.compile(r"\s+")

_BOUNDARY_PHRASES = (
    "i won't",
    "i will not",
    "i do not",
    "i'm not going to",
    "i am not going to",
    "can't",
    "cannot",
    "refuse",
)
_PROMPT_TARGET_PHRASES = (
    "hidden instructions",
    "system prompt",
    "developer prompt",
    "rules",
)
_SMALL_TALK_TOKENS = {"hello", "hey", "hi", "thanks", "thank", "appreciate"}
_HEATED_TOKENS = {"angry", "furious", "nasty", "rude"}
_CODING_TOKENS = {"code", "coding", "debug", "python", "script", "typescript"}
_TOOL_TOKENS = {"browse", "fetch", "lookup", "retrieve", "search", "tool", "web"}


def _normalize_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _normalize_line(raw_line: str) -> str:
    text = _normalize_text(raw_line)
    if not text:
        return ""
    return _SPEAKER_PREFIX_RE.sub("", text).strip()


def _segment_transcript(transcript: str) -> list[str]:
    normalized = _normalize_text(transcript)
    if not normalized:
        return []
    raw_lines = [segment for segment in transcript.splitlines() if str(segment or "").strip()]
    segments = [_normalize_line(line) for line in raw_lines]
    segments = [segment for segment in segments if segment]
    if len(segments) <= 1:
        segments = [_normalize_text(part) for part in _SENTENCE_SPLIT_RE.split(normalized)]
    cleaned: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        text = _normalize_line(segment)
        if len(text) < 24:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _infer_kind(text: str) -> str:
    lowered = text.lower()
    if any(phrase in lowered for phrase in _BOUNDARY_PHRASES):
        return "boundary"
    return "style"


def _infer_tone(text: str) -> str | None:
    lowered = text.lower()
    tokens = set(re.findall(r"[a-z0-9_+#./-]+", lowered))
    if tokens.intersection(_HEATED_TOKENS) or text.count("!") >= 2:
        return "heated"
    if tokens.intersection(_SMALL_TALK_TOKENS):
        return "warm"
    return "neutral"


def _infer_scenario_tags(text: str) -> list[str]:
    lowered = text.lower()
    tokens = set(re.findall(r"[a-z0-9_+#./-]+", lowered))
    tags: list[str] = []
    if any(phrase in lowered for phrase in _PROMPT_TARGET_PHRASES):
        tags.append("meta_prompt")
    if tokens.intersection(_CODING_TOKENS):
        tags.append("coding_request")
    if tokens.intersection(_TOOL_TOKENS):
        tags.append("tool_request")
    if tokens.intersection(_SMALL_TALK_TOKENS):
        tags.append("small_talk")
    if not tags:
        tags.append("general")
    return tags


def build_transcript_exemplar_candidates(
    *,
    transcript: str,
    source_ref: str | None = None,
    notes: str | None = None,
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    """Convert transcript text into disabled generated candidates for review."""
    segments = _segment_transcript(transcript)
    candidates: list[dict[str, Any]] = []
    max_count = max(1, min(int(max_candidates or 5), 10))
    base_notes = _normalize_text(notes)

    for index, segment in enumerate(segments[:max_count]):
        kind = _infer_kind(segment)
        candidate_notes = "Transcript candidate pending review."
        if base_notes:
            candidate_notes = f"{candidate_notes} Source notes: {base_notes}"
        candidates.append(
            {
                "kind": kind,
                "content": segment,
                "tone": _infer_tone(segment),
                "scenario_tags": _infer_scenario_tags(segment),
                "capability_tags": [],
                "priority": max_count - index,
                "enabled": False,
                "source_type": "generated_candidate",
                "source_ref": source_ref,
                "notes": candidate_notes,
            }
        )
    return candidates


def append_exemplar_review_note(
    *,
    existing_notes: str | None,
    action: str,
    review_note: str | None = None,
) -> str:
    """Append a deterministic review audit line to candidate notes."""
    base = _normalize_text(existing_notes)
    suffix = _normalize_text(review_note)
    normalized_action = _normalize_text(action).replace("-", "_").replace(" ", "_")
    action_label = {
        "approve": "approved",
        "approved": "approved",
        "reject": "rejected",
        "rejected": "rejected",
    }.get(normalized_action, normalized_action or "reviewed")
    review_line = f"Review {action_label}."
    if suffix:
        review_line = f"{review_line} {suffix}"
    if not base:
        return review_line
    return f"{base}\n{review_line}"


__all__ = [
    "append_exemplar_review_note",
    "build_transcript_exemplar_candidates",
]
