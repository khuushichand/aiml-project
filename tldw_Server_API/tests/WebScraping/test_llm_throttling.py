from tldw_Server_API.app.core.Chat import chat_service
from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael


def test_llm_throttling_applies_delay(monkeypatch):
    monkeypatch.setenv("LLM_DELAY_MS", "50")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")

    sleeps = []
    monkeypatch.setattr(ael.time, "sleep", lambda value: sleeps.append(value))
    monkeypatch.setattr(ael.time, "time", lambda: 1000.0)

    def _fake_call(**_kwargs):
        return {
            "choices": [{"message": {"content": '{"title": "T", "content": "C"}'}}],
            "usage": {},
            "model": "gpt-test",
        }

    monkeypatch.setattr(chat_service, "perform_chat_api_call", _fake_call)

    html = "<html><body>" + " ".join(["word"] * 80) + "</body></html>"
    result = ael.extract_article_with_pipeline(
        html,
        "https://example.com",
        strategy_order=["llm"],
        llm_settings={
            "provider": "openai",
            "mode": "blocks",
            "chunk_token_threshold": 5,
            "word_token_rate": 1.0,
        },
    )

    assert result["extraction_successful"] is True
    assert any(value >= 0.05 for value in sleeps)


def test_llm_throttling_uses_env_concurrency(monkeypatch):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "3")
    monkeypatch.setenv("LLM_DELAY_MS", "0")

    calls = {"max": None, "acquire": 0, "release": 0}

    class DummySemaphore:
        def acquire(self):
            calls["acquire"] += 1
            return True

        def release(self):
            calls["release"] += 1

    def fake_get(provider, max_concurrency):
        calls["max"] = max_concurrency
        return DummySemaphore()

    monkeypatch.setattr(ael, "_get_llm_semaphore", fake_get)
    monkeypatch.setattr(ael.time, "sleep", lambda _value: None)
    monkeypatch.setattr(ael.time, "time", lambda: 1000.0)

    def _fake_call(**_kwargs):
        return {
            "choices": [{"message": {"content": '{"title": "T", "content": "C"}'}}],
            "usage": {},
            "model": "gpt-test",
        }

    monkeypatch.setattr(chat_service, "perform_chat_api_call", _fake_call)

    html = "<html><body>" + " ".join(["word"] * 80) + "</body></html>"
    result = ael.extract_article_with_pipeline(
        html,
        "https://example.com",
        strategy_order=["llm"],
        llm_settings={
            "provider": "openai",
            "mode": "blocks",
            "chunk_token_threshold": 5,
            "word_token_rate": 1.0,
        },
    )

    assert result["extraction_successful"] is True
    assert calls["max"] == 3
    assert calls["acquire"] >= 1
    assert calls["release"] >= 1
