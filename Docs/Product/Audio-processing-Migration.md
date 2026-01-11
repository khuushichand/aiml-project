## Audio Processing Endpoint Migration Plan (`/process-audios`)

## Context

- Repo: `tldw_server2`.
- Feature track: Media Endpoint Refactor → **post–Stage 3 follow-up** (Stage 3 in the PRD is already marked “Complete – all process-only endpoints routed through `media/`”; this doc covers a deeper refactor of `/process-audios` internals).
- Current status:
  - Routing for `POST /api/v1/media/process-audios` is handled by `tldw_Server_API/app/api/v1/endpoints/media/process_audios.py`, which now owns the full HTTP-layer implementation (validation, TempDir handling, status codes).
  - Core “call audio library + merge results” logic lives in `tldw_Server_API/app/core/Ingestion_Media_Processing/audio_batch.py::run_audio_batch`.
  - `_legacy_media.process_audios_endpoint` has been reduced to a shim that simply delegates to the modular endpoint, preserving import compatibility.

## Goal

Move the implementation of `/process-audios` out of `_legacy_media.py` into the modular `media/` layer (and a small core helper), while:

- Keeping the HTTP contract **identical**:
  - Same path (`POST /api/v1/media/process-audios`), tags, rate limits, and auth behavior.
  - Same status codes and semantics (200/207/400/422/500 as in the legacy implementation).
  - Same response envelope:
    - Batch: `results`, `processed_count`, `errors_count`, `errors`.
    - Per item: `status`, `input_ref`, `processing_source`, `media_type`, `metadata`, `content`, `segments`, `chunks`, `analysis`, `analysis_details`, `keywords`, `warnings`, `error`, `db_id`, `db_message`, `message`.
- Preserving test expectations that:
  - Import `tldw_Server_API.app.api.v1.endpoints.media` / `_legacy_media`.
  - Assert on specific error messages, `input_ref` values, and audio‑specific fields (`segments`, analysis placeholder when disabled, etc.).

## Invariants to Preserve

- `input_ref`:
  - For URLs: original URL (e.g., `VALID_AUDIO_URL`), not a temp path.
  - For uploads: original filename (e.g., `SAMPLE_AUDIO_PATH.name`), not the temp path.
- `db_id` / `db_message`:
  - `db_id` remains `None`.
  - `db_message` is `"Processing only endpoint."` for processing-only routes.
- Error messages:
  - `"No valid media sources supplied"` from `_validate_inputs` for empty input.
  - Library/metadata/network errors must continue to match existing tests, including any standardized messages used to skip flaky external audio downloads (e.g., the CDN-hosted `VALID_AUDIO_URL` test now explicitly `pytest.skip`s when the host cannot be resolved in restricted environments).
- Counts and codes:
  - `processed_count` and `errors_count` computed from `status` fields (`Success` / `Warning` vs `Error`).
  - Status codes: 200 only if all items are `Success`; 207 when any item has `Warning` or when results are mixed/errors; 400 when there are no results; 422/500 from validation/internal errors as today.

---

## Phase 0 – Inventory and Safety Net

**Objective:** Understand the current behavior and lock in a baseline before refactoring.

Steps:

1. Re-read the existing implementation:
   - `_legacy_media.get_process_audios_form` and `_legacy_media.process_audios_endpoint` (Audio Processing Endpoint (REFACTORED) section).
   - `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Files.py::process_audio_files`.
   - `tldw_Server_API/app/api/v1/endpoints/media/process_audios.py`.
2. Identify key tests to rely on:
   - `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py::TestProcessAudios`.
   - `tldw_Server_API/tests/Media_Ingestion_Modification/test_add_media_endpoint.py::test_process_audio_with_analysis_mocked`.
   - Any e2e/UI tests that trigger `/process-audios` via the WebUI.
3. Run these tests before making changes to confirm the current baseline.

Success criteria:

- All identified tests are green before refactor.
- Clear understanding of:
  - How `TempDirManager`, `_save_uploaded_files`, and `file_validator_instance` are used for audio.
  - How `process_audio_files` is called (arguments, thread executor, return format).
  - How its output is transformed into the final batch (`results`, `errors`, counts).

---

## Phase 1 – Extract an Audio Batch Helper (Core Logic)

**Objective:** Move the “call audio library + merge results” part into a dedicated helper without changing behavior.

Steps:

1. Create a new helper module, e.g.:
   - `tldw_Server_API/app/core/Ingestion_Media_Processing/audio_batch.py`
2. Implement an async helper that encapsulates the core processing logic from `_legacy_media.process_audios_endpoint`, for example:
   - `async def run_audio_batch(all_inputs: List[str], *, form_data, temp_dir: str, temp_path_to_original_name: Dict[str, str], saved_files: List[Dict[str, Any]], file_errors_raw: List[Dict[str, Any]]) -> Dict[str, Any]:`
3. Inside this helper, **lift logic verbatim** from `_legacy_media.process_audios_endpoint`:
   - Build arguments for `process_audio_files` exactly as done today:
     - `inputs` (URLs + temp paths),
     - transcription options (model, language, diarize, timestamps, VAD),
     - analysis/claims options,
     - chunking options and contextual chunking fields,
     - cookies, API name, confabulation flags,
     - `temp_dir` and any user/context metadata currently passed.
   - Call `process_audio_files` via `loop.run_in_executor` with `functools.partial`, just like the legacy endpoint.
   - Merge `processing_output` into a combined `batch_result`:
     - Start from any structured file errors already present (see `_legacy_media`).
     - Map `input_ref` values from temp paths back to original filenames/URLs using `temp_path_to_original_name` and `saved_files` (for uploads).
     - Adapt library results to the expected media item shape:
       - Ensure all required keys are present (`content`, `segments`, `chunks`, `analysis`, `analysis_details`, `warnings`, etc.), using the same defaults as legacy.
       - Preserve “analysis not requested” placeholder behavior when analysis is disabled.
     - Handle library errors and unexpected formats in the same way:
       - Create error entries for each attempted input when needed, with `db_message="Processing only endpoint."`.
   - Compute and set:
     - `processed_count` (number of `status in {"Success", "Warning"}` items).
     - `errors_count` (number of `status == "Error"` items).
     - `errors` (deduplicated list of error messages).
4. The helper should import and use the **same logging/config context** as the legacy endpoint:
   - Reuse the existing `logger` and `config` objects (no new logging or config behavior).
   - Do **not** introduce `run_batch_processor` from `pipeline.py` at this stage; the goal is a behavior-preserving extraction, not a semantic change in counting/normalization.
5. The helper should **not** decide the final HTTP status code; it should return a fully-populated `batch_result` dict.

Success criteria:

- `run_audio_batch` returns a dict with the same structure that `_legacy_media.process_audios_endpoint` currently builds before returning.
- There is no change in visible behavior yet (the endpoint still runs through `_legacy_media`).

---

## Phase 2 – Move HTTP-Layer Logic into `media/process_audios.py`

**Objective:** Let the modular `media` package own the actual endpoint implementation, using shared helpers and the new audio batch helper.

Steps:

1. Replace the current thin wrapper in `tldw_Server_API/app/api/v1/endpoints/media/process_audios.py` with a full endpoint implementation that:
   - Keeps the same FastAPI signature and dependencies:
     - `background_tasks: BackgroundTasks`
     - `db: MediaDatabase = Depends(get_media_db_for_user)`
     - `form_data: ProcessAudiosForm = Depends(get_process_audios_form)`
     - `files: Optional[List[UploadFile]] = File(None, ...)`
     - `usage_log: UsageEventLogger = Depends(get_usage_event_logger)`
2. Port all HTTP-layer and orchestration logic from `_legacy_media.process_audios_endpoint` into this function:
   - Usage logging:
     - `usage_log.log_event("media.process.audio", tags=["no_db"], metadata={has_urls, has_files})`
   - Form normalization:
     - `if form_data.urls == ['']: form_data.urls = None`.
   - Input validation:
     - Call `_validate_inputs("audio", form_data.urls, files)` via the `media` shim (i.e., through `tldw_Server_API.app.api.v1.endpoints.media` / `_legacy_media`) to avoid duplicating validation rules.
   - Temporary directory and upload handling:
     - Use `TempDirManager(cleanup=True, prefix="process_audio_")`.
     - Resolve `validator` via the `media` shim (`media.file_validator_instance`), with fallback to the API deps-exported `file_validator_instance`, and write it back into `_legacy_media` for modules that read globals.
     - Call `save_uploaded_files` to get `saved_files` and `file_errors_raw`.
     - Populate `temp_path_to_original_name` for uploads.
     - Adapt file errors into the audio result structure (per legacy code) and seed the initial `batch_result` with those entries and error counters.
   - Input preparation:
     - Build `url_list` from `form_data.urls` and `uploaded_paths` from `saved_files`.
     - `all_inputs = url_list + uploaded_paths`.
   - Early-exit behavior:
     - If no inputs but there were file errors → return 207 with the structured file errors.
     - If no inputs at all → raise `HTTPException(400, "No valid media sources supplied.")`.
3. Build an initial `batch_result` dict in `media/process_audios.py` mirroring the legacy structure:
   - Seed `results` with structured file errors.
   - Set `processed_count`, `errors_count`, and `errors` according to file errors only.
4. Call the new core helper:
   - `batch_result = await run_audio_batch(all_inputs=all_inputs, form_data=form_data, temp_dir=str(temp_dir), temp_path_to_original_name=temp_path_to_original_name, saved_files=saved_files, file_errors_raw=file_errors_raw)`
   - The helper should return a full batch, merged with any file errors.
5. Determine the final HTTP status code **in `media/process_audios.py`** using the existing rules:
   - Count processed vs error items with the same logic used today (both `Success` and `Warning` count as processed).
   - 400 when there are no results; 200 when there are processed items and zero errors; 207 when there is any mix of error/non-error items.
   - Preserve existing logging around the final status and counts.
6. Return the response:
   - `return JSONResponse(status_code=final_status_code, content=batch_result)`

Notes:

- For the initial migration, it is acceptable **not** to use `run_batch_processor` from `pipeline.py`; the priority is behavior parity. A later iteration can consider layering `run_batch_processor` on top of `run_audio_batch` if that can be done without changing counts or error semantics.

Success criteria:

- All `/process-audios` HTTP behavior is now implemented in `media/process_audios.py` + `audio_batch.py`.
- `_legacy_media.process_audios_endpoint` is no longer responsible for the real work, but tests remain green.

---

## Phase 3 – Turn `_legacy_media.process_audios_endpoint` into a Shim

**Objective:** Keep `_legacy_media` import compatibility while delegating actual work to the modular endpoint.

Steps:

1. In `_legacy_media.py`, remove the `@router.post("/process-audios", ...)` decorator from `process_audios_endpoint`.
2. Replace the body of `process_audios_endpoint` with a thin delegating wrapper:
   - Import the modular implementation:
     - `from tldw_Server_API.app.api.v1.endpoints.media.process_audios import process_audios_endpoint as _process_audios_impl`
   - Forward all parameters:
     - `return await _process_audios_impl(background_tasks=background_tasks, db=db, form_data=form_data, files=files, usage_log=usage_log)`
3. Ensure the function signature remains identical so any direct calls from tests or other modules still succeed.
4. Confirm that `media/__init__.py` continues to prepend `process_audios.router.routes` before `legacy_router.routes`, so the only active HTTP route for `/process-audios` is the modular one.

Success criteria:

- Importers of `_legacy_media.process_audios_endpoint` still work as before.
- Actual HTTP traffic for `/process-audios` is handled only by the modular endpoint.

---

## Phase 4 – Testing and Verification

**Objective:** Demonstrate that behavior is unchanged from the perspective of HTTP clients and tests.

Steps:

1. Run focused tests:
   - `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py::TestProcessAudios`
   - `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_add_media_endpoint.py::test_process_audio_with_analysis_mocked`
   - Any relevant WebUI/e2e tests that exercise `/process-audios`.
2. Compare key expectations:
   - Status codes (200/207/400/422) for the same inputs as before.
   - `input_ref` values for:
     - URL inputs (`VALID_AUDIO_URL`).
     - Uploaded files (`SAMPLE_AUDIO_PATH.name`).
   - Audio-specific fields:
     - `content` is a string (possibly empty when transcription fails or is stubbed).
     - `segments` is a list when transcription succeeds.
     - When `perform_analysis=False` and `perform_chunking=False`, `analysis` and `chunks` are `None` or the documented “not requested” placeholder used in tests.
   - `db_id` / `db_message` values for processing-only endpoints.
3. If any discrepancy appears:
   - Adjust the helper / endpoint to match the legacy behavior, rather than changing tests, unless tests are clearly incorrect and the PRD indicates the older behavior was a bug.

Success criteria:

- All identified tests remain green after the migration.
- Manual inspection (or logging) shows response payloads and status codes matching legacy behavior for representative URL and upload cases, including mixed-success 207 responses.

---

## Future Optional Work (Post-Migration)

These are **not** required for the initial migration, but may be considered after behavior parity is proven:

- Consider introducing `run_batch_processor` from `pipeline.py` as a thin layer around per-item audio processing:
  - Define a per-item audio processor that turns simple `ProcessItem` structs into result dicts.
  - Use `run_batch_processor` to handle counts and normalization, then merge any audio-specific fields or debug metadata.
- Factor out any patterns shared between video and audio processing once both are modular and well-tested (e.g., shared input mapping, shared error normalization).

The migration should be considered complete once:

- `media/process_audios.py` + a small core helper own the `/process-audios` logic.
- `_legacy_media.process_audios_endpoint` is shim-only.
- No external behavior changes are observable to API clients and tests.
