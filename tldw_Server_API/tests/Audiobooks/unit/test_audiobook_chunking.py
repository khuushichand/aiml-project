import pytest

from tldw_Server_API.app.services import audiobook_jobs_worker

pytestmark = pytest.mark.unit


def test_get_chapter_chunk_max_chars_uses_chapter_env(monkeypatch):
    monkeypatch.setattr(audiobook_jobs_worker, "get_config_value", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AUDIOBOOK_CHAPTER_MAX_CHARS", "512")
    monkeypatch.delenv("AUDIOBOOK_MAX_CHARS", raising=False)

    assert audiobook_jobs_worker._get_chapter_chunk_max_chars() == 512


def test_get_chapter_chunk_max_chars_falls_back_to_max_chars(monkeypatch):
    monkeypatch.setattr(audiobook_jobs_worker, "get_config_value", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("AUDIOBOOK_CHAPTER_MAX_CHARS", raising=False)
    monkeypatch.setenv("AUDIOBOOK_MAX_CHARS", "256")

    assert audiobook_jobs_worker._get_chapter_chunk_max_chars() == 256


def test_get_chapter_chunk_max_chars_returns_none_on_invalid(monkeypatch):
    monkeypatch.setattr(audiobook_jobs_worker, "get_config_value", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("AUDIOBOOK_CHAPTER_MAX_CHARS", "nope")

    assert audiobook_jobs_worker._get_chapter_chunk_max_chars() is None


def test_split_text_by_max_chars_respects_limit():
    text = "Hello world. Again here. And once more."
    segments = audiobook_jobs_worker._split_text_by_max_chars(text, 15)

    assert segments
    assert "".join(segment.text for segment in segments) == text
    assert all(segment.text for segment in segments)
    assert all(len(segment.text) <= 15 for segment in segments)


def test_split_text_by_max_chars_prefers_sentence_boundary():
    text = "Hello world. Again here."
    segments = audiobook_jobs_worker._split_text_by_max_chars(text, 13)

    assert len(segments) == 2
    assert segments[0].text == "Hello world. "
    assert segments[1].text == "Again here."
