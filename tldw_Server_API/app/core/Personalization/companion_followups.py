from __future__ import annotations

"""Deterministic follow-up prompt sourcing for companion conversations."""

import re
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MAX_PROMPTS = 3
_SUPPRESSED_SIGNAL_THRESHOLD = 3.0


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _tokenize(value: Any) -> set[str]:
    return {token for token in _TOKEN_RE.findall(_normalize_text(value)) if len(token) >= 2}


def _score_text(query_tokens: set[str], value: Any) -> float:
    if not query_tokens:
        return 0.0
    normalized_text = _normalize_text(value)
    if not normalized_text:
        return 0.0
    candidate_tokens = _tokenize(normalized_text)
    overlap = query_tokens & candidate_tokens
    if not overlap:
        return 0.0
    return float(len(overlap)) + (len(overlap) / max(len(candidate_tokens), 1))


def _build_reflection_text(reflection: dict[str, Any]) -> str:
    prompt_text = " ".join(
        str(prompt.get("prompt_text") or "").strip()
        for prompt in list(reflection.get("follow_up_prompts") or [])
        if isinstance(prompt, dict)
    )
    return " ".join(
        fragment
        for fragment in (
            reflection.get("summary"),
            reflection.get("theme_key"),
            prompt_text,
        )
        if fragment
    )


def _normalize_prompt(
    prompt: dict[str, Any],
    *,
    source_reflection_id: str | None,
) -> dict[str, Any]:
    normalized = dict(prompt)
    if source_reflection_id and not normalized.get("source_reflection_id"):
        normalized["source_reflection_id"] = source_reflection_id
    if "source_evidence_ids" not in normalized or normalized["source_evidence_ids"] is None:
        normalized["source_evidence_ids"] = []
    return normalized


def _rank_reflections(
    reflections: list[dict[str, Any]],
    *,
    query: str | None,
) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, reflection in enumerate(reflections):
        prompts = list(reflection.get("follow_up_prompts") or [])
        if not prompts:
            continue
        score = _score_text(query_tokens, _build_reflection_text(reflection))
        if score <= 0 and query_tokens:
            continue
        if score <= 0:
            score = float(reflection.get("signal_strength") or 0.0)
        scored.append((score, index, reflection))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [reflection for _score, _index, reflection in scored]


def _build_context_prompts(
    *,
    context_cards: list[dict[str, Any]],
    context_goals: list[dict[str, Any]],
    context_activity: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    if context_goals:
        lead_goal = context_goals[0]
        prompts.append(
            {
                "prompt_id": f"goal-next-step:{lead_goal.get('id') or 'goal'}",
                "label": "Next concrete step",
                "prompt_text": f"What is the next concrete step for {lead_goal.get('title') or 'this goal'}?",
                "prompt_type": "clarify_priority",
                "source_reflection_id": None,
                "source_evidence_ids": [str(lead_goal.get("id") or "")] if lead_goal.get("id") else [],
            }
        )
        prompts.append(
            {
                "prompt_id": f"goal-blocker:{lead_goal.get('id') or 'goal'}",
                "label": "Check blockers",
                "prompt_text": f"What is blocking progress on {lead_goal.get('title') or 'this goal'}?",
                "prompt_type": "unblock",
                "source_reflection_id": None,
                "source_evidence_ids": [str(lead_goal.get("id") or "")] if lead_goal.get("id") else [],
            }
        )
    elif context_cards:
        lead_card = context_cards[0]
        prompts.append(
            {
                "prompt_id": f"card-focus:{lead_card.get('id') or 'card'}",
                "label": "Focus this next",
                "prompt_text": f"What should I focus on next about {lead_card.get('title') or 'this topic'}?",
                "prompt_type": "clarify_priority",
                "source_reflection_id": None,
                "source_evidence_ids": [str(lead_card.get("id") or "")] if lead_card.get("id") else [],
            }
        )
        prompts.append(
            {
                "prompt_id": f"card-narrow:{lead_card.get('id') or 'card'}",
                "label": "Narrow scope",
                "prompt_text": f"How can we narrow the scope around {lead_card.get('title') or 'this topic'}?",
                "prompt_type": "narrow_focus",
                "source_reflection_id": None,
                "source_evidence_ids": [str(lead_card.get("id") or "")] if lead_card.get("id") else [],
            }
        )
    elif context_activity:
        lead_event = context_activity[0]
        subject = (
            str((lead_event.get("metadata") or {}).get("title") or "").strip()
            or str(lead_event.get("source_type") or "this activity").strip()
        )
        prompts.append(
            {
                "prompt_id": f"activity-next-step:{lead_event.get('id') or 'activity'}",
                "label": "Continue from this",
                "prompt_text": f"What is the next step after {subject}?",
                "prompt_type": "clarify_priority",
                "source_reflection_id": None,
                "source_evidence_ids": [str(lead_event.get("id") or "")] if lead_event.get("id") else [],
            }
        )
    return prompts[:_MAX_PROMPTS]


def build_companion_conversation_prompts(
    *,
    query: str | None,
    delivered_reflections: list[dict[str, Any]],
    suppressed_reflections: list[dict[str, Any]],
    context_cards: list[dict[str, Any]],
    context_goals: list[dict[str, Any]],
    context_activity: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic prompt source payload for companion conversation."""
    ranked_delivered = _rank_reflections(delivered_reflections, query=query)
    if ranked_delivered:
        reflection = ranked_delivered[0]
        reflection_id = str(reflection.get("id") or "")
        prompts = [
            _normalize_prompt(prompt, source_reflection_id=reflection_id)
            for prompt in list(reflection.get("follow_up_prompts") or [])[:_MAX_PROMPTS]
            if isinstance(prompt, dict) and str(prompt.get("prompt_text") or "").strip()
        ]
        return {
            "prompt_source_kind": "reflection",
            "prompt_source_id": reflection_id,
            "prompts": prompts,
        }

    eligible_suppressed = [
        reflection
        for reflection in suppressed_reflections
        if float(reflection.get("signal_strength") or 0.0) >= _SUPPRESSED_SIGNAL_THRESHOLD
    ]
    ranked_suppressed = _rank_reflections(eligible_suppressed, query=query)
    if ranked_suppressed:
        reflection = ranked_suppressed[0]
        reflection_id = str(reflection.get("id") or "")
        prompts = [
            _normalize_prompt(prompt, source_reflection_id=reflection_id)
            for prompt in list(reflection.get("follow_up_prompts") or [])[:_MAX_PROMPTS]
            if isinstance(prompt, dict) and str(prompt.get("prompt_text") or "").strip()
        ]
        return {
            "prompt_source_kind": "suppressed_reflection",
            "prompt_source_id": reflection_id,
            "prompts": prompts,
        }

    if context_goals:
        prompt_source_kind = "goal"
        prompt_source_id = str(context_goals[0].get("id") or "")
    elif context_cards:
        prompt_source_kind = "knowledge_card"
        prompt_source_id = str(context_cards[0].get("id") or "")
    elif context_activity:
        prompt_source_kind = "activity"
        prompt_source_id = str(context_activity[0].get("id") or "")
    else:
        prompt_source_kind = "none"
        prompt_source_id = None
    return {
        "prompt_source_kind": prompt_source_kind,
        "prompt_source_id": prompt_source_id,
        "prompts": _build_context_prompts(
            context_cards=context_cards,
            context_goals=context_goals,
            context_activity=context_activity,
        ),
    }


__all__ = ["build_companion_conversation_prompts"]
