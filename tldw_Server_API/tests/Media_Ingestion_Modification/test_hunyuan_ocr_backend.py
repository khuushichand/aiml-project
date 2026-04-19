from __future__ import annotations

import pytest


@pytest.mark.unit
def test_ocr_backend_auto_eligible_defaults_true():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.base import OCRBackend

    assert OCRBackend.auto_eligible(False) is True  # nosec B101
    assert OCRBackend.auto_eligible(True) is True  # nosec B101


@pytest.mark.unit
def test_registry_explicit_hunyuan_selection_bypasses_auto_eligible(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import get_backend

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.hunyuan_ocr.HunyuanOCRBackend.available",
        classmethod(lambda cls: True),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.hunyuan_ocr.HunyuanOCRBackend.auto_eligible",
        classmethod(lambda cls, high_quality: False),
        raising=False,
    )

    backend = get_backend("hunyuan")

    assert backend is not None  # nosec B101
    assert getattr(backend, "name", None) == "hunyuan"  # nosec B101
