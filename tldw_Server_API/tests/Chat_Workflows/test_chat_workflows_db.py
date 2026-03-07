from concurrent.futures import ThreadPoolExecutor
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


def test_append_event_assigns_unique_sequences_under_concurrency(tmp_path):
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

    with ThreadPoolExecutor(max_workers=8) as executor:
        seqs = list(
            executor.map(
                lambda index: db.append_event(
                    run_id,
                    "test_event",
                    {"index": index},
                ),
                range(20),
            )
        )

    assert sorted(seqs) == list(range(1, 21))
    assert [event["seq"] for event in db.list_events(run_id)] == list(range(1, 21))


def test_replace_template_steps_persists_dialogue_metadata(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")

    template_id = db.create_template(
        tenant_id="default",
        user_id="user-1",
        title="Socratic",
        description=None,
        version=1,
    )

    db.replace_template_steps(
        template_id,
        [
            {
                "id": "debate-step",
                "step_index": 0,
                "step_type": "dialogue_round_step",
                "label": "Socratic Dialogue",
                "base_question": "State your thesis.",
                "question_mode": "stock",
                "dialogue_config": {
                    "goal_prompt": "Test the thesis.",
                    "opening_prompt_mode": "base_question",
                    "user_role_label": "Author",
                    "debate_llm_config": {"provider": "openai", "model": "gpt-4o-mini"},
                    "moderator_llm_config": {"provider": "openai", "model": "gpt-4o-mini"},
                    "max_rounds": 4,
                    "finish_conditions": ["clear compromise"],
                    "context_refs": [],
                    "debate_instruction_prompt": "Challenge weak assumptions.",
                    "moderator_instruction_prompt": "Return structured control output only.",
                },
                "context_refs": [],
            }
        ],
    )

    step = db.get_template(template_id)["steps"][0]

    assert step["step_type"] == "dialogue_round_step"
    assert json.loads(step["dialogue_config_json"])["goal_prompt"] == "Test the thesis."


def test_create_run_exposes_dialogue_runtime_state_columns(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")

    run_id = db.create_run(
        tenant_id="default",
        user_id="user-1",
        template_id=None,
        template_version=1,
        source_mode="generated_draft",
        status="active",
        template_snapshot={
            "steps": [
                {
                    "id": "dialogue-step",
                    "step_type": "dialogue_round_step",
                    "base_question": "State your thesis.",
                }
            ]
        },
        selected_context_refs=[],
        resolved_context_snapshot=[],
    )

    run = db.get_run(run_id)

    assert "active_round_index" in run
    assert "step_runtime_state_json" in run
    assert run["active_round_index"] == 0


def test_chat_workflow_rounds_table_exists(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")

    row = db._conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'chat_workflow_rounds'
        """
    ).fetchone()

    assert row is not None


def test_chat_workflow_runs_schema_includes_dialogue_runtime_columns(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")

    columns = {
        row["name"]
        for row in db._conn.execute("PRAGMA table_info(chat_workflow_runs)").fetchall()
    }

    assert "active_round_index" in columns
    assert "step_runtime_state_json" in columns


def test_chat_workflow_template_steps_schema_includes_dialogue_columns(tmp_path):
    db = ChatWorkflowsDatabase(db_path=tmp_path / "chat_workflows.db", client_id="test")

    columns = {
        row["name"]
        for row in db._conn.execute("PRAGMA table_info(chat_workflow_template_steps)").fetchall()
    }

    assert "step_type" in columns
    assert "dialogue_config_json" in columns
