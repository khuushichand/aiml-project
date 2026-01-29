from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal


OCRFormat = Literal["text", "markdown", "html", "json", "unknown"]


@dataclass
class OCRBlock:
    text: str
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1] pixels or normalized
    block_type: Optional[str] = None


@dataclass
class OCRTable:
    format: Literal["html", "markdown", "cells"]
    content: Any


@dataclass
class OCRResult:
    text: str = ""
    format: OCRFormat = "text"
    blocks: List[OCRBlock] = field(default_factory=list)
    tables: List[OCRTable] = field(default_factory=list)
    pages: Optional[List[Dict[str, Any]]] = None
    raw: Optional[Any] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text or "",
            "format": self.format,
            "blocks": [
                {"text": b.text, "bbox": b.bbox, "block_type": b.block_type}
                for b in self.blocks
            ],
            "tables": [
                {"format": t.format, "content": t.content}
                for t in self.tables
            ],
            "pages": self.pages,
            "raw": self.raw,
            "meta": self.meta,
            "warnings": self.warnings,
        }


def normalize_ocr_format(value: Optional[str]) -> OCRFormat:
    if not value:
        return "unknown"
    v = str(value).strip().lower()
    if v in ("auto", "none", "null"):
        return "unknown"
    if v in ("text", "markdown", "html", "json", "unknown"):
        return v  # type: ignore[return-value]
    return "unknown"
