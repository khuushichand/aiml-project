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


class _DummyProcess:
    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_package_m4b_with_chapters_invokes_ffmpeg(tmp_path, monkeypatch):
    input_paths = [tmp_path / "a.wav", tmp_path / "b.wav"]
    for path in input_paths:
        path.write_bytes(b"")

    async def fake_duration(_path):
        return 1.0

    calls = {}

    async def fake_exec(*args, **kwargs):
        calls["args"] = args
        return _DummyProcess(returncode=0)

    monkeypatch.setattr(AudioConverter, "get_duration", staticmethod(fake_duration))
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.audio_converter.asyncio.create_subprocess_exec",
        fake_exec,
    )

    output_path = tmp_path / "book.m4b"
    ok = await AudioConverter.package_m4b_with_chapters(
        input_paths,
        output_path,
        ["Chapter 1", "Chapter 2"],
        metadata={"title": "Book"},
    )

    assert ok is True
    cmd = list(calls["args"])
    assert cmd[0] == "ffmpeg"
    assert "-f" in cmd and "concat" in cmd
    assert "-map_metadata" in cmd and "1" in cmd
    assert "-map_chapters" in cmd and "1" in cmd
    assert cmd[-1].endswith(".m4b")


@pytest.mark.asyncio
async def test_package_m4b_with_chapters_returns_false_on_ffmpeg_error(tmp_path, monkeypatch):
    input_path = tmp_path / "a.wav"
    input_path.write_bytes(b"")

    async def fake_duration(_path):
        return 1.0

    async def fake_exec(*args, **kwargs):
        return _DummyProcess(returncode=1, stderr=b"ffmpeg failed")

    monkeypatch.setattr(AudioConverter, "get_duration", staticmethod(fake_duration))
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.audio_converter.asyncio.create_subprocess_exec",
        fake_exec,
    )

    output_path = tmp_path / "book.m4b"
    ok = await AudioConverter.package_m4b_with_chapters(
        [input_path],
        output_path,
        ["Chapter 1"],
    )

    assert ok is False
