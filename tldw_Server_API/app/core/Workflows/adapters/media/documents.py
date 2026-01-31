"""Document processing adapters.

This module includes adapters for document operations:
- pdf_extract: Extract content from PDF files
- ocr: Optical character recognition on images
- document_table_extract: Extract tables from documents
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.media._config import (
    DocumentTableExtractConfig,
    OCRConfig,
    PDFExtractConfig,
)


@registry.register(
    "pdf_extract",
    category="media",
    description="Extract content from PDF",
    parallelizable=True,
    tags=["media", "document"],
    config_model=PDFExtractConfig,
)
async def run_pdf_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text and metadata from a PDF file.

    Config:
      - pdf_uri: str (templated, file:// path - required)
      - parser: Literal["pymupdf4llm", "pymupdf", "docling"] (default: "pymupdf4llm")
      - title: str (optional, templated - title override)
      - author: str (optional, templated - author override)
      - keywords: List[str] (optional)
      - perform_chunking: bool (default: True)
      - chunk_method: str (default: "sentences")
      - max_chunk_size: int (default: 500)
      - chunk_overlap: int (default: 100)
      - enable_ocr: bool (default: False)
      - ocr_backend: str (optional)
      - ocr_lang: str (default: "eng")
      - ocr_mode: Literal["fallback", "always"] (default: "fallback")
      - enable_vlm: bool (default: False)
      - vlm_backend: str (optional)
      - vlm_detect_tables_only: bool (default: True)
    Output:
      - {status, content, text, metadata, chunks, keywords, page_count, warnings}
    """
    # Delegate to legacy for full functionality
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_pdf_extract_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "ocr",
    category="media",
    description="Optical character recognition",
    parallelizable=True,
    tags=["media", "ocr"],
    config_model=OCRConfig,
)
async def run_ocr_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run OCR on an image to extract text.

    Config:
      - image_uri: str (templated, file:// path or artifact URI - required)
      - backend: str (optional: "auto", "tesseract", "deepseek", "nemotron_parse", etc.)
      - language: str (default: "eng")
      - output_format: Literal["text", "markdown", "html", "json"] (default: "text")
      - prompt_preset: str (optional, backend-specific)
    Output:
      - {text, format, blocks, tables, meta, warnings}
    """
    # Delegate to legacy for full functionality
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_ocr_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "document_table_extract",
    category="media",
    description="Extract tables from documents",
    parallelizable=False,
    tags=["media", "document"],
    config_model=DocumentTableExtractConfig,
)
async def run_document_table_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract tables from documents as structured JSON/CSV.

    Config:
      - file_path: str - Path to document (PDF, image, etc.)
      - file_uri: str - Alternative: file:// URI
      - output_format: str - "json" or "csv" (default: "json")
      - table_index: int - Specific table index to extract (default: all)
      - provider: str - Extraction provider: "docling", "llm" (default: "docling")
    Output:
      - tables: list[dict] - Extracted tables
      - count: int
      - format: str
    """
    # Delegate to legacy for full functionality
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_document_table_extract_adapter as _legacy
    return await _legacy(config, context)
