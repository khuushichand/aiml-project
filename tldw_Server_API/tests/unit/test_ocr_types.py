from __future__ import annotations

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.base import OCRBackend
from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.types import (
    OCRBlock,
    OCRResult,
    normalize_ocr_format,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.backends.hunyuan_ocr import (
    _build_result_from_output,
)


class DummyBackend(OCRBackend):
    name = "dummy"

    @classmethod
    def available(cls) -> bool:
        return True

    def ocr_image(self, image_bytes: bytes, lang: str | None = None) -> str:
        return "hello"


def test_normalize_ocr_format():
    assert normalize_ocr_format(None) == "unknown"
    assert normalize_ocr_format("text") == "text"
    assert normalize_ocr_format("markdown") == "markdown"
    assert normalize_ocr_format("json") == "json"
    assert normalize_ocr_format("auto") == "unknown"
    assert normalize_ocr_format("weird") == "unknown"


def test_ocr_result_as_dict():
    result = OCRResult(
        text="hi",
        format="text",
        blocks=[OCRBlock(text="hi", bbox=[0, 0, 1, 1], block_type="text")],
    )
    payload = result.as_dict()
    assert payload["text"] == "hi"
    assert payload["blocks"][0]["bbox"] == [0, 0, 1, 1]


def test_backend_structured_fallback():
    backend = DummyBackend()
    res = backend.ocr_image_structured(b"bytes", output_format="markdown")
    assert res.text == "hello"
    assert res.format == "markdown"


def test_hunyuan_json_parse_builds_blocks():
    raw = '{"text": "hi", "blocks": [{"text": "hi", "bbox": [0, 0, 1, 1]}]}'
    res = _build_result_from_output(raw, output_format="json", prompt_preset="json", meta={})
    assert res.format == "json"
    assert res.text == "hi"
    assert res.blocks
    assert res.blocks[0].bbox == [0, 0, 1, 1]
