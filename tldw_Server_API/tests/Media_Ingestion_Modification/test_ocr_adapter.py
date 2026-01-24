import types
from typing import Optional

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import get_backend
from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.tesseract_cli import (
    TesseractCLIBackend,
)


@pytest.mark.unit
def test_registry_selects_tesseract_when_available(monkeypatch):


    # Simulate tesseract binary present
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tesseract" if name == "tesseract" else None)
    backend = get_backend(None)  # auto
    assert backend is not None
    assert isinstance(backend, TesseractCLIBackend)


@pytest.mark.unit
def test_tesseract_cli_ocr_invocation(monkeypatch):


    # Ensure registry thinks tesseract is present
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tesseract" if name == "tesseract" else None)

    # Mock subprocess.run used by backend
    class DummyCompleted:
        def __init__(self, stdout: str):
            self.stdout = stdout

    def fake_run(cmd, capture_output, text, check):

        assert cmd[0] == "tesseract"
        assert "stdout" in cmd
        return DummyCompleted(stdout="Hello OCR")

    monkeypatch.setattr("subprocess.run", fake_run)

    backend = get_backend("tesseract")
    assert backend is not None
    text = backend.ocr_image(b"\x89PNG\r\n....")
    assert text == "Hello OCR"


@pytest.mark.unit
def test_registry_resolves_nemotron_parse_when_configured(monkeypatch):
    monkeypatch.setenv("NEMOTRON_VLLM_URL", "http://127.0.0.1:8001/v1/chat/completions")
    backend = get_backend("nemotron_parse")
    assert backend is not None
    assert getattr(backend, "name", None) == "nemotron_parse"
