# Ingestion_Media_Processing (Developer Guide)

Core ingestion and media processing for audio, video, PDFs, EPUBs, documents (txt/md/html/xml/docx/rtf), and MediaWiki dumps. This module focuses on safe ingestion, extraction, optional chunking/analysis, and returns DB-agnostic results. FastAPI endpoints handle persistence and response shaping.

- Full guide: `Docs/Code_Documentation/Ingestion_Media_Processing.md`
- Related pipelines: see `Docs/Code_Documentation/Ingestion_Pipeline_*.md`

**Directory Map**
- `Audio/` - STT (faster_whisper, Nemo/Parakeet/Qwen2Audio), diarization, streaming
- `Video/` - yt-dlp download + audio transcription
- `PDF/` - parsing via PyMuPDF/pymupdf4llm/Docling; optional OCR & VLM
- `VLM/` - pluggable vision backends (e.g., HF Table Transformer)
- `Books/` - EPUB extraction and ZIP of EPUBs
- `Plaintext/` - txt/md/html/xml/docx/rtf conversion
- `MediaWiki/` - XML dump parsing (evented, optional persistence)
- `Claims/` - ingestion-time claim extraction helpers
- `Upload_Sink.py` - secure upload validation (MIME/size/Yara/archive scanning)
- `Media_Update_lib.py` - DB-level update utilities (versioning/keywords)
- `XML_Ingestion_Lib.py` - legacy XML helper (writes to DB)

**Design Principles**
- DB-agnostic processors: functions return structured dicts the API layer can persist.
- Safety first: strict file validation, size caps, optional Yara, controlled archive scanning.
- Pluggable extras: OCR and VLM use registries so backends can be added or swapped.
- Chunking as a service: consistent chunk outputs via `app/core/Chunking` utilities.
- Clear contracts: predictable result keys, minimal surprises across media types.

**Result Contract (typical keys)**
- `status` (`Success|Warning|Error`)
- `input_ref` and `processing_source`
- `media_type` (e.g., `pdf|audio|video|document`)
- `metadata` (title/author/filename/raw)
- `content` (plain/markdown text) or `segments`
- `chunks` (list with `text` and `metadata`)
- `analysis` and `analysis_details` (when summarization enabled)
- `keywords`, `warnings`, `error`

See examples in `PDF/PDF_Processing_Lib.py` (function `process_pdf`) and `Plaintext/Plaintext_Files.py` (function `process_document_content`).

**Validation & Security**
- Upload validation in `Upload_Sink.py`:
  - Extension/MIME filtering, size limits per type, optional Yara scanning
  - Safe archive scanning for ZIP/TAR with nesting and total size caps
  - Configurable via `loaded_config_data['media_processing']`
- Hardened parsers for risky formats (e.g., `defusedxml` for XML via Plaintext/XML paths)
- Blocked executables and scripts by default

Quick entry points
- PDF: `PDF/PDF_Processing_Lib.py:process_pdf`
- Documents: `Plaintext/Plaintext_Files.py:process_document_content`
- Audio: `Audio/Audio_Files.py:process_audio_files` (batch) and `Audio/Audio_Transcription_Lib.py` (core STT)
- Video: `Video/Video_DL_Ingestion_Lib.py` (download + STT)
- MediaWiki: `MediaWiki/Media_Wiki.py` (evented dump import)

**OCR and VLM (Pluggable)**
- OCR registry: `OCR/registry.py` exposes `get_backend(name)` and `list_backends()`; add backends under `OCR/backends`.
- VLM registry: `VLM/registry.py` similarly resolves vision backends.
- PDF OCR/VLM toggles are available through `process_pdf` parameters and mirrored by API forms.

**Persistence Boundary**
- Processors here do not write to databases by default.
- API endpoints wire persistence using `Media_DB_v2` and helpers in `app/core/DB_Management/`.
- When needed, DB-level helpers exist, e.g. `Media_Update_lib.py:process_media_update` to create new document versions or update keywords.

Contribution Guide (for this module)
- Follow PEP-8, type hints, and comprehensive docstrings.
- Prefer DB-agnostic functions that accept paths/bytes and return dicts.
- Use `loguru` via `app/core/Utils/Utils.py:logging` helper for consistency.
- Respect configuration via `app/core/config.py` (`loaded_config_data`).
- Add tests under `tldw_Server_API/tests` mirroring structure; mark with `unit`/`integration` as appropriate.
- Mock external services (LLMs, STT, yt-dlp) in tests; avoid real network.

Adding a new media pipeline
- Place code under a new folder here (e.g., `XYZ/`) with a clear public `process_*` entry.
- Keep the function DB-agnostic; return the standard result dict.
- Reuse `improved_chunking_process` for chunking and `analyze` for optional summarization.
- Add secure handling to `Upload_Sink.py` if new file types are supported (extension/MIME/size policy).
- Wire the API endpoint in `app/api/v1/endpoints/media.py` and add Pydantic schemas.
- Write unit tests for the processor and integration tests for the endpoint.

Local setup tips
- Install extras as needed: `pip install -e .[dev]` then add optional deps (e.g., `pypandoc`, `docling`, `yara`).
- Ensure `ffmpeg` is available on PATH for audio/video.
- For OCR, install a backend (e.g., Tesseract) and verify via `OCR/registry.py:list_backends()`.

Testing pointers
- Run: `python -m pytest -m "unit" -v` or full `python -m pytest -v`.
- Useful workflow tests: `tldw_Server_API/tests/Workflows/test_media_ingest_local_chunking.py` and `.../test_media_ingest_db_integration.py`.
- Media claims tests: see `tldw_Server_API/tests/Claims/`.

References
- `Docs/Code_Documentation/Ingestion_Media_Processing.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_PDF.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_Documents.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_Video.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_Ebooks.md`
- `Docs/Code_Documentation/Ingestion_Pipeline_MediaWiki.md`


## How To Test Locally

Prereqs (recommended)
- Python deps: `pip install -e .[dev]` and add optional extras as needed (e.g., `pypandoc`, `docling`, `yara`, `python-magic`, `puremagic`).
- Binaries: `ffmpeg` (audio/video), `tesseract` (OCR optional), `pandoc` (RTF), `yt-dlp` (video/audio downloads).

Quick checks
```bash
ffmpeg -hide_banner -version | head -n1
yt-dlp --version
tesseract --version  # optional
pandoc --version     # optional (.rtf)
python - <<'PY'
try:
    import puremagic; print('puremagic: OK')
except Exception as e:
    print('puremagic: missing', e)
try:
    import yara; print('yara: OK (optional)')
except Exception:
    print('yara: missing (optional)')
PY
```

Run the dev server
```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
# API docs: http://127.0.0.1:8000/docs
```

Auth notes
- In single-user mode, include `X-API-KEY: <your_key>` header. Startup logs print the key if not set via env.
- In multi-user mode, include `Authorization: Bearer <jwt>`.

Endpoint smoke tests (no DB persistence)
```bash
# PDF
curl -sS -H 'X-API-KEY: <key>' \
  -F 'files=@sample.pdf' \
  http://127.0.0.1:8000/api/v1/media/process-pdfs | jq .

# Documents (txt/md/html/xml/docx/rtf)
curl -sS -H 'X-API-KEY: <key>' \
  -F 'files=@sample.txt' \
  http://127.0.0.1:8000/api/v1/media/process-documents | jq .

# Audio (local file)
curl -sS -H 'X-API-KEY: <key>' \
  -F 'files=@sample.mp3' \
  http://127.0.0.1:8000/api/v1/media/process-audios | jq .

# Video (YouTube URL)
curl -sS -H 'X-API-KEY: <key>' \
  -F 'urls=https://www.youtube.com/watch?v=dQw4w9WgXcQ' \
  http://127.0.0.1:8000/api/v1/media/process-videos | jq .

# EPUB
curl -sS -H 'X-API-KEY: <key>' \
  -F 'files=@book.epub' \
  http://127.0.0.1:8000/api/v1/media/process-ebooks | jq .
```

MediaWiki (two options)
- Python (ephemeral iteration):
```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki import import_mediawiki_dump

for ev in import_mediawiki_dump(
    file_path='enwiki-abstract.xml.bz2',
    wiki_name='enwiki',
    namespaces=[0],
    skip_redirects=True,
    store_to_db=False,
    store_to_vector_db=False,
):
    print(ev.get('type'), ev.get('message') or ev.get('data', {}).get('title'))
```
- API (ephemeral, streaming NDJSON):
```bash
curl -N -H 'X-API-KEY: <key>' \
  -F 'dump_file=@enwiki-abstract.xml.bz2' \
  -F 'wiki_name=enwiki' \
  -F 'namespaces=0' \
  -F 'skip_redirects=true' \
  http://127.0.0.1:8000/api/v1/media/mediawiki/process-dump
```

Direct Python usage examples
```python
# PDF (bytes input)
from pathlib import Path
from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf

data = Path('sample.pdf').read_bytes()
res = process_pdf(data, filename='sample.pdf', parser='pymupdf4llm', perform_chunking=True)
print(res['status'], len(res.get('chunks') or []))

# Documents (path input)
from pathlib import Path
from tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files import process_document_content

res = process_document_content(
    doc_path=Path('sample.txt'),
    perform_chunking=True,
    chunk_options={'method': 'recursive', 'max_size': 1000, 'overlap': 200},
    perform_analysis=False,
    summarize_recursively=False,
    api_name=None, api_key=None,
    custom_prompt=None, system_prompt=None,
)
print(res['status'], res['metadata'])

# Audio (batch)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files import process_audio_files
res = process_audio_files(
    inputs=['sample.mp3'],
    transcription_model='base.en',
    transcription_language='en',
    perform_analysis=False,
    perform_chunking=True,
    chunk_method='sentences', max_chunk_size=1000, chunk_overlap=200,
    use_adaptive_chunking=False, use_multi_level_chunking=False,
    summarize_recursively=False,
    api_name=None,
)
print(res['processed_count'], 'items processed')

# Video (YouTube URL)
import tempfile
from tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib import process_videos
tmp = tempfile.mkdtemp(prefix='vid_')
out = process_videos(
    inputs=['https://www.youtube.com/watch?v=dQw4w9WgXcQ'],
    start_time=None, end_time=None,
    diarize=False, vad_use=False,
    transcription_model='small', transcription_language='en',
    perform_analysis=False, custom_prompt=None, system_prompt=None,
    perform_chunking=True, chunk_method='sentences', max_chunk_size=1000, chunk_overlap=200,
    use_adaptive_chunking=False, use_multi_level_chunking=False, chunk_language='en',
    summarize_recursively=False, api_name=None,
    use_cookies=False, cookies=None, timestamp_option=False,
    perform_confabulation_check=False, temp_dir=tmp,
)
print(out['processed_count'], 'video(s) processed')

# EPUB
from tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib import process_epub
book = process_epub('book.epub', perform_chunking=True)
print(book['status'], len(book.get('chunks') or []))
```
