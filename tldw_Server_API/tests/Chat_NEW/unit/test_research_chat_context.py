"""Unit tests for deep research chat context prompt assembly."""

import copy

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.Chat.chat_service import inject_research_context_into_prompt


def _research_context_payload() -> dict:
    return {
        "run_id": "run_123",
        "query": "battery recycling supply chain",
        "question": "What changed in the battery recycling market?",
        "outline": [{"title": "Overview"}],
        "key_claims": [{"text": "Claim one"}],
        "unresolved_questions": ["What changed in Europe?"],
        "verification_summary": {"unsupported_claim_count": 0},
        "source_trust_summary": {"high_trust_count": 3},
        "research_url": "/research?run=run_123",
    }


def test_inject_research_context_into_prompt_keeps_transcript_payload_untouched():
    """Research context should become model-side prompt context, not transcript content."""
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Use the attached research."}],
        research_context=_research_context_payload(),
    )
    templated_llm_payload = [{"role": "user", "content": "Use the attached research."}]
    payload_before = copy.deepcopy(templated_llm_payload)

    final_system_message, model_payload = inject_research_context_into_prompt(
        final_system_message="Base instructions.",
        templated_llm_payload=templated_llm_payload,
        research_context=request.research_context,
    )

    assert "battery recycling supply chain" in final_system_message
    assert "Claim one" in final_system_message
    assert "What changed in Europe?" in final_system_message
    assert model_payload == payload_before
    assert templated_llm_payload == payload_before
