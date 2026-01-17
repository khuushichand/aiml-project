from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files as audio_files


@pytest.mark.unit
def test_download_youtube_audio_uses_unique_paths(tmp_path, monkeypatch):
    def fake_evaluate_url_policy(*_args, **_kwargs):
        return SimpleNamespace(allowed=True, reason=None)

    monkeypatch.setattr(audio_files, "evaluate_url_policy", fake_evaluate_url_policy)

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _url, download=False):
            return {"title": "Same Title", "id": "abc123"}

        def download(self, _urls):
            outtmpl = self.opts.get("outtmpl")
            if not outtmpl:
                return
            target = Path(outtmpl.replace("%(ext)s", "mp3"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fake-audio")

    monkeypatch.setattr(audio_files.yt_dlp, "YoutubeDL", FakeYDL)

    path_one, _ = audio_files.download_youtube_audio(
        "https://youtube.com/watch?v=abc123",
        output_dir=tmp_path,
    )
    path_two, _ = audio_files.download_youtube_audio(
        "https://youtube.com/watch?v=abc123",
        output_dir=tmp_path,
    )

    assert path_one != path_two
    assert Path(path_one).exists()
    assert Path(path_two).exists()
    assert Path(path_one).parent == tmp_path
    assert Path(path_two).parent == tmp_path
