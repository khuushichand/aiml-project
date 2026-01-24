# PRD: Expose Image Generation Backends in /llm/models

## Summary
Expose configured image generation backends through the existing LLM models catalog (now officially cross-modality) so clients can discover image-capable backends via `/api/v1/llm/models` and `/api/v1/llm/models/metadata` without adding a new endpoint. Image backends are represented as model entries with explicit `type`, `modalities`, and `capabilities` fields so clients can filter appropriately.

## Goals
- Surface image generation backends in the existing models list used by clients.
- Ensure entries are clearly marked as **image** models via `type` and `modalities`.
- Keep changes backward-compatible for chat/embedding flows (no breakage or schema regressions).
- Formalize `/api/v1/llm/models` as a cross-modality catalog and provide filtering guidance/parameters for modality-specific lists.
- Provide a stable foundation for future “multi-modal catalog” expansion.

## Non-Goals
- Adding new image generation endpoints (this is purely discovery).
- Implementing additional image backends beyond existing registry.
- Reworking provider overrides or AuthNZ logic.
- Changing the file artifacts API behavior or export modes.

## Background / Current State
- LLM models are listed via `/api/v1/llm/models` (flat list) and `/api/v1/llm/models/metadata` (flattened metadata) built in `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`.
- Image generation backends are configured under `[Image-Generation]` and resolved via `tldw_Server_API/app/core/Image_Generation/adapter_registry.py` and `config.py`.
- Image generation is available via file artifacts (`file_type=image`) and is currently discoverable only by docs and config, not via the models list.

## User Story
“As a client integrator, I want the models list to show available image backends, so that UI surfaces and API clients can discover image generation options without hardcoding backend names.”

## Requirements
### Functional
1. **Default inclusion**: Image backends appear in `/api/v1/llm/models` and `/api/v1/llm/models/metadata` by default (no query parameter required).
2. **Stable identifiers**:
   - Model ID format: `image/<backend>` (e.g., `image/stable_diffusion_cpp`).
   - `name` is the backend key (e.g., `stable_diffusion_cpp`).
   - `provider` is set to `image`.
3. **Explicit classification**:
   - `type: "image"`.
   - `modalities: { input: ["text"], output: ["image"] }`.
   - `capabilities: { image_generation: true }`.
4. **Configuration-aware status**:
   - Include `is_configured: true|false` (best-effort) using `[Image-Generation]` config and backend validation.
   - Only include backends present in the image adapter registry and listed in `enabled_backends`; do not invent backends.
5. **Supported formats**:
   - Provide `supported_formats` from adapter if available (e.g., png/jpg/webp).
6. **Filtering (optional)**:
   - `/api/v1/llm/models` accepts optional `type`, `input_modality`, and `output_modality` filters.
   - `/api/v1/llm/models/metadata` accepts the same filters for server-side narrowing.
   - All filters are repeatable query params; values within a filter are ORed, and different filters are ANDed.
   - Default remains full catalog when no filters are provided.

### Compatibility
- Existing fields in `/llm/models/metadata` must remain unchanged for LLM entries.
- Existing LLM-only consumers should continue to function by switching to `/llm/models/metadata` filtering (or `type=chat` on `/llm/models` when available).

### Observability
- Log once per process boot (and once per config reload) if image backends cannot be evaluated (missing config, invalid paths), but do not fail the endpoint.
- Cache `is_configured` results to avoid filesystem checks on every request (TTL or config-reload keyed).

## API Changes
### `/api/v1/llm/models`
- **Before**: list of `provider/model` strings for LLM providers.
- **After**: include image backend IDs like `image/stable_diffusion_cpp` in the same list.
- **Optional filters**:
  - `type=chat|embedding|image|audio|other` (repeatable)
  - `input_modality=text|image|audio|file` (repeatable)
  - `output_modality=text|image|audio` (repeatable)
  - `include_deprecated=true|false` (existing)

### `/api/v1/llm/models/metadata`
- **Before**: flattened list of LLM metadata with `{ provider, name, capabilities, ... }`.
- **After**: append image entries with additional fields:
  - `id` (required; canonical identity, `provider/name`)
  - `type`, `modalities`, `capabilities.image_generation`, `supported_formats`, `is_configured`
  - Same optional filters as `/api/v1/llm/models`

#### Filter Examples
- Chat-only list: `/api/v1/llm/models?type=chat`
- Image generators only: `/api/v1/llm/models?type=image&output_modality=image`
- Vision-capable chat models: `/api/v1/llm/models/metadata?type=chat&input_modality=image`

## Schema / OpenAPI
- Update the Pydantic response model used by `/llm/models/metadata` to include the new fields (or use a union/discriminator on `type`).
- Ensure OpenAPI documents `/llm/models` as a cross-modality list with optional `type`/`modalities` filters.

## Data Model (Image Entry)
```json
{
  "provider": "image",
  "id": "image/stable_diffusion_cpp",
  "name": "stable_diffusion_cpp",
  "type": "image",
  "capabilities": { "image_generation": true },
  "modalities": { "input": ["text"], "output": ["image"] },
  "supported_formats": ["png", "jpg", "webp"],
  "is_configured": true
}
```
Notes:
- `id` is required and canonical; `name` is not guaranteed unique across providers.
- `supported_formats` should be normalized to lowercase file extensions; prefer a single canonical extension (e.g., `jpg` over `jpeg`) unless the adapter truly distinguishes.

## Source of Truth
- `ImageAdapterRegistry.DEFAULT_ADAPTERS` plus any dynamically registered adapters (runtime).
- `[Image-Generation]` config determines `enabled_backends` and paths. Only enabled backends are listed.

## Configuration Rules (Config-Aware Status)
For `stable_diffusion_cpp`:
- `is_configured = true` if:
  - backend is in `enabled_backends`, and
  - `sd_cpp_binary_path` exists, and
  - either `sd_cpp_diffusion_model_path` or `sd_cpp_model_path` exists.
- Otherwise `is_configured = false`.

Config keys are defined under `[Image-Generation]` in `tldw_Server_API/Config_Files/config.txt`:
- `enabled_backends`, `default_backend`
- `sd_cpp_binary_path`, `sd_cpp_diffusion_model_path`, `sd_cpp_model_path`
- `sd_cpp_llm_path`, `sd_cpp_vae_path`, `sd_cpp_lora_paths`, `sd_cpp_allowed_extra_params`
- `sd_cpp_default_steps`, `sd_cpp_default_cfg_scale`, `sd_cpp_default_sampler`, `sd_cpp_device`, `sd_cpp_timeout_seconds`

Other backends (future):
- Use backend-specific `is_configured` checks when available.
- Default to `enabled_backends` membership if no detailed checks exist.

## Frontend / Client Considerations
- The extension currently infers model type via name heuristics in `apps/tldw-frontend/extension/services/tldw/TldwModels.ts`.
- With image entries included by default, update to:
  - Prefer `type` or `modalities.output` to classify (`image` vs `chat` vs `embedding`).
  - Avoid listing `type=image` in chat dropdowns.
- The main Web UI currently does not reference `/llm/models`; if added later, it must apply the same `type`/`modalities` filtering.

## Testing
### Unit
- Image backend listing helper returns correct entries for:
  - enabled but misconfigured backend (is_configured=false)
  - enabled and configured backend (is_configured=true)
  - disabled backend (excluded if not in enabled_backends)
- Normalizes `supported_formats` to lowercase canonical extensions.
- Ensures `id` is always present and `provider/name`-shaped.

### Integration
- `/api/v1/llm/models` includes `image/<backend>` when enabled.
- `/api/v1/llm/models/metadata` includes a properly typed image entry.
- `/api/v1/llm/models?type=chat` (or metadata filter) returns no image entries.

### Frontend
- Model lists continue to show only chat models in chat UI.
- Model settings view shows image entries in the “All models” list (if desired).

## Risks / Mitigations
- **Risk**: Existing clients assume all models are chat models.
  - **Mitigation**: Mark entries explicitly with `type=image` and `modalities`. Provide `type` filters and update our own frontend logic.
- **Risk**: Incomplete config checks incorrectly report configured status.
  - **Mitigation**: Keep checks conservative and best-effort; never block listing.

## Rollout Plan
1. Server changes merged behind existing endpoints (no flags).
2. Frontend model classification updated to respect `type` and `modalities`.
3. Update docs: add note to models endpoint behavior and image discovery.

## Open Questions
- Should `/api/v1/llm/providers` also include an `image` provider entry (for consistency)?
- Should `image` entries be included in pricing catalog or remain separate?
- Do we want a dedicated “models catalog” endpoint later to unify LLM/embeddings/image/audio?
