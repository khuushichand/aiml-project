"""Pydantic config models for media adapters."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class ChunkingConfig(BaseAdapterConfig):
    """Chunking configuration for media ingestion."""

    method: Literal["sentences", "words", "paragraphs", "tokens", "semantic", "recursive"] = Field(
        "sentences", description="Chunking method"
    )
    max_size: int = Field(500, ge=50, description="Maximum chunk size")
    overlap: int = Field(50, ge=0, description="Overlap between chunks")
    language: str | None = Field(None, description="Language hint for chunking")


class MediaIngestConfig(BaseAdapterConfig):
    """Config for media ingestion adapter."""

    url: str | None = Field(None, description="URL to ingest (web page, YouTube, etc.)")
    file_uri: str | None = Field(None, description="file:// path to local file")
    content: str | None = Field(None, description="Raw text content to ingest")
    title: str | None = Field(None, description="Content title (optional)")
    author: str | None = Field(None, description="Content author (optional)")
    tags: list[str] | None = Field(None, description="Tags for the content")
    keywords: list[str] | None = Field(None, description="Keywords for the content")
    chunking: ChunkingConfig | None = Field(None, description="Chunking configuration")
    transcribe: bool = Field(True, description="Transcribe audio/video content")
    extract_metadata: bool = Field(True, description="Extract metadata from content")
    store_embeddings: bool = Field(True, description="Generate and store embeddings")
    overwrite: bool = Field(False, description="Overwrite existing content with same URL")


class ProcessMediaConfig(BaseAdapterConfig):
    """Config for process_media adapter."""

    url: str | None = Field(None, description="URL to process")
    file_uri: str | None = Field(None, description="file:// path to local file")
    transcribe: bool = Field(True, description="Transcribe audio/video content")
    summarize: bool = Field(False, description="Generate summary after processing")
    chunking: ChunkingConfig | None = Field(None, description="Chunking configuration")
    output_format: str | None = Field(None, description="Preferred output format")


class PDFExtractConfig(BaseAdapterConfig):
    """Config for PDF extraction adapter."""

    file_uri: str = Field(..., description="file:// path to PDF file (required)")
    extract_images: bool = Field(False, description="Extract images from PDF")
    extract_tables: bool = Field(False, description="Extract tables from PDF")
    ocr_enabled: bool = Field(False, description="Use OCR for scanned pages")
    page_range: str | None = Field(None, description="Page range (e.g., '1-5,10,15-20')")
    output_format: Literal["text", "markdown", "html", "json"] = Field(
        "text", description="Output format"
    )


class OCRConfig(BaseAdapterConfig):
    """Config for OCR adapter."""

    file_uri: str = Field(..., description="file:// path to image/PDF (required)")
    language: str = Field("eng", description="OCR language code(s)")
    engine: Literal["tesseract", "easyocr", "paddleocr"] = Field(
        "tesseract", description="OCR engine to use"
    )
    preprocess: bool = Field(True, description="Apply image preprocessing")
    output_format: Literal["text", "hocr", "json"] = Field("text", description="Output format")


class DocumentTableExtractConfig(BaseAdapterConfig):
    """Config for document table extraction adapter."""

    file_uri: str = Field(..., description="file:// path to document (required)")
    output_format: Literal["csv", "json", "markdown", "html"] = Field(
        "json", description="Output format for tables"
    )
    page_range: str | None = Field(None, description="Page range to extract from")
    merge_cells: bool = Field(True, description="Merge spanning cells")
    header_detection: bool = Field(True, description="Auto-detect table headers")
