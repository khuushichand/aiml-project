import os
from io import BytesIO
from pathlib import Path

import pytest
from loguru import logger


# Unit-test the internal save/upload utility to exercise cleanup paths.
from tldw_Server_API.app.api.v1.endpoints.media import _save_uploaded_files
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import file_validator_instance


class DummyUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._bio = BytesIO(content)

    async def read(self, n: int) -> bytes:
        return self._bio.read(n)

    async def close(self) -> None:
        """Mimic FastAPI's UploadFile.close() as an awaitable.
        Ensures production code awaiting file.close() does not raise.
        """
        try:
            self._bio.close()
        except Exception:
            pass


@pytest.fixture
def tmp_media_dir(tmp_path: Path) -> Path:
    d = tmp_path / "media_uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.mark.asyncio
async def test_save_uploaded_files_empty_file_cleanup_logs(tmp_media_dir, capsys):
    # Capture loguru logs to stdout for simple assertion
    sink_id = logger.add(lambda m: print(m, end=""))
    try:
        files = [DummyUploadFile("empty.txt", b"")]
        processed, errors = await _save_uploaded_files(
            files,
            tmp_media_dir,
            validator=file_validator_instance,
            allowed_extensions=[".txt"],
        )
        assert processed == []
        assert len(errors) == 1
        assert errors[0]["status"] == "Error"
        # Ensure a warning about empty upload was logged and no crash occurred
        out = capsys.readouterr().out
        assert "is empty. Skipping." in out
    finally:
        logger.remove(sink_id)


@pytest.mark.asyncio
async def test_save_uploaded_files_write_failure_cleanup(tmp_media_dir, monkeypatch):
    # Force aiofiles.open to raise OSError to exercise the write-error cleanup path
    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    class _FailOpen:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise OSError("simulated write open error")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _fake_open(*a, **kw):
        return _FailOpen()

    monkeypatch.setattr(media_mod.aiofiles, "open", _fake_open, raising=True)

    files = [DummyUploadFile("code.py", b"print('x')\n")]
    processed, errors = await _save_uploaded_files(
        files,
        tmp_media_dir,
        validator=file_validator_instance,
        allowed_extensions=[".py"],
        expected_media_type_key="code",
    )
    assert processed == []
    assert len(errors) == 1
    assert errors[0]["status"] == "Error"
    assert "simulated write open error" in str(errors[0]["error"])
