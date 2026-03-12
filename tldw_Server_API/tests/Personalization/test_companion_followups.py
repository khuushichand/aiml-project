from __future__ import annotations

import importlib
import importlib.util

import pytest


pytestmark = pytest.mark.unit


def test_build_companion_conversation_prompts_prefers_relevant_delivered_reflection() -> None:
    module_path = "tldw_Server_API.app.core.Personalization.companion_followups"
    assert importlib.util.find_spec(module_path) is not None
    module = importlib.import_module(module_path)
    assert hasattr(module, "build_companion_conversation_prompts")

    payload = module.build_companion_conversation_prompts(
        query="help me decide the next step on backlog review",
        delivered_reflections=[
            {
                "id": "reflection-1",
                "summary": "You returned to backlog review and identified a stalled next step.",
                "theme_key": "backlog-review",
                "signal_strength": 4.0,
                "follow_up_prompts": [
                    {
                        "prompt_id": "prompt-1",
                        "label": "Next concrete step",
                        "prompt_text": "What is the next concrete step for backlog review?",
                        "prompt_type": "clarify_priority",
                        "source_reflection_id": "reflection-1",
                        "source_evidence_ids": ["evt-1"],
                    }
                ],
            }
        ],
        suppressed_reflections=[],
        context_cards=[],
        context_goals=[],
        context_activity=[],
    )

    assert payload["prompt_source_kind"] == "reflection"
    assert payload["prompt_source_id"] == "reflection-1"
    assert payload["prompts"][0]["source_reflection_id"] == "reflection-1"
