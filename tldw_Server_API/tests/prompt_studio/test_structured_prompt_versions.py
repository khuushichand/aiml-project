import pytest

from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import InputError, PromptStudioDatabase


def _make_prompt_definition_payload(task_text: str = "Evaluate {{input}}") -> dict:
    return {
        "schema_version": 1,
        "format": "structured",
        "variables": [
            {
                "name": "input",
                "label": "Input",
                "required": True,
                "input_type": "textarea",
            }
        ],
        "blocks": [
            {
                "id": "identity",
                "name": "Identity",
                "role": "system",
                "content": "You are a careful evaluator.",
                "enabled": True,
                "order": 10,
                "is_template": False,
            },
            {
                "id": "task",
                "name": "Task",
                "role": "user",
                "content": task_text,
                "enabled": True,
                "order": 20,
                "is_template": True,
            },
        ],
        "assembly_config": {
            "legacy_system_roles": ["system", "developer"],
            "legacy_user_roles": ["user"],
            "block_separator": "\n\n",
        },
    }


def test_prompt_studio_update_creates_new_structured_prompt_version(
    isolated_db: PromptStudioDatabase,
):
    project = isolated_db.create_project(name="Structured Prompt Project", user_id="test-user")
    created = isolated_db.create_prompt(
        project_id=project["id"],
        name="Structured Evaluator",
        version_number=1,
        prompt_format="structured",
        prompt_schema_version=1,
        prompt_definition=_make_prompt_definition_payload(),
        client_id="test-client",
    )

    updated = isolated_db.create_prompt_version(
        created["id"],
        change_description="Adjust instructions",
        prompt_definition=_make_prompt_definition_payload("Evaluate {{input}} carefully."),
        client_id="test-client",
    )

    assert updated["version_number"] == 2
    assert updated["prompt_format"] == "structured"
    assert updated["prompt_definition"]["blocks"][1]["content"] == "Evaluate {{input}} carefully."


def test_prompt_studio_rejects_schema_version_mismatch(
    isolated_db: PromptStudioDatabase,
):
    project = isolated_db.create_project(name="Structured Prompt Project", user_id="test-user")

    with pytest.raises(InputError, match="must match prompt_definition.schema_version"):
        isolated_db.create_prompt(
            project_id=project["id"],
            name="Structured Evaluator",
            version_number=1,
            prompt_format="structured",
            prompt_schema_version=999,
            prompt_definition=_make_prompt_definition_payload(),
            client_id="test-client",
        )
