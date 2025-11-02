# OCR Providers Setup

This guide covers enabling and using optional OCR providers with the PDF pipeline. You can select the provider via the `ocr_backend` option in API/WebUI forms.

Supported backends
- tesseract (built-in, CLI)
- dots (dots.ocr project)
- points (Tencent POINTS-Reader)

Common usage
- Set `enable_ocr=true` and choose `ocr_backend` (`tesseract`, `dots`, or `points`).
- `ocr_mode`: `fallback` (only pages lacking text) or `always` (force OCR).
- `ocr_dpi`: 200-300 is a good balance.
- Parallelism: `OCR_PAGE_CONCURRENCY` controls per-page OCR concurrency (default 1). Keep small (1-2) for GPU-backed models.

## dots.ocr (backend: `dots`)

Quick setup
- Install per upstream repo:
  - git clone https://github.com/rednote-hilab/dots.ocr.git && cd dots.ocr
  - Install a compatible PyTorch build (CUDA/CPU), then `pip install -e .`
  - Download model weights: `python3 tools/download_model.py` (use a directory name without periods, e.g., `DotsOCR`).
- Recommended: serve with vLLM for performance (see upstream docs).

Install via extras (optional)
- You can install the project with the dots extra:
  - `pip install .[ocr_dots]`
  - This pulls the dots.ocr repo via a VCS dependency.

Backend specifics
- CLI mode: shells out to `python -m dots_ocr.parser <image.png>` per page (or use `DOTS_OCR_CMD` to specify an explicit command).
- vLLM mode: if `DOTS_VLLM_URL` is set, calls an OpenAI-compatible endpoint (`/v1/chat/completions`). Use `DOTS_VLLM_MODEL` (served-model-name), `DOTS_VLLM_TIMEOUT`, and `DOTS_VLLM_USE_DATA_URL` (default true) to control behavior.
- Env: `DOTS_OCR_PROMPT` (default `prompt_ocr`); `DOTS_OCR_CMD` can point to a script for custom setups.

Docs
- See pyproject extras and provider docs for optional OCR dependencies.

Pros/cons
- Pros: strong layout understanding; good accuracy on scanned docs; vLLM option for scale.
- Cons: heavy install; per-page CLI call if not served; model weights management.

## POINTS-Reader (backend: `points`)

Modes
- Transformers (local): loads `tencent/POINTS-Reader` via `transformers` and WePOINTS toolkit.
- SGLang (server): calls an OpenAI-compatible `/v1/chat/completions` endpoint.

Environment
- `POINTS_MODE`: `auto` (default), `sglang`, `transformers`.
- Transformers:
  - `POINTS_MODEL_PATH` (default `tencent/POINTS-Reader`), requires `transformers` + `torch` and WePOINTS installed.
- SGLang:
  - `POINTS_SGLANG_URL` (default `http://127.0.0.1:8081/v1/chat/completions`)
  - `POINTS_SGLANG_MODEL` (default `WePoints`)
- Shared generation (both modes): `POINTS_MAX_NEW_TOKENS`, `POINTS_TEMPERATURE`, `POINTS_REPETITION_PENALTY`, `POINTS_TOP_P`, `POINTS_TOP_K`, `POINTS_DO_SAMPLE`.
- Prompt: `POINTS_PROMPT` (defaults to extracting tables as HTML and text as Markdown).

Docs
- See detailed guide at `Docs/OCR/POINTS-Reader.md`.

Install via extras (optional)
- Local transformers path: `pip install .[ocr_points_transformers]`
  - Includes `transformers`, `torch`, and the WePOINTS toolkit via VCS.
- SGLang client only: `pip install .[ocr_points_sglang]`

## WebUI

- OCR Evaluation is available under WebUI → Evaluations → “OCR Evaluation / OCR PDF”.
- Fields map to API parameters: `enable_ocr`, `ocr_backend`, `ocr_mode`, `ocr_dpi`, etc.
- Set `ocr_backend` to `dots` or `points` after installing the respective provider.

## Tips

- Prefer `fallback` mode to reduce compute and latency when PDFs already contain text.
- Lower `ocr_dpi` for speed; raise it if recognition quality needs improvement.
- Review provider-specific known issues and constraints in their docs.

## Quick comparison

| Backend   | Modes             | Best for                          | Notes                                  |
|-----------|-------------------|-----------------------------------|----------------------------------------|
| tesseract | CLI               | Light installs, fast text         | No layout semantics, basic accuracy    |
| dots      | CLI + vLLM        | High quality OCR + layout         | Heavy; recommend vLLM; prompt-tunable  |
| points    | Transformers/SGLang | OCR + HTML tables + Markdown text | trust_remote_code required; SGLang ideal |

Note: VCS installs (extras) require `git` and network. For airgapped deployments, install upstream repos manually, then install this project without the extras.
