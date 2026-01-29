# PRD: Image Generation Adapter for File Artifacts API

## Overview
Extend the File Artifacts API to support image generation via a backend adapter registry. The first backend adapter will be stable-diffusion.cpp. Clients will call the existing file creation endpoint to generate an image, choose a configured backend, and receive the image inline (base64) without storing the image on disk or in the database.

## Goals
- Add an image file type to the File Artifacts API using the existing adapter registry pattern.
- Allow users to choose from configured image backends per request.
- Ship stable-diffusion.cpp as the first backend adapter.
- Return images inline (base64) and do not persist image bytes server-side.
- Provide clear validation, limits, and error messages for image generation requests.

## Non-Goals
- UI/UX work or frontend flows.
- Long-lived storage, galleries, or asset management.
- Image editing, inpainting, or upscaling (can be added later).
- Multi-image batches or streaming outputs in v1.
- Network-based image fetching or remote hosting of outputs.

## Target Users
- API clients that need on-demand image generation.
- Internal services that want a unified file creation interface for images.

## Core Requirements
1. `POST /api/v1/files/create` must accept `file_type: "image"` with an image payload.
2. Backend selection must be explicit (`payload.backend`) or default to a configured backend.
3. Export must be inline only (base64) to avoid server-side storage of image bytes.
4. Requests must be rejected if the backend is not configured or disabled.
5. Provide deterministic output via seed controls where supported.
6. Enforce strict size, resolution, and runtime limits to prevent resource exhaustion.
7. Enforce an allowlist for `extra_params` keys per backend (deny by default).
8. Persist remains required to create the artifact, but image bytes are never stored.

## API Contract

### Create Image Artifact
`POST /api/v1/files/create`

Allowed image export formats are backend-specific (no server-side conversion in v1).

Request:
```json
{
  "file_type": "image",
  "title": "optional display name",
  "payload": {
    "backend": "stable_diffusion_cpp",
    "prompt": "A neon-lit city street in the rain",
    "negative_prompt": "blurry, low quality",
    "width": 768,
    "height": 512,
    "steps": 25,
    "cfg_scale": 7.5,
    "seed": 123456789,
    "sampler": "euler_a",
    "model": "optional backend-specific model id",
    "extra_params": {
      "clip_skip": 2
    }
  },
  "export": {
    "format": "webp",
    "mode": "inline",
    "async_mode": "sync"
  },
  "options": {
    "persist": true,
    "max_bytes": 4000000
  }
}
```

Response (inline only):
```json
{
  "artifact": {
    "file_id": 456,
    "file_type": "image",
    "title": "image_artifact",
    "structured": {
      "backend": "stable_diffusion_cpp",
      "prompt": "A neon-lit city street in the rain",
      "negative_prompt": "blurry, low quality",
      "width": 768,
      "height": 512,
      "steps": 25,
      "cfg_scale": 7.5,
      "seed": 123456789,
      "sampler": "euler_a",
      "model": "optional backend-specific model id",
      "extra_params": {"clip_skip": 2}
    },
    "validation": {"ok": true, "warnings": []},
    "export": {
      "status": "none",
      "format": "webp",
      "content_type": "image/webp",
      "bytes": 354112,
      "content_b64": "<base64>"
    },
    "created_at": "2026-01-01T12:00:00Z",
    "updated_at": "2026-01-01T12:00:00Z"
  }
}
```

### Retrieve Image Artifact
`GET /api/v1/files/{file_id}`

Response (metadata only; no export bytes):
```json
{
  "artifact": {
    "file_id": 456,
    "file_type": "image",
    "title": "image_artifact",
    "structured": {
      "backend": "stable_diffusion_cpp",
      "prompt": "A neon-lit city street in the rain",
      "negative_prompt": "blurry, low quality",
      "width": 768,
      "height": 512,
      "steps": 25,
      "cfg_scale": 7.5,
      "seed": 123456789,
      "sampler": "euler_a",
      "model": "optional backend-specific model id",
      "extra_params": {"clip_skip": 2}
    },
    "validation": {"ok": true, "warnings": []},
    "export": {
      "status": "none",
      "format": "webp",
      "content_type": "image/webp",
      "bytes": null
    },
    "created_at": "2026-01-01T12:00:00Z",
    "updated_at": "2026-01-01T12:00:00Z"
  }
}
```

### Error Codes
- `unsupported_file_type` (400): `file_type` not registered.
- `image_backend_unavailable` (400): backend not configured or disabled.
- `unsupported_export_format` (422): export format not allowed for images.
- `invalid_export_mode` (422): export mode must be inline for images.
- `invalid_async_mode` (422): async_mode not allowed for images.
- `export_size_exceeded` (422): output size exceeds configured limits.
- `image_params_invalid` (422): invalid width/height/steps/seed/etc.
- `image_generation_failed` (500): backend returned a failure.

## Payload Schema (file_type=image)
Required:
- `backend` (string): backend key registered in the image adapter registry.
- `prompt` (string): primary prompt text.

Optional:
- `negative_prompt` (string)
- `width` (int)
- `height` (int)
- `steps` (int)
- `cfg_scale` (float)
- `seed` (int)
- `sampler` (string)
- `model` (string)
- `extra_params` (object): backend-specific knobs; only allowlisted keys are accepted (deny by default).

Defaults should be sourced from config when fields are omitted.
`options.persist` must be `true` to create the artifact; image bytes are never stored.
`options.max_bytes` is enforced, and image outputs are additionally capped by `[Image-Generation].inline_max_bytes` (falling back to `Files.inline_max_bytes`).

## Adapter Architecture

### Image Adapter Registry
Introduce a dedicated image adapter registry that mirrors existing patterns in LLM/TTS:
- Registry maps backend keys to adapter classes (lazy imports).
- Exposes `get_adapter(backend)` and `list_backends()`.
- Supports per-backend config injection.

### File Artifacts Image Adapter
Add a `FileAdapter` implementation for `file_type="image"` that:
- Normalizes and validates the image payload.
- Delegates generation to the selected backend adapter.
- Returns bytes via `ExportResult` (inline only).
- Rejects `export.mode="url"` and `export.async_mode!="sync"`.
  - Accepts formats supported by the selected backend adapter.

### Backend Adapter Interface
Define an interface, for example:
```
class ImageGenerationAdapter(Protocol):
    name: str
    supported_formats: set[str]
    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        ...
```

## stable-diffusion.cpp Adapter (v1)
- Backend key: `stable_diffusion_cpp`.
- Execution model: spawn the `stable-diffusion.cpp` CLI via subprocess.
- Output handling:
  - Render to a temporary file in a temp dir.
  - Read bytes into memory.
  - Delete the file and directory immediately after read.
- Timeouts and resource limits:
  - Hard timeout per request (configurable).
  - Concurrency guard (configurable max concurrent jobs).
- Formats: use backend-native output (no conversion in v1).

### Config Requirements
Add configuration for image backends in `Config_Files/config.txt` under `[Image-Generation]`:
- `default_backend`
- `enabled_backends` (JSON array)
- `max_width`, `max_height`, `max_pixels`
- `max_steps`, `max_prompt_length`
- `inline_max_bytes` (override Files.inline_max_bytes for images)

stable-diffusion.cpp specific (same section):
- `sd_cpp_binary_path`
- `sd_cpp_diffusion_model_path`
- `sd_cpp_model_path`
- `sd_cpp_llm_path`
- `sd_cpp_vae_path` (optional)
- `sd_cpp_lora_paths` (optional JSON array)
- `sd_cpp_allowed_extra_params` (optional JSON array allowlist for extra_params)
- `sd_cpp_default_steps`, `sd_cpp_default_cfg_scale`
- `sd_cpp_default_sampler`
- `sd_cpp_device` (cpu/cuda/metal) where supported
- `sd_cpp_timeout_seconds`

## Delivery and Storage Rules
- Inline export only; no `url` mode for images in v1.
- No image bytes stored in DB.
- No server-side export files written to user temp outputs.
- Temporary files created by the backend adapter must be deleted immediately after reading.
- Reject outputs that exceed configured byte limits (return `export_size_exceeded`).
- Inline responses use `export.status="none"` with `content_b64` populated.
- `GET /api/v1/files/{id}` returns the image artifact metadata without export bytes; export fields are present with `export.status="none"`, `content_b64` omitted, and `bytes=null`.

## Limits and Validation
- Enforce width, height, steps, and pixel count caps from config.
- Enforce max bytes for raw image output (before base64 encoding).
- Enforce prompt length and disallow empty prompt.
- Enforce `format` in the selected backend's supported formats.
- Reject async generation for images in v1.

## Observability
- Metrics:
  - `image_generation_requests_total{backend,status}`
  - `image_generation_latency_ms{backend}`
  - `image_generation_bytes{backend}`
- Logging:
  - Log request_id, backend, duration, and output size.
  - Do not log full prompts by default (optional redaction or hash).

## Testing
- Unit tests:
  - Payload normalization and validation for image file type.
  - Backend registry selection and fallback to default.
  - Export mode enforcement (inline only).
- Integration tests:
  - Mock backend adapter returns a fixed PNG; validate response schema.
- Optional external tests:
  - stable-diffusion.cpp adapter integration (skipped unless configured).

## Rollout
- Gate behind `image_generation.enabled_backends`.
- Document new config in `Docs/Operations/Env_Vars.md` and config templates.
- Add API docs entries for `file_type=image`.
- Follow-up: add async generation with ephemeral in-memory cache if needed.
