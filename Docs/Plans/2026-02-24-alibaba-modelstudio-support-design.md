# Alibaba Model Studio (Qwen + Image) Integration Design

Date: 2026-02-24
Status: Approved for implementation planning
Owner: Codex + user collaboration

## 1. Goal

Add first-class support for Alibaba Model Studio APIs for:

- Chat/models via existing `qwen` provider plumbing.
- Image generation via a new image backend usable from `POST /api/v1/files/create`.

This design preserves backward compatibility with current `qwen` behavior while adding region-aware routing and image generation support with both sync and async task modes.

## 2. Confirmed Scope Decisions

Validated with user:

1. Scope: both chat/model support and image support.
2. Image execution: sync + async.
3. Provider naming: keep `qwen` (no rename to `alibaba`).
4. Region coverage:
   - Include International (Singapore) and Mainland China (Beijing).
   - Include US (Virginia) where APIs support it.

## 3. Approaches Considered

## Approach A: Minimal image-only adapter, no catalog/config improvements

- Add `modelstudio` image adapter only.
- Keep manual model entry for users.

Pros:
- Fastest to ship.

Cons:
- Lower discoverability and weaker UX.
- Incomplete solution for model support goals.

## Approach B (Recommended): Structured hybrid integration

- Keep `qwen` provider key and extend region/base URL handling.
- Add `modelstudio` image backend with sync + async support.
- Add additive config fields for Model Studio image backend.
- Add catalog/listing updates (curated model IDs, configured checks).

Pros:
- Meets requested scope with low migration risk.
- Aligns with existing architecture patterns.
- Keeps implementation complexity manageable.

Cons:
- Curated model lists need occasional maintenance.

## Approach C: Dynamic model discovery at runtime

- Add live model discovery with caching/retries/fallbacks.

Pros:
- More automatically up-to-date model inventory.

Cons:
- Higher complexity and larger failure surface.
- Not necessary for first release.

Decision: Approach B.

## 4. Architecture

## 4.1 Chat Provider (`qwen`)

Keep `qwen` as the provider key and extend `QwenAdapter` base URL resolution:

Precedence:

1. Request override (`request.base_url`)
2. Env override (`QWEN_BASE_URL`)
3. Config override (`qwen_api.api_base_url`)
4. Region preset (`cn`, `sg`, `us`)

Region presets:

- `sg`: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- `us`: `https://dashscope-us.aliyuncs.com/compatible-mode/v1`
- `cn`: `https://dashscope.aliyuncs.com/compatible-mode/v1`

This preserves current behavior while making region routing explicit.

## 4.2 New Image Backend (`modelstudio`)

Add `ModelStudioImageAdapter` under:

- `tldw_Server_API/app/core/Image_Generation/adapters/modelstudio_image_adapter.py`

Register in:

- `ImageAdapterRegistry.DEFAULT_ADAPTERS` as backend name `modelstudio`.

Adapter responsibilities:

- Resolve API key + base URL + region preset.
- Support sync image generation endpoint.
- Support async submit + task polling endpoint.
- Normalize varying image response payload shapes into `ImageGenResult`.

## 4.3 Config Integration

Add additive fields in `[Image-Generation]` config parsing:

- `modelstudio_image_base_url`
- `modelstudio_image_api_key`
- `modelstudio_image_default_model`
- `modelstudio_image_region` (`cn|sg|us`)
- `modelstudio_image_mode` (`sync|async|auto`)
- `modelstudio_image_poll_interval_seconds`
- `modelstudio_image_timeout_seconds`
- `modelstudio_image_allowed_extra_params`

No existing key changes; fully backward compatible.

## 4.4 Listing/Catalog Integration

Update image backend listing and config checks:

- Include `image/modelstudio` in `list_image_models_for_catalog()`.
- Mark as configured when enabled and key present.

Update model catalog seed usage for `qwen`:

- Add curated Model Studio model IDs (text/image-relevant IDs as available).
- Continue using existing pricing catalog + configured model merge behavior.

No runtime discovery in v1.

## 5. Data Flow

## 5.1 Chat Flow

1. `/api/v1/chat/completions` receives provider=`qwen`.
2. Existing adapter dispatch remains unchanged.
3. `QwenAdapter` resolves base URL using the precedence chain above.
4. Request continues through existing OpenAI-compatible `/chat/completions` path.

## 5.2 Image Flow

1. `/api/v1/files/create` with `file_type=image`, `payload.backend=modelstudio`.
2. `ImageAdapter` validates payload and allowlisted `extra_params`.
3. Registry returns `ModelStudioImageAdapter`.
4. Adapter mode selection:
   - `sync`: direct generation request and image extraction.
   - `async`: submit task then poll until terminal state.
   - `auto`: prefer sync when supported, fallback to async.
5. Result returns through existing artifact export envelope (inline, format conversion, size checks).

## 5.3 Model Listing Flow

1. `GET /api/v1/llm/providers` composes provider/model listing.
2. Image section includes `image/modelstudio`.
3. `qwen` models include catalog/config-seeded entries.

## 6. Error Handling and Security

Error mapping:

- Missing key/base URL/disabled backend -> `image_backend_unavailable`.
- Remote generation failure, terminal failed tasks, invalid payloads, timeouts -> `image_generation_failed`.

Security and safety:

- Bearer auth only; no secret in URL/query.
- Reuse shared HTTP client for timeout/retry behavior.
- Keep strict `extra_params` allowlist enforcement.
- Preserve output size constraints and format checks.
- Do not log raw API keys.

## 7. Compatibility and Migration

- No provider rename and no endpoint contract change.
- Existing `qwen` clients keep working.
- New behavior is additive and opt-in through config + backend selection.
- Existing image backends (`stable_diffusion_cpp`, `swarmui`, `openrouter`, `novita`, `together`) unchanged.

## 8. Test Plan

Unit tests (new):

- `tests/Image_Generation/test_modelstudio_image_adapter.py`
  - Sync success paths (base64/data-url/url forms).
  - Async success path (submit + poll).
  - Async failure and timeout paths.
  - Region/base URL resolution precedence.
  - Unsupported format validation.

Unit tests (extend):

- `tests/LLM_Adapters/unit/test_qwen_native_http.py`
  - Region preset handling and override precedence.

Config/listing tests (extend):

- `tests/Image_Generation/test_image_generation_config_defaults.py`
  - Model Studio config defaults.
- `tests/Image_Generation/test_image_models_listing.py`
  - `image/modelstudio` configured/unconfigured checks.

Endpoint integration (extend):

- `tests/Files/test_files_image_endpoint.py`
  - Mocked `backend=modelstudio` path.
  - `extra_params` allowlist acceptance/rejection.

Verification gates:

- Targeted pytest suites for touched areas.
- Bandit scan on touched paths before declaring completion.

## 9. Rollout Notes

Recommended rollout:

1. Merge code guarded by config defaults (backend disabled unless explicitly enabled).
2. Add documentation updates for config and usage examples.
3. Validate with smoke tests against at least one sync model and one async model/task flow.

## 10. Implementation Boundary (v1)

Included:

- `qwen` region-aware routing.
- `modelstudio` image backend sync + async.
- Config + listing + tests.

Deferred:

- Runtime remote model discovery.
- Auto-pricing sync from provider docs.
- Advanced image edit/variation API variants.

