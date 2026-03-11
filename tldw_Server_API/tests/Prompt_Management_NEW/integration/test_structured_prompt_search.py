"""
Integration tests for structured prompt search indexing.
"""

import pytest

pytestmark = pytest.mark.integration


def _make_prompt_definition_payload() -> dict:
    return {
        "schema_version": 1,
        "format": "structured",
        "variables": [
            {
                "name": "text",
                "label": "Text",
                "required": True,
                "input_type": "textarea",
            }
        ],
        "blocks": [
            {
                "id": "identity",
                "name": "Identity",
                "role": "system",
                "content": "You are a classifier.",
                "enabled": True,
                "order": 10,
                "is_template": False,
            },
            {
                "id": "task",
                "name": "Task",
                "role": "user",
                "content": "Classify {{text}} by sentiment.",
                "enabled": True,
                "order": 20,
                "is_template": True,
            },
            {
                "id": "rubric",
                "name": "Rubric",
                "role": "assistant",
                "content": "Use the mauveflint verdict label when sentiment is mixed.",
                "enabled": True,
                "order": 30,
                "is_template": False,
            },
        ],
    }


def test_structured_prompt_search_indexes_enabled_block_content(
    test_client,
    auth_headers,
):
    create_response = test_client.post(
        "/api/v1/prompts",
        json={
            "name": "Structured Classifier",
            "author": "integration-test",
            "prompt_format": "structured",
            "prompt_schema_version": 1,
            "prompt_definition": _make_prompt_definition_payload(),
            "keywords": ["classification"],
        },
        headers=auth_headers,
    )

    assert create_response.status_code == 201, create_response.text

    search_response = test_client.post(
        "/api/v1/prompts/search",
        params={"search_query": "mauveflint"},
        headers=auth_headers,
    )

    assert search_response.status_code == 200, search_response.text
    body = search_response.json()
    assert body["total_matches"] == 1
    assert body["items"][0]["name"] == "Structured Classifier"
