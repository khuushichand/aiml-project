"""
OCR adapter package for PDF and image text extraction.

Provides a pluggable interface and registry so multiple OCR backends/models
can be supported without changing ingestion code.

Backends can be added under `backends/` and registered in `registry.py`.
"""
