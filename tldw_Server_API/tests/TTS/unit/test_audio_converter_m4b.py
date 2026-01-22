import pytest

from tldw_Server_API.app.core.TTS.audio_converter import AudioConverter

pytestmark = pytest.mark.unit


def test_build_ffmetadata_includes_chapters_and_metadata():
    meta = AudioConverter._build_ffmetadata(
        ["Intro"],
        [1000, 2000],
        {"title": "My Book", "artist": "Author"},
    )
    assert meta.startswith(";FFMETADATA1")
    assert "title=My Book" in meta
    assert "artist=Author" in meta
    assert meta.count("[CHAPTER]") == 2
    assert "START=0" in meta
    assert "END=1000" in meta
    assert "title=Intro" in meta
    assert "START=1000" in meta
    assert "END=3000" in meta
    assert "title=Chapter 2" in meta


def test_build_ffmetadata_clamps_min_duration():
    meta = AudioConverter._build_ffmetadata(["Only"], [0], None)
    assert "START=0" in meta
    assert "END=1" in meta
