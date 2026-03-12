from tldw_Server_API.app.core.Workflows.capabilities import get_step_capability


def test_webhook_steps_default_to_unsafe_replay():
    capability = get_step_capability("webhook")

    assert capability.replay_safe is False
    assert capability.requires_human_review_for_rerun is True
    assert capability.idempotency_strategy == "external"


def test_prompt_steps_expose_safe_replay_defaults():
    capability = get_step_capability("prompt")

    assert capability.replay_safe is True
    assert capability.idempotency_strategy == "run_scoped"
    assert capability.compensation_supported is False


def test_step_types_endpoint_includes_capability_metadata(client_user_only):
    response = client_user_only.get("/api/v1/workflows/step-types")

    assert response.status_code == 200
    prompt = next(item for item in response.json() if item["name"] == "prompt")
    webhook = next(item for item in response.json() if item["name"] == "webhook")

    assert prompt["capabilities"]["replay_safe"] is True
    assert prompt["capabilities"]["idempotency_strategy"] == "run_scoped"
    assert webhook["capabilities"]["replay_safe"] is False
    assert webhook["capabilities"]["requires_human_review_for_rerun"] is True
