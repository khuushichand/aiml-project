"""
Integration tests for structured prompt support in the regular Prompts API.
"""

import pytest

pytestmark = pytest.mark.integration


def _make_prompt_definition_payload() -> dict:
    return {
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


def test_create_structured_prompt_persists_definition_and_format(test_client, auth_headers):
    payload = {
        "name": "Structured Summarizer",
        "author": "integration-test",
        "prompt_format": "structured",
        "prompt_schema_version": 1,
        "prompt_definition": _make_prompt_definition_payload(),
        "keywords": ["summary"],
    }

    create_response = test_client.post(
        "/api/v1/prompts",
        json=payload,
        headers=auth_headers,
    )

    assert create_response.status_code == 201, create_response.text
    created_body = create_response.json()
    assert created_body["prompt_format"] == "structured"
    assert created_body["prompt_schema_version"] == 1
    assert created_body["prompt_definition"]["schema_version"] == 1

    prompt_id = created_body["id"]
    get_response = test_client.get(
        f"/api/v1/prompts/{prompt_id}",
        headers=auth_headers,
    )

    assert get_response.status_code == 200, get_response.text
    fetched_body = get_response.json()
    assert fetched_body["prompt_format"] == "structured"
    assert fetched_body["prompt_schema_version"] == 1
    assert fetched_body["prompt_definition"]["blocks"][1]["content"] == "Summarize {{topic}}"


def test_update_structured_prompt_preserves_format_when_prompt_format_is_omitted(
    test_client,
    auth_headers,
):
    create_response = test_client.post(
        "/api/v1/prompts",
        json={
            "name": "Structured Evaluator",
            "author": "integration-test",
            "prompt_format": "structured",
            "prompt_schema_version": 1,
            "prompt_definition": _make_prompt_definition_payload(),
            "keywords": ["evaluate"],
        },
        headers=auth_headers,
    )

    assert create_response.status_code == 201, create_response.text
    created_body = create_response.json()
    updated_definition = _make_prompt_definition_payload()
    updated_definition["blocks"][1]["content"] = "Evaluate {{topic}} carefully."

    update_response = test_client.put(
        f"/api/v1/prompts/{created_body['id']}",
        json={
            "name": created_body["name"],
            "author": created_body["author"],
            "prompt_schema_version": 1,
            "prompt_definition": updated_definition,
            "keywords": created_body["keywords"],
        },
        headers=auth_headers,
    )

    assert update_response.status_code == 200, update_response.text
    updated_body = update_response.json()
    assert updated_body["prompt_format"] == "structured"
    assert updated_body["prompt_definition"]["blocks"][1]["content"] == "Evaluate {{topic}} carefully."


def test_preview_prompt_returns_assembled_messages_and_legacy_snapshot(test_client, auth_headers):
    response = test_client.post(
        "/api/v1/prompts/preview",
        json={
            "prompt_format": "structured",
            "prompt_schema_version": 1,
            "prompt_definition": _make_prompt_definition_payload(),
            "variables": {"topic": "SQLite FTS"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assembled_messages"] == [
        {"role": "system", "content": "You are precise."},
        {"role": "user", "content": "Summarize SQLite FTS"},
    ]
    assert body["legacy_system_prompt"] == "You are precise."
    assert body["legacy_user_prompt"] == "Summarize SQLite FTS"


def test_convert_prompt_returns_structured_definition_with_normalized_variables(test_client, auth_headers):
    response = test_client.post(
        "/api/v1/prompts/convert",
        json={
            "system_prompt": "Be precise about {topic}.",
            "user_prompt": "Summarize $topic against <baseline> in {{style}}.",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prompt_format"] == "structured"
    assert body["prompt_schema_version"] == 1
    assert body["extracted_variables"] == ["topic", "baseline", "style"]
    assert body["prompt_definition"]["blocks"][0]["content"] == "Be precise about {{topic}}."
    assert body["prompt_definition"]["blocks"][1]["content"] == (
        "Summarize {{topic}} against {{baseline}} in {{style}}."
    )
