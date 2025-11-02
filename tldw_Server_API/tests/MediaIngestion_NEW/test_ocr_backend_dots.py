import io
import pytest


@pytest.mark.unit
def test_dots_backend_available_flag_safely_imports():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.dots_ocr import (
        DotsOCRBackend,
    )

    # Should return a boolean without raising, even if dots_ocr is not installed
    assert isinstance(DotsOCRBackend.available(), bool)


@pytest.mark.unit
def test_dots_backend_registry_resolution_when_installed():
    # Skip unless dots_ocr package is importable
    pytest.importorskip("dots_ocr")

    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import (
        get_backend,
    )

    backend = get_backend("dots")
    assert backend is not None, "Expected DotsOCRBackend instance when dots_ocr is installed"

    # Minimal valid 1x1 PNG (transparent) bytes
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    # Ensure ocr_image returns a string; content may be empty depending on env setup
    out = backend.ocr_image(png_bytes, lang="eng")
    assert isinstance(out, str)
