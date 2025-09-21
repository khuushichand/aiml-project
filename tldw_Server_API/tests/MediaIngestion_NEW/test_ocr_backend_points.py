import os
import pytest


@pytest.mark.unit
def test_points_backend_available_returns_bool():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.points_reader import (
        PointsReaderBackend,
    )
    assert isinstance(PointsReaderBackend.available(), bool)


@pytest.mark.unit
def test_points_backend_sglang_mock(monkeypatch):
    # Force SGLang mode and stub requests.post
    monkeypatch.setenv("POINTS_MODE", "sglang")
    monkeypatch.setenv("POINTS_SGLANG_URL", "http://127.0.0.1:9999/v1/chat/completions")
    monkeypatch.setenv("POINTS_SGLANG_MODEL", "WePoints")

    class DummyResp:
        status_code = 200
        text = "{\"choices\":[{\"message\":{\"content\":\"MOCK_TEXT\"}}]}"

        def raise_for_status(self):
            return None

        def json(self):
            import json as _json
            return _json.loads(self.text)

    import requests as _requests
    monkeypatch.setattr(_requests, "post", lambda *a, **k: DummyResp())

    from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import (
        get_backend,
    )

    backend = get_backend("points")
    assert backend is not None

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    out = backend.ocr_image(png_bytes, lang="eng")
    assert isinstance(out, str) and out == "MOCK_TEXT"
