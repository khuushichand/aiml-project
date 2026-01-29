import importlib
import importlib.util
from pathlib import Path

import pytest


def _module_available() -> bool:
    return (
        importlib.util.find_spec(
            "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.deepseek_ocr"
        )
        is not None
    )


@pytest.mark.unit
def test_deepseek_backend_available_returns_bool():
    if not _module_available():
        pytest.skip("DeepSeek OCR backend not implemented yet")

    module = importlib.import_module(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.deepseek_ocr"
    )
    assert isinstance(module.DeepSeekOCRBackend.available(), bool)


@pytest.mark.unit
def test_deepseek_backend_save_results_uses_output_dir(tmp_path, monkeypatch):
    module = importlib.import_module(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.deepseek_ocr"
    )

    # Force availability and stub model inference to avoid heavy deps.
    monkeypatch.setattr(module.DeepSeekOCRBackend, "available", classmethod(lambda cls: True))
    monkeypatch.setenv("DEEPSEEK_OCR_SAVE_RESULTS", "true")
    monkeypatch.setenv("DEEPSEEK_OCR_OUTPUT_DIR", str(tmp_path))

    calls = {}

    class DummyModel:
        def infer(self, tokenizer, **kwargs):
            calls["output_path"] = kwargs.get("output_path")
            return "OK"

    monkeypatch.setattr(module, "_load_transformers", lambda: (DummyModel(), object()))

    backend = module.DeepSeekOCRBackend()
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    out = backend.ocr_image(png_bytes, lang="eng")
    assert out == "OK"

    output_path = calls.get("output_path")
    assert output_path, "Expected output_path to be passed to model.infer"
    resolved = Path(output_path).resolve()
    base = Path(tmp_path).resolve()
    assert str(resolved).startswith(str(base)), "output_path should live under DEEPSEEK_OCR_OUTPUT_DIR"
    assert resolved.exists() and resolved.is_dir()
