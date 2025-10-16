from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..base import VLMBackend, VLMDetection, VLMResult


class DoclingVLMBackend(VLMBackend):
    """
    Docling-backed VLM for structural element detection in PDFs.

    This backend leverages Docling's DocumentConverter to parse a PDF and
    extract table-like structures. It is optimized for PDF-level processing
    via `process_pdf(...)`. The `process_image(...)` method returns no detections
    and exists only to satisfy the interface; the PDF integration calls
    `process_pdf(...)` when available.

    Detected elements are returned as `VLMDetection` entries with label
    'table' and a best-effort score. Page and bbox information are populated
    when available; otherwise, they may be omitted.
    """

    name = "docling"

    def __init__(self):
        self._converter = None
        self._loaded = False

    @classmethod
    def available(cls) -> bool:
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401
        except Exception:
            return False
        return True

    def _lazy_load(self):
        if self._loaded:
            return
        from docling.document_converter import DocumentConverter

        self._converter = DocumentConverter()
        self._loaded = True

    def describe(self) -> Dict[str, Any]:
        return {"name": self.name, "available": self.available()}

    # Interface requirement (not used for docling).
    def process_image(
        self,
        image_bytes: bytes,
        *,
        mime_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VLMResult:
        return VLMResult(detections=[], texts=None, extra={("page" if context else "ctx"): (context or {})})

    # PDF-oriented processing for docling.
    def process_pdf(
        self,
        pdf_path: str,
        *,
        max_pages: Optional[int] = None,
    ) -> VLMResult:
        self._lazy_load()
        # Parse PDF via docling
        result = self._converter.convert(pdf_path)
        doc = getattr(result, "document", None)

        # Best-effort extraction strategy:
        # 1) Structured: try to read tables and figures/images from document attributes.
        # 2) Fallback: export to markdown and detect markdown tables and images.
        detections: List[VLMDetection] = []
        by_page: List[Dict[str, Any]] = []

        # Structured access (tables, figures/images)
        structured_any = False
        try:
            # Tables
            tables = getattr(doc, "tables", None)
            if isinstance(tables, list) and tables:
                structured_any = True
                for t in tables:
                    md: Dict[str, Any] = {}
                    page = getattr(t, "page", None) or getattr(t, "page_number", None)
                    if page is not None:
                        md["page"] = int(page)
                    bbox = getattr(t, "bbox", None)
                    b = [float(x) for x in (bbox or [0.0, 0.0, 0.0, 0.0])]
                    detections.append(VLMDetection(label="table", score=0.9, bbox=b, metadata=md))

            # Figures/Images (try common attribute names)
            for attr_name, label_name, score in (
                ("figures", "figure", 0.8),
                ("images", "image", 0.75),
                ("illustrations", "figure", 0.78),
            ):
                items = getattr(doc, attr_name, None)
                if isinstance(items, list) and items:
                    structured_any = True
                    for it in items:
                        md: Dict[str, Any] = {}
                        page = getattr(it, "page", None) or getattr(it, "page_number", None)
                        if page is not None:
                            md["page"] = int(page)
                        bbox = getattr(it, "bbox", None)
                        b = [float(x) for x in (bbox or [0.0, 0.0, 0.0, 0.0])]
                        detections.append(VLMDetection(label=label_name, score=score, bbox=b, metadata=md))

            # Group by page for summary (structured)
            if structured_any and detections:
                page_map: Dict[int, List[Dict[str, Any]]] = {}
                for d in detections:
                    p = int(d.metadata.get("page")) if d.metadata.get("page") is not None else -1
                    page_map.setdefault(p, []).append({"label": d.label, "score": d.score, "bbox": d.bbox})
                for p, dets in page_map.items():
                    by_page.append({"page": (None if p < 0 else p), "detections": dets})
        except Exception:
            structured_any = False

        # Markdown fallback: detect tables and images if structured info was not available
        try:
            md_text = None
            # If doc exposes markdown export, use it regardless to enrich with images if needed
            if hasattr(doc, "export_to_markdown"):
                try:
                    md_text = doc.export_to_markdown()
                except Exception:
                    md_text = None

            if isinstance(md_text, str):
                # Detect markdown tables
                if not structured_any:
                    blocks = re.split(r"\n\n+", md_text)
                    local_new = []
                    for blk in blocks:
                        lines = [l.strip() for l in blk.splitlines() if l.strip()]
                        if len(lines) >= 2 and ("|" in lines[0]) and re.search(r"\|\s*-{2,}\s*\|", lines[1]):
                            local_new.append(VLMDetection(label="table", score=0.6, bbox=[0.0, 0.0, 0.0, 0.0], metadata={}))
                    if local_new:
                        detections.extend(local_new)
                        # All unknown page
                        by_page.append({
                            "page": None,
                            "detections": [{"label": d.label, "score": d.score, "bbox": d.bbox} for d in local_new],
                        })

                # Detect markdown images (Figure/Image): ![alt](url)
                img_matches = list(re.finditer(r"!\[[^\]]*\]\([^\)]+\)", md_text))
                if img_matches:
                    local_imgs = [VLMDetection(label="image", score=0.55, bbox=[0.0, 0.0, 0.0, 0.0], metadata={}) for _ in img_matches]
                    detections.extend(local_imgs)
                    by_page.append({
                        "page": None,
                        "detections": [{"label": d.label, "score": d.score, "bbox": d.bbox} for d in local_imgs],
                    })
        except Exception:
            pass

        return VLMResult(detections=detections, texts=None, extra={"by_page": by_page})
