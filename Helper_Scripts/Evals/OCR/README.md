# OCR Evaluation Samples

This folder contains ready-to-use sample payloads for evaluating OCR quality via CLI or API.

## Files

- `items_with_pages.jsonl`: JSON Lines file with sample items that include `extracted_text`, `ground_truth_text`, and `ground_truth_pages` for page-level scoring.
- `per_page_gts.json`: Example JSON array of arrays containing per-file per-page ground-truth text, aligned to multiple `--pdf` inputs.

## CLI Usage

1) Evaluate using items file (text-to-text, with per-page scoring):

```bash
# Show JSON output
tldw-evals eval ocr \
  --items-file Helper_Scripts/Evals/OCR/items_with_pages.jsonl \
  --max-cer 0.1 --max-wer 0.2 \
  --format json

# Show a compact table summary
tldw-evals eval ocr \
  --items-file Helper_Scripts/Evals/OCR/items_with_pages.jsonl \
  --max-cer 0.1 --max-wer 0.2 \
  --format table
```

2) Evaluate end-to-end OCR on PDFs (page-level ground-truths provided separately):

```bash
# Replace example.pdf with your PDFs. Requires tesseract installed for default backend.
tldw-evals eval ocr \
  --pdf example1.pdf --pdf example2.pdf \
  --ground-truths-pages-file Helper_Scripts/Evals/OCR/per_page_gts.json \
  --ocr-backend tesseract --ocr-lang eng --ocr-mode fallback \
  --max-cer 0.15 --min-coverage 0.7 \
  --format json
```

## API Usage (WebUI)

- `POST /api/v1/evaluations/ocr` (JSON):
  - Include `items` with `extracted_text`, `ground_truth_text`, and optional `ground_truth_pages` for page-level scoring.
  - Optional `thresholds` and `metrics`.

- `POST /api/v1/evaluations/ocr-pdf` (multipart/form-data):
  - `files`: one or more PDFs
  - `ground_truths_json`: JSON array of per-file ground-truth text
  - `ground_truths_pages_json`: JSON array of arrays of per-page ground-truth text, aligned to the uploaded files
  - `thresholds_json`: JSON dict (e.g., {"max_cer":0.15,"min_coverage":0.7})
  - OCR options: `enable_ocr`, `ocr_backend`, `ocr_lang`, `ocr_dpi`, `ocr_mode`, `ocr_min_page_text_chars`

In the WebUI (Evaluations → OCR Evaluation), fill `Ground Truths (JSON Array)` and `Per-Page Ground Truths (JSON Array of Arrays)` as needed for page-level scoring.

## Notes

- Page-level metrics are computed when `ground_truth_pages` (or `ground_truths_pages_json` in the PDF endpoint) are provided.
- Thresholds apply both at document level and at per-page level for pass/fail flags.
- Default OCR backend uses system `tesseract` (install via Homebrew on macOS or apt on Debian/Ubuntu).
