from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files as audio_files


@pytest.mark.unit
def test_download_audio_file_blocks_disallowed_url(monkeypatch, tmp_path):
     def fake_evaluate_url_policy(*_args, **_kwargs):
        return SimpleNamespace(allowed=False, reason="blocked")

    monkeypatch.setattr(audio_files, "evaluate_url_policy", fake_evaluate_url_policy)

    with pytest.raises(audio_files.AudioDownloadError) as exc:
        audio_files.download_audio_file("https://example.com/file.mp3", str(tmp_path))

    assert "blocked" in str(exc.value)


@pytest.mark.unit
def test_download_youtube_audio_blocks_disallowed_url(monkeypatch):
     def fake_evaluate_url_policy(*_args, **_kwargs):
        return SimpleNamespace(allowed=False, reason="blocked")

    monkeypatch.setattr(audio_files, "evaluate_url_policy", fake_evaluate_url_policy)

    path, message = audio_files.download_youtube_audio("https://example.com/watch?v=123")

    assert path is None
    assert "blocked" in message
