# OCR API Documentation (v0.1) - Placeholder

Status: Initial placeholder for OCR endpoints and integration. This page will expand with full request/response schemas and examples.

## Summary

The OCR module integrates with media ingestion to extract text from scanned PDFs or images when native text is unavailable. The public API currently exposes lightweight endpoints for backend discovery and preloading, while full OCR execution is driven via the media ingestion APIs.

## Endpoints

1) GET `/api/v1/ocr/backends`
   - Lists available OCR backends with basic health info.
   - Returns a map keyed by backend name (e.g., `points`, `dots`) including minimal configuration details and reachability checks.
   - Code: `tldw_Server_API/app/api/v1/endpoints/ocr.py:router.get("/backends")`

2) POST `/api/v1/ocr/points/preload`
   - Attempts to preload the POINTS Transformers model to surface errors early.
   - Returns `{ "status": "ok" | "error", ... }`.
   - Code: `tldw_Server_API/app/api/v1/endpoints/ocr.py:router.post("/points/preload")`

## OCR in Media Ingestion

OCR is typically enabled via the media ingestion request options. Key fields (see code for authoritative definitions):

- `enable_ocr` (bool) - enable OCR for scanned/low-text PDFs
- `ocr_backend` (str | null) - backend name (e.g., `tesseract`, `auto`, or module-specific)
- `ocr_lang` (str) - language (e.g., `eng`)
- `ocr_dpi` (int) - DPI for page rendering prior to OCR
- `ocr_mode` (enum) - `always` or `fallback`
- `ocr_min_page_text_chars` (int) - threshold to treat a page as “no text” for fallback OCR

Reference (code): `tldw_Server_API/app/api/v1/schemas/media_request_models.py`.

## Quick Examples

List OCR backends

```bash
curl -s http://localhost:8000/api/v1/ocr/backends | jq
```

Preload POINTS Transformers

```bash
curl -s -X POST http://localhost:8000/api/v1/ocr/points/preload | jq
```

Enable OCR in media ingestion (illustrative JSON fragment)

```json
{
  "enable_ocr": true,
  "ocr_backend": "auto",
  "ocr_lang": "eng",
  "ocr_mode": "fallback",
  "ocr_dpi": 300
}
```

## Backend Notes

- POINTS Reader: documentation coming soon
- OCR Providers overview: documentation coming soon

## Roadmap (Placeholder)

- Expand docs with full request/response schemas
- Add examples for common ingestion flows with OCR
- Add troubleshooting and performance tips

---

If you need additional OCR endpoints or deeper docs, please open an issue with your use case.
