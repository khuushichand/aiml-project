from tldw_Server_API.app.core.Chat import chat_service


def test_token_estimate_redacts_base64_images():
    base64_payload = "A" * 4000
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_payload}"}},
            ],
        }
    ]
    messages_redacted = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "image_url", "image_url": {"url": "data:image/omitted"}},
            ],
        }
    ]

    est_with_payload = chat_service._estimate_tokens_from_messages(messages)
    est_redacted = chat_service._estimate_tokens_from_messages(messages_redacted)

    assert est_with_payload == est_redacted
