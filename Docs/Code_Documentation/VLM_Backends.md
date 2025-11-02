# Vision-Language Processing (VLM) in tldw_server

This document explains how VLM integrates with media ingestion and RAG, and how to use and configure supported backends.

- VLM is separate from OCR. OCR extracts text from page images; VLM detects/understands visual elements and emits structured detections and compact text hints for retrieval.
- Outputs are added as extra chunks for search/RAG with `chunk_type` of `table` (for tables) or `vlm` (for non-table labels like images/figures).

## Where VLM is used

- PDF processing pipeline (`/api/v1/media/process-pdfs`):
  - When enabled, each page is analyzed for visual elements.
  - Results are returned in the response and can be persisted as unvectorized chunks when ingesting media.

## API controls (process-pdfs)

Add these fields to the form data (in addition to existing PDF controls):

- `vlm_enable: bool` - enable VLM (default false)
- `vlm_backend: str | null` - backend name (see Backends below)
- `vlm_detect_tables_only: bool` - keep only `table` detections (default true)
- `vlm_max_pages: int | null` - limit the number of pages analyzed

Example (curl):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/media/process-pdfs \
  -F vlm_enable=true \
  -F vlm_backend="hf_table_transformer" \
  -F vlm_detect_tables_only=false \
  -F vlm_max_pages=3 \
  -F files=@/path/to/your.pdf
```

List available backends:

- `GET /api/v1/vlm/backends`

## Backends

### 1) Hugging Face Table Transformer (Detection)

- Name: `hf_table_transformer`
- Detects table regions via object detection.
- Requirements: `transformers`, `torch`, `Pillow`.
- Model control via environment variables:
  - `VLM_TABLE_MODEL_NAME` (default: `microsoft/table-transformer-detection`)
  - `VLM_TABLE_REVISION` (optional)
- Inference threshold:
  - `VLM_TABLE_THRESHOLD` (default: `0.9`)
- Notes:
  - Operates per-page by rendering a medium-resolution bitmap and running detection.
  - Emits `label=table` detections with bounding boxes.
  - Uses `model.config.id2label` when provided to map class IDs to text labels.

### 2) Docling (PDF structural VLM)

- Name: `docling`
- Uses `docling` to parse PDFs and extract structural elements.
- Detects:
  - Tables (structured when available; markdown fallback if not)
  - Figures/Images (structured when available; markdown `![...](...)` fallback)
- Requirements: `docling` Python package and its dependencies.
- Behavior:
  - Prefers document-level processing (`process_pdf`); if unavailable, the system falls back to per-page image mode (other backends).
  - Where page/bbox info isn’t available (fallback mode), detections are reported with `page=None` and zero bbox; compact text chunks are still generated for retrieval.

## Output structure

- Response contains `analysis_details.vlm`:

```json
{
  "vlm": {
    "backend": "docling",
    "pages_scanned": 3,
    "detections_total": 5,
    "by_page": [
      {"page": 1, "detections": [{"label": "table", "score": 0.90, "bbox": [x0,y0,x1,y1]}]},
      {"page": 2, "detections": [{"label": "image", "score": 0.75, "bbox": [x0,y0,x1,y1]}]}
    ]
  }
}
```

- The pipeline also emits `extra_chunks`, which are merged into `UnvectorizedMediaChunks` during ingestion. These chunks are terse textual hints like:

```
Detected table (0.90) on page 2 at [x0, y0, x1, y1]
Detected image (0.75) on page 3 at [x0, y0, x1, y1]
```

- `chunk_type` is set to `table` for tables, or `vlm` for other labels. Use the RAG API’s `chunk_type_filter` to include/exclude these.

## RAG integration

- No changes required to the unified pipeline; VLM chunks are indexed like other unvectorized chunks.
- To focus searches on visual artifacts:
  - Set `chunk_type_filter: ["table", "vlm"]` in RAG queries.

## Limitations & tips

- Docling page/bbox availability varies by document and docling version. Fallbacks populate unknowns conservatively.
- The HF backend runs inference per page; adjust `vlm_max_pages` for large PDFs.
- For embedding/storage, ensure your ingestion path merges `extra_chunks` (already wired in the default media ingestion flow).

## Troubleshooting

- `GET /api/v1/vlm/backends` shows which backends are importable and available.
- If a backend is not listed as available, verify its Python packages are installed and importable in the server environment.
- For HF Table Transformer, confirm GPU/CPU torch installation matches your environment.
