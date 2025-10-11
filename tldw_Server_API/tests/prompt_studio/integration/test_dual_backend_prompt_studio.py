"""Dual-backend regression covering Prompt Studio project/prompt CRUD flows."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "project_payload",
    [
        {
            "name": "Dual Backend Project",
            "description": "Ensures Prompt Studio projects work across backends",
            "status": "draft",
            "metadata": {"source": "test"},
        }
    ],
)
@pytest.mark.integration
def test_project_and_prompt_flow_across_backends(
    prompt_studio_dual_backend_client,
    project_payload,
):
    backend_label, client, _db = prompt_studio_dual_backend_client

    # Create a project
    project_response = client.post("/api/v1/prompt-studio/projects/", json=project_payload)
    assert project_response.status_code == 201, project_response.text
    project_body = project_response.json()
    assert project_body["success"] is True
    project_id = project_body["data"]["id"]

    # Create a prompt in that project
    prompt_payload = {
        "project_id": project_id,
        "name": f"Intro Prompt ({backend_label})",
        "system_prompt": "Summarize the input text.",
        "user_prompt": "{{text}}",
    }
    prompt_response = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json=prompt_payload,
    )
    assert prompt_response.status_code == 201, prompt_response.text
    prompt_body = prompt_response.json()
    assert prompt_body["success"] is True
    created_prompt = prompt_body["data"]
    assert created_prompt["project_id"] == project_id
    assert created_prompt["name"] == prompt_payload["name"]

    # List prompts to confirm retrieval works on the selected backend
    list_response = client.get(
        "/api/v1/prompt-studio/prompts",
        params={"project_id": project_id},
    )
    assert list_response.status_code == 200, list_response.text
    prompts_payload = list_response.json()
    assert prompts_payload["success"] is True
    assert prompts_payload["metadata"]["total"] >= 1

    names = {prompt["name"] for prompt in prompts_payload["data"]}
    assert prompt_payload["name"] in names

    # Fetch the prompt directly
    prompt_id = created_prompt["id"]
    get_response = client.get(f"/api/v1/prompt-studio/prompts/get/{prompt_id}")
    assert get_response.status_code == 200, get_response.text
    prompt_detail = get_response.json()
    assert prompt_detail["success"] is True
    assert prompt_detail["data"]["id"] == prompt_id
    assert prompt_detail["data"]["project_id"] == project_id

    # Update the project to verify write paths on both backends
    update_payload = {"description": f"Updated via {backend_label}", "status": "active"}
    update_response = client.put(
        f"/api/v1/prompt-studio/projects/update/{project_id}",
        json=update_payload,
    )
    assert update_response.status_code == 200, update_response.text
    updated_project = update_response.json()["data"]
    assert updated_project["description"] == update_payload["description"]
    assert updated_project["status"] == "active"
