# DeepSeek OCR Backend

This document describes how to enable and operate the DeepSeek-OCR backend in tldw_server. This backend runs local HuggingFace Transformers inference only.

## Summary

- Backend name: `deepseek`
- API usage: set `enable_ocr=true` and `ocr_backend=deepseek` in PDF processing/evaluation endpoints.
- Mode: local Transformers only (no server mode in this integration).

## Recommended Prompt

Default prompt (layout-aware, Markdown output):
```
<image>
<|grounding|>Convert the document to markdown.
```

For plain text (no layout), you can use:
```
<image>
Free OCR.
```

Override with `DEEPSEEK_OCR_PROMPT`.

## Environment Variables

- `DEEPSEEK_OCR_MODEL_ID`: HF model id or local path (default: `deepseek-ai/DeepSeek-OCR`).
- `DEEPSEEK_OCR_PROMPT`: Prompt override.
- `DEEPSEEK_OCR_BASE_SIZE`: Base resolution size (default: `1024`).
- `DEEPSEEK_OCR_IMAGE_SIZE`: Secondary resolution size (default: `640`).
- `DEEPSEEK_OCR_CROP_MODE`: `true|false` (default: `true`).
- `DEEPSEEK_OCR_SAVE_RESULTS`: `true|false` (default: `false`).
- `DEEPSEEK_OCR_TEST_COMPRESS`: `true|false` (default: `false`).
- `DEEPSEEK_OCR_DTYPE`: `bfloat16|float16|float32` (default: `bfloat16`).
- `DEEPSEEK_OCR_ATTN_IMPL`: Attention implementation (default: `flash_attention_2`).
- `DEEPSEEK_OCR_DEVICE`: `cuda|cpu` (default: `cuda`).
- `DEEPSEEK_OCR_OUTPUT_DIR`: Optional output directory when `DEEPSEEK_OCR_SAVE_RESULTS=true`.

Resolution presets (optional mapping):
- Tiny: base_size=512, image_size=512, crop_mode=false
- Small: base_size=640, image_size=640, crop_mode=false
- Base: base_size=1024, image_size=1024, crop_mode=false
- Large: base_size=1280, image_size=1280, crop_mode=false
- Gundam: base_size=1024, image_size=640, crop_mode=true

## Installation

1) Install a CUDA-compatible PyTorch build.
2) Install `transformers` and FlashAttention (if using `flash_attention_2`).
3) Ensure the model repo is cached or accessible.

Security note:
- Upstream requires `trust_remote_code=True` for model loading. Only enable this in controlled environments and review the code you execute.

## Using with API Endpoints

Any endpoint that accepts OCR options can use DeepSeek:
- PDF ingestion: `POST /api/v1/media/process`
- OCR evaluation (PDFs): `POST /api/v1/evaluations/ocr-pdf`

Example (form fields):
- `enable_ocr=true`
- `ocr_backend=deepseek`
- `ocr_mode=fallback` (or `always`)
- `ocr_dpi=300`

## Performance Tips

- Prefer `ocr_mode=fallback` to reduce compute when PDFs already contain text.
- Keep `OCR_PAGE_CONCURRENCY` low (1-2) for GPU-backed OCR.
- Lower `ocr_dpi` for speed; raise it if recognition quality needs improvement.
- If you enable `DEEPSEEK_OCR_SAVE_RESULTS`, set `DEEPSEEK_OCR_OUTPUT_DIR` to persist outputs; otherwise results are stored in a temporary directory.

## Troubleshooting

- Ensure `torch` and `transformers` import cleanly and CUDA is available.
- If the backend is not detected, check `DEEPSEEK_OCR_DEVICE` and your CUDA/driver setup.
- If output includes extra tokens or odd formatting, try a simpler prompt and reduce resolution.
