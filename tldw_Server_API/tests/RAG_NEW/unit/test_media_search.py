import pytest

from tldw_Server_API.app.core.RAG.rag_service import media_search as ms


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_search_images_uses_to_thread_and_returns_normalized_results(monkeypatch):
    import tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs as web_apis

    captured: dict[str, object] = {"to_thread_calls": 0}

    async def _fake_reformulate_query(_query, _system, _provider, _model):  # noqa: ANN001
        return "KFC logo"

    def _fake_perform_websearch(**kwargs):  # noqa: ANN003
        captured["search_kwargs"] = kwargs
        return {
            "results": [
                {
                    "title": "KFC Logo",
                    "url": "https://example.com/kfc-logo",
                    "thumbnail": "https://example.com/kfc-logo-thumb.jpg",
                    "snippet": "Official KFC logo image",
                }
            ]
        }

    async def _fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        captured["to_thread_calls"] = int(captured["to_thread_calls"]) + 1
        captured["to_thread_func"] = getattr(func, "__name__", str(func))
        return func(*args, **kwargs)

    monkeypatch.setattr(ms, "_reformulate_query", _fake_reformulate_query)
    monkeypatch.setattr(web_apis, "perform_websearch", _fake_perform_websearch)
    monkeypatch.setattr(ms.asyncio, "to_thread", _fake_to_thread)

    images = await ms.search_images(
        query="What does the KFC logo look like?",
        max_results=1,
    )

    assert captured["to_thread_calls"] == 1
    assert captured["to_thread_func"] == "_fake_perform_websearch"
    assert captured["search_kwargs"]["search_query"] == "KFC logo images"
    assert len(images) == 1
    assert images[0]["title"] == "KFC Logo"
    assert images[0]["url"] == "https://example.com/kfc-logo"
    assert images[0]["thumbnail_url"] == "https://example.com/kfc-logo-thumb.jpg"


@pytest.mark.asyncio
async def test_search_videos_uses_to_thread_and_builds_youtube_thumbnail(monkeypatch):
    import tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs as web_apis

    captured: dict[str, object] = {"to_thread_calls": 0}

    async def _fake_reformulate_query(_query, _system, _provider, _model):  # noqa: ANN001
        return "python beginner tutorial"

    def _fake_perform_websearch(**kwargs):  # noqa: ANN003
        captured["search_kwargs"] = kwargs
        return {
            "results": [
                {
                    "title": "Python Beginner Tutorial",
                    "url": "https://www.youtube.com/watch?v=abcdefghijk",
                    "snippet": "Learn Python step by step.",
                }
            ]
        }

    async def _fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        captured["to_thread_calls"] = int(captured["to_thread_calls"]) + 1
        captured["to_thread_func"] = getattr(func, "__name__", str(func))
        return func(*args, **kwargs)

    monkeypatch.setattr(ms, "_reformulate_query", _fake_reformulate_query)
    monkeypatch.setattr(web_apis, "perform_websearch", _fake_perform_websearch)
    monkeypatch.setattr(ms.asyncio, "to_thread", _fake_to_thread)

    videos = await ms.search_videos(
        query="How do I learn Python?",
        max_results=1,
    )

    assert captured["to_thread_calls"] == 1
    assert captured["to_thread_func"] == "_fake_perform_websearch"
    assert captured["search_kwargs"]["search_query"] == "site:youtube.com python beginner tutorial"
    assert len(videos) == 1
    assert videos[0]["source"] == "youtube"
    assert videos[0]["thumbnail_url"] == "https://img.youtube.com/vi/abcdefghijk/mqdefault.jpg"
