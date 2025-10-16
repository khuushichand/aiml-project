# Ingestion_Media_Processing

Core media ingestion and processing module for audio, video, PDFs, EPUBs, documents (txt/md/html/xml/docx/rtf), and MediaWiki dumps. Provides DB‑agnostic processors used by the FastAPI endpoints, plus secure upload validation utilities.

- Full guide: see `Docs/Code_Documentation/Ingestion_Media_Processing.md`
- Key subpackages:
  - `Audio/` – transcription (faster_whisper, Nemo/Parakeet/Qwen2Audio), diarization, streaming
  - `Video/` – yt‑dlp download + transcription
  - `PDF/` – parsing (pymupdf4llm/PyMuPDF/Docling), optional OCR
  - `VLM/` – vision-language processing (e.g., table detection via HF Table Transformer)
  - `Books/` – EPUB extraction (filtered/markdown/basic)
  - `Plaintext/` – txt/md/html/xml/docx/rtf conversion
  - `MediaWiki/` – XML dump processing (evented, optional DB persistence)
  - `Claims/` – claim extraction helpers
  - `Upload_Sink.py` – file validation (MIME/size/Yara/archive scanning)

This folder’s processors return structured dicts; the API layer wires persistence and response shaping.

Per-pipeline docs:
- `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_Video.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_PDF.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_Ebooks.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_Documents.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_MediaWiki.md`

VLM quick notes:
- PDF processing can optionally run a VLM detector per page to create searchable chunks (separate from OCR).
- Enable via process-pdfs endpoint form fields: `vlm_enable`, `vlm_backend`, `vlm_detect_tables_only`, `vlm_max_pages`.
- Backends are pluggable; list current backends at `GET /api/v1/vlm/backends`.
- Detailed guide: Docs/Code_Documentation/VLM_Backends.md
