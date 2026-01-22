from tldw_Server_API.app.core.LLM_Calls.providers.local_adapters import _extract_text_from_message_content


def test_extract_text_from_message_content_handles_non_dict_parts():
    content = [
        {"type": "text", "text": "hello"},
        "world",
        123,
        {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
    ]
    out = _extract_text_from_message_content(content, "LocalAdapterTest", 0)
    assert "hello" in out
    assert "world" in out
