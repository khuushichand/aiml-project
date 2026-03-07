import json

from tldw_Server_API.app.core.DB_Management import DB_Manager
from tldw_Server_API.app.core.DB_Management.ChatWorkflows_DB import (
    ChatWorkflowsDatabase,
)


def test_chat_workflows_db_persists_template_and_run_snapshot(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")

    template_id = db.create_template(
        tenant_id="default",
        user_id="user-1",
        title="Discovery Interview",
        description="Collect onboarding answers",
        version=1,
    )

    db.replace_template_steps(
        template_id,
        [
            {
                "step_index": 0,
                "label": "Goal",
                "base_question": "What outcome do you want?",
                "question_mode": "stock",
                "context_refs_json": "[]",
            }
        ],
    )

    run_id = db.create_run(
        tenant_id="default",
        user_id="user-1",
        template_id=template_id,
        template_version=1,
        source_mode="saved_template",
        status="active",
        template_snapshot={
            "title": "Discovery Interview",
            "steps": [{"base_question": "What outcome do you want?"}],
        },
        selected_context_refs=[],
        resolved_context_snapshot=[],
    )

    run = db.get_run(run_id)

    assert run["template_version"] == 1
    assert (
        json.loads(run["template_snapshot_json"])["steps"][0]["base_question"]
        == "What outcome do you want?"
    )


def test_add_answer_is_unique_per_run_step(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")

    run_id = db.create_run(
        tenant_id="default",
        user_id="user-1",
        template_id=None,
        template_version=1,
        source_mode="generated_draft",
        status="active",
        template_snapshot={"steps": [{"id": "step-1", "base_question": "Why?"}]},
        selected_context_refs=[],
        resolved_context_snapshot=[],
    )

    db.add_answer(
        run_id=run_id,
        step_id="step-1",
        step_index=0,
        displayed_question="Why?",
        answer_text="Because.",
        question_generation_meta={},
    )

    answers = db.list_answers(run_id)

    assert len(answers) == 1
    assert answers[0]["answer_text"] == "Because."


def test_create_chat_workflows_database_uses_explicit_db_path(tmp_path):
    db = DB_Manager.create_chat_workflows_database(
        client_id="factory-test",
        db_path=tmp_path / "factory_chat_workflows.db",
    )

    assert isinstance(db, ChatWorkflowsDatabase)
    assert db.db_path == str(tmp_path / "factory_chat_workflows.db")
