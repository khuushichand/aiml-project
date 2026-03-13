from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ocr_evaluator_uses_mineru_structured_pages_for_per_page_metrics(monkeypatch):
    from tldw_Server_API.app.core.Evaluations.ocr_evaluator import OCREvaluator
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF import PDF_Processing_Lib as pdf_lib

    monkeypatch.setattr(
        pdf_lib,
        "process_pdf",
        lambda **kwargs: {
            "content": "page one\npage two",
            "analysis_details": {
                "ocr": {
                    "backend": "mineru",
                    "total_pages": 2,
                    "ocr_pages": 2,
                    "structured": {
                        "schema_version": 1,
                        "pages": [
                            {"page": 1, "text": "page one"},
                            {"page": 2, "text": "page two"},
                        ],
                        "meta": {"supports_per_page_metrics": True},
                    },
                }
            },
        },
    )

    evaluator = OCREvaluator()
    result = await evaluator.evaluate(
        items=[
            {
                "id": "mineru-doc",
                "pdf_bytes": b"%PDF-1.4",
                "ground_truth_text": "page one page two",
                "ground_truth_pages": ["page one", "page two"],
            }
        ],
        ocr_options={"ocr_backend": "mineru"},
    )

    item = result["results"][0]
    assert item["per_page_metrics"][0]["page"] == 1
    assert item["per_page_metrics"][1]["page"] == 2
    assert item["page_coverage"] == 1.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ocr_evaluator_warns_when_mineru_has_no_page_slices(monkeypatch):
    from tldw_Server_API.app.core.Evaluations.ocr_evaluator import OCREvaluator
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF import PDF_Processing_Lib as pdf_lib

    monkeypatch.setattr(
        pdf_lib,
        "process_pdf",
        lambda **kwargs: {
            "content": "whole document text",
            "analysis_details": {
                "ocr": {
                    "backend": "mineru",
                    "total_pages": 2,
                    "ocr_pages": 2,
                    "structured": {
                        "schema_version": 1,
                        "pages": [],
                        "meta": {"supports_per_page_metrics": False},
                    },
                }
            },
        },
    )

    evaluator = OCREvaluator()
    result = await evaluator.evaluate(
        items=[
            {
                "id": "mineru-doc",
                "pdf_bytes": b"%PDF-1.4",
                "ground_truth_text": "whole document text",
                "ground_truth_pages": ["page one", "page two"],
            }
        ],
        ocr_options={"ocr_backend": "mineru"},
    )

    item = result["results"][0]
    assert "per_page_metrics" not in item
    assert item["ocr_details"]["supports_per_page_metrics"] is False
    assert item["ocr_details"]["warnings"] == ["MinerU output did not include page slices"]
