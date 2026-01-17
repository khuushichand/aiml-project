import json

from tldw_Server_API.app.core.Chat import chat_service
from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael


def test_generate_regex_pattern_from_llm(monkeypatch):
    html = "<html><body>Order #12345 confirmed.</body></html>"
    payload = json.dumps({"pattern": r"Order\s+#(\d+)", "flags": "i", "group": 1})

    def _fake_call(**_kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": payload,
                    }
                }
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
            "model": "gpt-test",
        }

    monkeypatch.setattr(chat_service, "perform_chat_api_call", _fake_call)

    result = ael.generate_regex_pattern_from_llm(
        html,
        "https://example.com",
        label="order_id",
        query="Find order IDs",
        llm_settings={"provider": "openai"},
    )

    assert result["success"] is True
    assert result["pattern"] == r"Order\s+#(\d+)"
    assert result.get("sample_match") == "12345"
