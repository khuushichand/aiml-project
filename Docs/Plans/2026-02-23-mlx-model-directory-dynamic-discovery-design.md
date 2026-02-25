# MLX Model Directory Dynamic Discovery Design

Date: 2026-02-23
Owner: Codex + maintainer review
Status: Approved

## Goal
Enable MLX admins to define a server-side model directory, discover valid models dynamically without server restarts, and select a discovered model at load time using a safe server-resolved identifier.

## Scope
In scope:
- MLX model directory configuration via env/config (`MLX_MODEL_DIR`) only.
- New admin endpoint to list discovered MLX models.
- Extend MLX load contract to support `model_id` (relative path resolved server-side).
- Admin UI updates in `/admin/mlx` for model discovery + selection clarity.
- Backward-compatible manual `model_path` fallback.

Out of scope:
- Runtime mutation/persistence of model directory from UI/API.
- Global provider-catalog injection of discovered MLX models.
- Refactor of non-MLX local provider surfaces.

## Approved Decisions
1. Surface: API + `/admin/mlx` UI.
2. Directory source: server config/env only.
3. Discovery: recursive scan under `MLX_MODEL_DIR`.
4. Validation: manifest-based eligibility.
5. Fallback: keep manual `model_path` entry.
6. Refresh model: on-access scanning with short TTL cache.
7. Symlinks: disallowed.
8. Load selection: `model_id` primary, server-resolved.
9. Empty/invalid directory semantics: HTTP 200 + warnings + empty results.
10. Sorting/metadata: name ascending with useful metadata.
11. Manifest patterns:
   - `config.json` required
   - tokenizer required: `tokenizer.json` or `tokenizer.model`
   - weights required: one or more `*.safetensors` or `*.bin`

## Architecture
### Control Plane
- Existing lifecycle endpoints remain:
  - `POST /api/v1/llm/providers/mlx/load`
  - `POST /api/v1/llm/providers/mlx/unload`
  - `GET /api/v1/llm/providers/mlx/status`
- Add:
  - `GET /api/v1/llm/providers/mlx/models` (admin-only, rate-limited like other MLX lifecycle routes).

### Discovery Engine
- Implement model discovery in MLX provider layer (or helper) to keep endpoint thin.
- Discovery returns both selectable and non-selectable candidates, including explicit reasons for non-selectability.
- Include short in-memory TTL cache keyed by directory + scan options.
- Support `refresh=true` query flag to bypass TTL.

### Load Resolution
- Extend `MLXLoadRequest` with optional `model_id`.
- Load precedence:
  1. `model_id` (resolve relative to `MLX_MODEL_DIR` and validate)
  2. explicit `model_path`
  3. default `MLX_MODEL_PATH` (`_default_settings().model_path`)
- Preserve existing `model_path` behavior for backward compatibility.

## API Contract
### GET `/api/v1/llm/providers/mlx/models`
Response shape:
- `backend: "mlx"`
- `model_dir: string | null`
- `model_dir_configured: boolean`
- `warnings: string[]`
- `available_models: Array<MLXModelListItem>`

`MLXModelListItem`:
- `id: string` (normalized relative path; used by load API)
- `name: string` (display label)
- `relative_path: string`
- `modified_at: number | null`
- `size_bytes: number | null`
- `selectable: boolean`
- `reasons: string[]` (non-empty when not selectable)

Error semantics:
- Directory unset/invalid/inaccessible returns `200`, not hard-failure.
- `warnings` explains configuration or scan state.

### POST `/api/v1/llm/providers/mlx/load`
Request extension:
- existing `model_path?: string`
- new `model_id?: string`

Validation:
- `model_id` must be relative, normalized, and remain under `MLX_MODEL_DIR` after resolution.
- Reject absolute paths, traversal segments, and unresolved targets.
- Reject non-selectable/disallowed discovered entries when using `model_id`.

Status codes:
- `400` invalid `model_id`/resolution/eligibility.
- `500` MLX runtime/provider failures (existing behavior).

## Security and Safety
- Ignore symlinked directories/files during scans.
- Resolve real paths and enforce root containment.
- Avoid exposing absolute paths to client payloads; resolve on server from `model_id`.
- Preserve admin RBAC for all MLX lifecycle/discovery operations.

## Admin UI Design (`/admin/mlx`)
Primary flow:
1. Show configured model directory status.
2. Show discovered model selector sourced from `/mlx/models`.
3. Allow explicit refresh.
4. Load selected discovered model via `model_id`.

Clarity requirements:
- Non-selectable entries are disabled and show explicit reasons.
- UI copy explains:
  - what is selectable
  - why items are non-selectable
  - fallback to manual path/repo when needed

Fallback flow:
- Keep manual path/repo input.
- If both discovered selection and manual input are present, discovered selection is primary unless user explicitly chooses manual mode.

## Data Flow
1. UI calls `GET /mlx/models` (periodic/on-open and manual refresh).
2. Backend scans `MLX_MODEL_DIR` (or returns cached scan result within TTL).
3. UI renders selectable/non-selectable model list with reasons.
4. User selects model and clicks Load.
5. UI posts `model_id` in `POST /mlx/load`.
6. Backend resolves `model_id` -> absolute safe path -> calls existing registry `load(model_path=...)`.
7. UI refreshes `GET /mlx/status`.

## Testing Strategy
Backend tests:
- Discovery endpoint shape, warnings, sorting, and eligibility reasons.
- Recursive manifest validation cases.
- Symlink ignore behavior.
- `model_id` resolution and traversal rejection.
- Backward compatibility of existing `model_path` load behavior.

Frontend tests:
- Rendering of directory status and discovered list.
- Disabled/non-selectable entries with reason text.
- Load action uses `model_id` for discovered model.
- Manual fallback remains functional.

## Rollout and Compatibility
- Backward compatible for existing clients that only send `model_path`.
- No migration required.
- Documentation updates:
  - add `MLX_MODEL_DIR` setup guidance
  - add `/mlx/models` endpoint examples
  - clarify discovered vs manual load modes.

## Success Criteria
1. Admin sets `MLX_MODEL_DIR` and sees discovered models without restart.
2. Adding/removing model directories is reflected after refresh or TTL expiry.
3. Admin can load by choosing a discovered model identifier (`model_id`).
4. UI clearly indicates why any model is non-selectable.
5. Existing manual `model_path` load behavior continues to work.
