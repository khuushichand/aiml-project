import io
import pytest


class _StubDet:
    def __init__(self, label="table", score=0.9, bbox=None):
        self.label = label
        self.score = score
        self.bbox = bbox or [10.0, 10.0, 100.0, 50.0]


class _StubVLMResult:
    def __init__(self):
        self.detections = [_StubDet()]
        self.texts = None
        self.extra = None


class _StubBackend:
    name = "stub_vlm"

    @classmethod
    def available(cls) -> bool:
        return True

    def process_image(self, image_bytes: bytes, *, mime_type=None, context=None):
        return _StubVLMResult()


@pytest.mark.asyncio
async def test_pdf_process_includes_vlm_chunks(monkeypatch):
    try:
        import pymupdf
        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF import PDF_Processing_Lib as pdf_lib
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    # Monkeypatch the VLM backend resolver used in the module
    monkeypatch.setattr(pdf_lib, "_get_vlm_backend", lambda name=None: _StubBackend())

    # Build an in-memory minimal PDF
    buf = io.BytesIO()
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((72, 72), "Hello")
    pdf_bytes = doc.tobytes()
    doc.close()

    # Process with VLM enabled
    res = await pdf_lib.process_pdf_task(
        file_bytes=pdf_bytes,
        filename="test.pdf",
        parser="pymupdf4llm",
        perform_chunking=False,
        perform_analysis=False,
        enable_vlm=True,
        vlm_backend="stub_vlm",
        vlm_detect_tables_only=True,
        vlm_max_pages=1,
    )

    assert isinstance(res, dict)
    assert res.get("analysis_details", {}).get("vlm") is not None
    vlm = res["analysis_details"]["vlm"]
    assert vlm.get("pages_scanned") == 1
    assert vlm.get("detections_total") >= 1
    # Ensure extra chunks are exposed
    extra = res.get("extra_chunks")
    assert isinstance(extra, list)
    assert any((c.get("chunk_type") in ("table", "vlm")) for c in extra)
