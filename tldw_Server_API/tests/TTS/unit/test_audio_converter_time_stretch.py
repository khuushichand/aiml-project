import pytest

from tldw_Server_API.app.core.TTS import audio_converter as ac_mod

pytestmark = pytest.mark.unit


def test_build_atempo_filter_splits_large_ratio():
    filter_spec = ac_mod.AudioConverter._build_atempo_filter(3.0)
    assert "atempo=2" in filter_spec
    assert "atempo=1.5" in filter_spec
    assert "," in filter_spec


@pytest.mark.asyncio
async def test_time_stretch_builds_ffmpeg_command(monkeypatch, tmp_path):
    captured = {}

    class _FakeProc:
        def __init__(self):
            self.returncode = 0

        async def communicate(self):
            return b"", b""

    async def _fake_cpe(*cmd, **_kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    monkeypatch.setattr(ac_mod.asyncio, "create_subprocess_exec", _fake_cpe)

    in_path = tmp_path / "in.wav"
    in_path.write_bytes(b"audio")
    out_path = tmp_path / "out.wav"

    ok = await ac_mod.AudioConverter.time_stretch(in_path, out_path, 1.25)
    assert ok
    cmd = " ".join(captured["cmd"])
    assert "ffmpeg" in cmd
    assert "-filter:a" in captured["cmd"]
    assert "atempo=1.25" in cmd


@pytest.mark.asyncio
async def test_time_stretch_rejects_non_positive_ratio(tmp_path):
    in_path = tmp_path / "in.wav"
    in_path.write_bytes(b"audio")
    out_path = tmp_path / "out.wav"
    ok = await ac_mod.AudioConverter.time_stretch(in_path, out_path, 0)
    assert ok is False
