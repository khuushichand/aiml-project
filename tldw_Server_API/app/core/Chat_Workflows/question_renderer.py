from __future__ import annotations

from typing import Any


class ChatWorkflowQuestionRenderer:
    """Minimal question renderer for chat workflow steps."""

    async def render_question(
        self,
        *,
        base_question: str,
        phrasing_instructions: str | None,
        prior_answers: list[dict[str, Any]],
        context_snapshot: list[dict[str, Any]] | list[Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        return {
            "displayed_question": base_question,
            "question_generation_meta": {
                "model": model,
                "phrasing_instructions": bool(phrasing_instructions),
                "prior_answer_count": len(prior_answers),
                "context_item_count": len(context_snapshot),
            },
            "fallback_used": False,
        }
