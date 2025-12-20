from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint


def test_queue_estimate_sanitizes_base64_payload():
    payload = "data:image/png;base64," + ("a" * 400)
    raw = (
        "{\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"image_url\",\"image_url\":{\"url\":\""
        + payload
        + "\"}}]}]}"
    )

    raw_est = max(1, len(raw) // 4)
    sanitized = chat_endpoint._sanitize_json_for_rate_limit(raw)
    sanitized_est = max(1, len(sanitized) // 4)
    helper_est = chat_endpoint._estimate_tokens_for_queue(raw)

    assert helper_est == sanitized_est
    assert sanitized_est < raw_est
