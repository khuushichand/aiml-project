# test_structured_prompt_assembler.py
# Unit tests for structured prompt assembly and legacy rendering

import pytest

from tldw_Server_API.app.core.Prompt_Management.structured_prompts.assembler import (
    StructuredPromptAssemblyError,
    assemble_prompt_definition,
)


def _make_definition(**overrides):
    definition = {
        "schema_version": 1,
        "format": "structured",
        "variables": [
            {
                "name": "topic",
                "label": "Topic",
                "required": True,
                "input_type": "textarea",
            }
        ],
        "blocks": [
            {
                "id": "identity",
                "name": "Identity",
                "role": "system",
                "content": "You are precise.",
                "enabled": True,
                "order": 10,
                "is_template": False,
            },
            {
                "id": "task",
                "name": "Task",
                "role": "user",
                "content": "Summarize {{topic}}",
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
    definition.update(overrides)
    return definition


def test_assembler_returns_canonical_messages_and_legacy_snapshot():
    result = assemble_prompt_definition(_make_definition(), {"topic": "SQLite FTS"})

    assert result.messages == [
        {"role": "system", "content": "You are precise."},
        {"role": "user", "content": "Summarize SQLite FTS"},
    ]
    assert result.legacy.system_prompt == "You are precise."
    assert result.legacy.user_prompt == "Summarize SQLite FTS"


def test_assembler_raises_when_required_variable_missing():
    with pytest.raises(StructuredPromptAssemblyError) as exc_info:
        assemble_prompt_definition(_make_definition(), {})

    assert exc_info.value.code == "missing_required_variable"
    assert exc_info.value.variable_name == "topic"


def test_assembler_inserts_few_shot_examples_and_modules_at_fixed_points():
    result = assemble_prompt_definition(
        _make_definition(),
        {"topic": "SQLite FTS"},
        extras={
            "few_shot_examples": [
                {
                    "inputs": {"topic": "Indexes"},
                    "outputs": {"answer": "Use the covering index."},
                }
            ],
            "modules_config": [
                {"type": "style_rules", "enabled": True, "config": {"tone": "concise"}}
            ],
        },
    )

    assert [message["role"] for message in result.messages] == [
        "system",
        "developer",
        "user",
        "assistant",
        "user",
    ]
    assert result.messages[1]["content"] == "Module style_rules: tone=concise"
    assert result.messages[2]["content"] == 'Example input: {"topic": "Indexes"}'
    assert result.messages[3]["content"] == 'Example output: {"answer": "Use the covering index."}'
    assert result.messages[4]["content"] == "Summarize SQLite FTS"
    assert "Module style_rules: tone=concise" in result.legacy.system_prompt
    assert 'Example input: {"topic": "Indexes"}' in result.legacy.user_prompt
    assert "Summarize SQLite FTS" in result.legacy.user_prompt
