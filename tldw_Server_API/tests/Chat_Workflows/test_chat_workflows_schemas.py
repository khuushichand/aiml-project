import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.chat_workflows import (
    ChatWorkflowTemplateStep,
    GenerateDraftRequest,
    StartRunRequest,
    SubmitAnswerRequest,
)


def test_generate_draft_request_requires_goal():
    req = GenerateDraftRequest(
        goal="Plan my migration",
        desired_step_count=4,
        context_refs=[],
    )

    assert req.goal == "Plan my migration"
    assert req.desired_step_count == 4


def test_answer_request_rejects_empty_answer():
    with pytest.raises(ValidationError):
        SubmitAnswerRequest(step_index=0, answer_text="  ")


def test_template_step_normalizes_llm_phrased_question_mode():
    step = ChatWorkflowTemplateStep(
        id="goal",
        step_index=0,
        base_question="What is your goal?",
        question_mode="llm-phrased",
        context_refs=[],
    )

    assert step.question_mode == "llm_phrased"


def test_start_run_request_requires_template_reference():
    with pytest.raises(ValidationError):
        StartRunRequest(selected_context_refs=[])


def test_submit_answer_request_strips_idempotency_key():
    req = SubmitAnswerRequest(
        step_index=0,
        answer_text="Ship a feature",
        idempotency_key="  replay-1  ",
    )

    assert req.idempotency_key == "replay-1"
