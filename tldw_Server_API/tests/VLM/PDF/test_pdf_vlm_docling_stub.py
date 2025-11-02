import io
import pytest


class _StubDet2:
    def __init__(self, label="table", score=0.8, bbox=None, page=1):
        self.label = label
        self.score = score
        self.bbox = bbox or [1.0, 1.0, 2.0, 2.0]
        self.page = page


class _StubRes2:
    def __init__(self):
        self.detections = []
        self.texts = None
        self.extra = {
            "by_page": [
                {"page": 1, "detections": [{"label": "table", "score": 0.8, "bbox": [1.0, 1.0, 2.0, 2.0]}]}
            ]
        }


class _StubDoclingBackend:
    name = "docling"

    @classmethod
    def available(cls) -> bool:
        return True

    def process_pdf(self, pdf_path: str, *, max_pages=None):
        return _StubRes2()


@pytest.mark.asyncio
async def test_pdf_process_uses_process_pdf_when_available(monkeypatch):
    try:
        import pymupdf
        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF import PDF_Processing_Lib as pdf_lib
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    # Monkeypatch the VLM backend resolver to a backend exposing process_pdf()
    monkeypatch.setattr(pdf_lib, "_get_vlm_backend", lambda name=None: _StubDoclingBackend())

    # Build an in-memory minimal PDF
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((72, 72), "Hello")
    pdf_bytes = doc.tobytes()
    doc.close()

    res = await pdf_lib.process_pdf_task(
        file_bytes=pdf_bytes,
        filename="test.pdf",
        parser="pymupdf4llm",
        perform_chunking=False,
        perform_analysis=False,
        enable_vlm=True,
        vlm_backend="docling",
        vlm_detect_tables_only=True,
        vlm_max_pages=2,
    )

    assert isinstance(res, dict)
    vlm = res.get("analysis_details", {}).get("vlm")
    assert vlm is not None
    assert vlm.get("pages_scanned") >= 1
    assert vlm.get("detections_total") >= 1
    # Confirm extra chunks were created
    extra = res.get("extra_chunks")
    assert isinstance(extra, list) and extra
