import builtins
import tempfile
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Utils import System_Checks_Lib
from tldw_Server_API.app.core.Utils import Utils


class _FakeResponse:
    def __init__(self, *, status_code: int, headers: dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self._body = body

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        yield self._body


class _TqdmStub:
    def __init__(self, *_, **__):
        pass

    def update(self, _amount):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_download_file_resumes_without_truncation(monkeypatch, tmp_path):
    dest = tmp_path / "file.bin"
    tmp_file = dest.with_suffix(".bin.tmp")
    tmp_file.write_bytes(b"12345")

    captured_headers = {}

    def fake_get(url, stream=True, headers=None, timeout=60):
        nonlocal captured_headers
        captured_headers = headers or {}
        return _FakeResponse(
            status_code=206,
            headers={
                "Content-Range": "bytes 5-9/10",
                "content-length": "5",
            },
            body=b"67890",
        )

    monkeypatch.setattr(Utils.requests, "get", fake_get)
    monkeypatch.setattr(Utils, "tqdm", _TqdmStub)

    Utils.download_file("https://example.com/file.bin", str(dest))

    assert dest.read_bytes() == b"1234567890"
    assert not tmp_file.exists()
    assert captured_headers.get("Range") == "bytes=5-"


def test_extract_text_from_segments_collects_all_segments():
    segments = [
        {"Time_Start": 0, "Time_End": 1, "Text": "First"},
        {"Time_Start": 1, "Time_End": 2, "Text": "Second"},
    ]
    result = Utils.extract_text_from_segments(segments, include_timestamps=True)
    assert result.splitlines() == [
        "0s - 1s | First",
        "1s - 2s | Second",
    ]


def test_extract_text_from_segments_handles_nested_dict():
    segments = {
        "outer": {
            "inner": {
                "Time_Start": 2,
                "Time_End": 3,
                "Text": "Nested text",
            }
        }
    }
    result = Utils.extract_text_from_segments(segments, include_timestamps=False)
    assert result == "Nested text"


def test_save_temp_file_normalizes_and_preserves_content(monkeypatch):
    class DummyUpload:
        def __init__(self, name, data):
            self.name = name
            self._data = data

        def read(self):
            return self._data

    upload = DummyUpload("../evil.txt", b"payload")
    saved_path = Utils.save_temp_file(upload)

    temp_dir = Path(tempfile.gettempdir()).resolve()
    resolved_saved = Path(saved_path).resolve()

    assert resolved_saved.parent == temp_dir
    assert resolved_saved.exists()
    assert b"payload" == resolved_saved.read_bytes()

    resolved_saved.unlink()


def test_safe_read_file_handles_empty_decodes(monkeypatch):
    class FakeBytes(bytes):
        def decode(self, encoding="utf-8", errors="strict"):
            return ""

    class DummyFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return FakeBytes(b"data")

    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: DummyFile())
    monkeypatch.setattr(Utils.chardet, "detect", lambda _raw: {"encoding": "ascii"})

    result = Utils.safe_read_file("dummy-path")

    assert isinstance(result, str)
    assert "Unable to decode" in result


def test_decide_cpugpu_defaults_on_eof(monkeypatch):
    System_Checks_Lib.processing_choice = "cpu"
    monkeypatch.setattr(System_Checks_Lib, "input", _raise_eof, raising=False)

    selection = System_Checks_Lib.decide_cpugpu()

    assert selection == "cpu"


def test_check_ffmpeg_handles_unknown_os(monkeypatch):
    System_Checks_Lib.userOS = "Unknown"
    monkeypatch.setattr(System_Checks_Lib.shutil, "which", lambda *_: None)
    monkeypatch.setattr(System_Checks_Lib.os.path, "exists", lambda *_: False)
    monkeypatch.setattr(System_Checks_Lib.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(System_Checks_Lib, "input", _raise_eof, raising=False)

    result = System_Checks_Lib.check_ffmpeg()

    assert result is False
def _raise_eof(*_args, **_kwargs):
    raise EOFError()
