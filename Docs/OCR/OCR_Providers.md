# OCR Providers Setup

This guide covers enabling and using optional OCR providers with the PDF pipeline. You can select the provider via the `ocr_backend` option in API/WebUI forms.

Supported backends
- tesseract (built-in, CLI)
- dots (dots.ocr project)
- points (Tencent POINTS-Reader)
- deepseek (DeepSeek-OCR, Transformers)
- hunyuan (Tencent HunyuanOCR, vLLM + Transformers)
- dolphin (ByteDance Dolphin-v2, Transformers + remote server)

Common usage
- Set `enable_ocr=true` and choose `ocr_backend` (`tesseract`, `dots`, `points`, `deepseek`, `hunyuan`, or `dolphin`).
- `ocr_mode`: `fallback` (only pages lacking text) or `always` (force OCR).
- `ocr_dpi`: 200-300 is a good balance.
- Structured outputs:
  - `ocr_output_format`: `text|markdown|json`
  - `ocr_prompt_preset`: `general|doc|table|spotting|json`
- Parallelism: `OCR_PAGE_CONCURRENCY` controls per-page OCR concurrency (default 1). Keep small (1-2) for GPU-backed models.
- Config override: `Config_Files/config.txt` supports `[OCR] backend_priority` (comma-separated list or JSON array) to control auto selection order.

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

## DeepSeek-OCR (backend: `deepseek`)

Summary
- Local Transformers-only backend (no server mode yet).
- Requires `trust_remote_code=True` and GPU-friendly dependencies.
- Default prompt targets Markdown conversion with layout grounding; override via env.

Environment
- `DEEPSEEK_OCR_MODEL_ID` (default: `deepseek-ai/DeepSeek-OCR`)
- `DEEPSEEK_OCR_PROMPT` (default: markdown conversion prompt)
- `DEEPSEEK_OCR_BASE_SIZE`, `DEEPSEEK_OCR_IMAGE_SIZE`, `DEEPSEEK_OCR_CROP_MODE`
- `DEEPSEEK_OCR_DTYPE` (default: `bfloat16`)
- `DEEPSEEK_OCR_ATTN_IMPL` (default: `flash_attention_2`)
- `DEEPSEEK_OCR_DEVICE` (default: `cuda`)
- `DEEPSEEK_OCR_SAVE_RESULTS` (default: `false`)
- `DEEPSEEK_OCR_TEST_COMPRESS` (default: `false`)
- `DEEPSEEK_OCR_OUTPUT_DIR` (optional; used when `DEEPSEEK_OCR_SAVE_RESULTS=true`)

Install (manual)
- Install a compatible `torch`, `transformers`, and flash-attn stack for your CUDA version.
- Set `DEEPSEEK_OCR_MODEL_ID` if you want a local cache path or different repo.
- Security note: upstream requires `trust_remote_code=True`; use only in controlled environments.

Docs
- See `Docs/OCR/DeepSeek-OCR.md` for setup details and prompt tips.

## HunyuanOCR (backend: `hunyuan`)

Summary
- Supports vLLM (OpenAI-compatible) and local Transformers.
- Good for structured outputs when paired with `ocr_output_format=json` or prompt presets.

Environment
- `HUNYUAN_MODE`: `auto` (default), `vllm`, `transformers`.
- `HUNYUAN_PROMPT`: prompt override (free-form).
- `HUNYUAN_PROMPT_PRESET`: `general|doc|table|spotting|json`.

vLLM
- `HUNYUAN_VLLM_URL`: OpenAI-compatible `/v1/chat/completions` endpoint.
- `HUNYUAN_VLLM_MODEL`: served model name.
- `HUNYUAN_VLLM_TIMEOUT`: request timeout seconds.
- `HUNYUAN_VLLM_USE_DATA_URL`: `true` to send base64 image URLs (recommended).

Transformers
- `HUNYUAN_MODEL_PATH` (default: `tencent/HunyuanOCR`).
- `HUNYUAN_DEVICE` (optional: `cuda`, `cpu`, etc.).

Generation / post-processing
- `HUNYUAN_MAX_NEW_TOKENS`, `HUNYUAN_TEMPERATURE`, `HUNYUAN_DO_SAMPLE`.
- `HUNYUAN_CLEAN_REPEATS`: `true|false` (default `true`).

Docs
- See `Docs/OCR/HunyuanOCR.md` for setup details and usage notes.

## Dolphin (backend: `dolphin`)

Summary
- Supports local Transformers inference (ByteDance/Dolphin-v2) and remote Dolphin servers.
- Returns Markdown as-is; also captures JSON outputs inline when enabled.
- Opt-in only (use `ocr_backend=dolphin` or include in `OCR.backend_priority`).

Environment
- `DOLPHIN_MODE`: `auto` (default), `transformers`, `remote`.
- `DOLPHIN_PROMPT`: override main prompt.
- `DOLPHIN_PROMPT_PRESET`: `general|doc|table|json` (default picks `doc`).
- `DOLPHIN_JSON_PROMPT`: override JSON prompt (empty disables).
- `DOLPHIN_DISABLE_JSON`: `true` to skip JSON extraction pass.

Remote (Dolphin servers)
- `DOLPHIN_URL`: server base URL.
- `DOLPHIN_REMOTE_MODE`: `dolphin_vllm` (expects `encoder_prompt` + `decoder_prompt`), `dolphin_trt` (expects `prompt`), or `openai`.
- `DOLPHIN_ENCODER_PROMPT`: override encoder prompt (vLLM mode).
- `DOLPHIN_DECODER_PROMPT`: override decoder prompt (vLLM/TRT).
- `DOLPHIN_REMOTE_MODEL`: model name for OpenAI-compatible mode.
- `DOLPHIN_TIMEOUT`: request timeout seconds (default 60).
- `DOLPHIN_USE_DATA_URL`: `true` to send base64 image URLs (recommended for remote).

Local Transformers
- `DOLPHIN_MODEL_PATH` (default: `ByteDance/Dolphin-v2`).
- `DOLPHIN_DEVICE` (optional: `cuda`, `cpu`, etc.).

Generation controls
- `DOLPHIN_MAX_NEW_TOKENS`, `DOLPHIN_MAX_LENGTH`, `DOLPHIN_TEMPERATURE`
- `DOLPHIN_TOP_P`, `DOLPHIN_TOP_K`, `DOLPHIN_REPETITION_PENALTY`
- `DOLPHIN_DO_SAMPLE`, `DOLPHIN_NUM_BEAMS`

Notes
- If `ocr_output_format=json` is requested but JSON parsing fails, the backend returns Markdown and logs a warning.

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
| deepseek  | Transformers      | Layout-rich OCR to Markdown       | Heavy GPU stack; trust_remote_code required |
| hunyuan   | vLLM/Transformers | Structured OCR + JSON outputs     | vLLM recommended for quality/speed     |

Note: VCS installs (extras) require `git` and network. For airgapped deployments, install upstream repos manually, then install this project without the extras.
