import json

import pytest

from tldw_Server_API.app.core.Chat_Workflows.service import ChatWorkflowService
from tldw_Server_API.app.core.DB_Management.ChatWorkflows_DB import ChatWorkflowsDatabase


@pytest.fixture
def fake_chat_workflows_db(tmp_path):
    return ChatWorkflowsDatabase(
        db_path=tmp_path / "chat_workflows.db",
        client_id="test",
    )


def test_start_run_uses_template_snapshot(fake_chat_workflows_db):
    service = ChatWorkflowService(db=fake_chat_workflows_db, question_renderer=None)

    run = service.start_run(
        tenant_id="default",
        user_id="user-1",
        template={
            "id": 10,
            "title": "Discovery",
            "version": 3,
            "steps": [
                {
                    "id": "goal",
                    "step_index": 0,
                    "base_question": "What do you want?",
                    "question_mode": "stock",
                    "context_refs": [],
                }
            ],
        },
        source_mode="saved_template",
        selected_context_refs=[],
    )

    assert run["template_version"] == 3
    assert run["current_step_index"] == 0
    assert json.loads(run["template_snapshot_json"])["steps"][0]["id"] == "goal"


def test_renderer_falls_back_to_base_question_on_error(fake_chat_workflows_db):
    class FailingRenderer:
        async def render_question(self, **kwargs):
            raise RuntimeError("provider offline")

    service = ChatWorkflowService(
        db=fake_chat_workflows_db,
        question_renderer=FailingRenderer(),
    )
    question = service._render_question_sync(
        step={"base_question": "What is your goal?", "question_mode": "llm_phrased"},
        prior_answers=[],
        context_snapshot=[],
    )

    assert question["displayed_question"] == "What is your goal?"
    assert question["fallback_used"] is True


@pytest.mark.asyncio
async def test_get_current_step_reuses_rendered_question(fake_chat_workflows_db):
    class CountingRenderer:
        def __init__(self):
            self.calls = 0

        async def render_question(self, **kwargs):
            self.calls += 1
            return {
                "displayed_question": f"Rendered question #{self.calls}",
                "question_generation_meta": {"calls": self.calls},
                "fallback_used": False,
            }

    renderer = CountingRenderer()
    service = ChatWorkflowService(
        db=fake_chat_workflows_db,
        question_renderer=renderer,
    )
    run = service.start_run(
        tenant_id="default",
        user_id="user-1",
        template={
            "id": 10,
            "title": "Discovery",
            "version": 1,
            "steps": [
                {
                    "id": "goal",
                    "step_index": 0,
                    "base_question": "What do you want?",
                    "question_mode": "llm_phrased",
                    "context_refs": [],
                }
            ],
        },
        source_mode="saved_template",
        selected_context_refs=[],
    )

    first = await service.get_current_step(run["run_id"])
    second = await service.get_current_step(run["run_id"])

    assert first["displayed_question"] == "Rendered question #1"
    assert second["displayed_question"] == "Rendered question #1"
    assert renderer.calls == 1


@pytest.mark.asyncio
async def test_record_answer_completes_run_after_last_step(fake_chat_workflows_db):
    service = ChatWorkflowService(db=fake_chat_workflows_db, question_renderer=None)
    run = service.start_run(
        tenant_id="default",
        user_id="user-1",
        template={
            "id": 10,
            "title": "Discovery",
            "version": 1,
            "steps": [
                {
                    "id": "goal",
                    "step_index": 0,
                    "base_question": "What is your goal?",
                    "question_mode": "stock",
                    "context_refs": [],
                }
            ],
        },
        source_mode="saved_template",
        selected_context_refs=[],
    )

    result = await service.record_answer(
        run_id=run["run_id"],
        step_index=0,
        answer_text="Ship a feature",
    )

    answers = fake_chat_workflows_db.list_answers(run["run_id"])

    assert result["status"] == "completed"
    assert result["current_step_index"] == 1
    assert answers[0]["displayed_question"] == "What is your goal?"


@pytest.mark.asyncio
async def test_record_answer_rejects_stale_step_submission(fake_chat_workflows_db):
    service = ChatWorkflowService(db=fake_chat_workflows_db, question_renderer=None)
    run = service.start_run(
        tenant_id="default",
        user_id="user-1",
        template={
            "id": 10,
            "title": "Discovery",
            "version": 1,
            "steps": [
                {
                    "id": "goal",
                    "step_index": 0,
                    "base_question": "What is your goal?",
                    "question_mode": "stock",
                    "context_refs": [],
                }
            ],
        },
        source_mode="saved_template",
        selected_context_refs=[],
    )

    await service.record_answer(
        run_id=run["run_id"],
        step_index=0,
        answer_text="Ship a feature",
    )

    with pytest.raises(ValueError, match="step submission"):
        await service.record_answer(
            run_id=run["run_id"],
            step_index=0,
            answer_text="Try again",
        )
