## Video Processing Endpoint Migration Plan (`/process-videos`)

**Context**

- Repo: `tldw_server2`.
- Feature track: Media Endpoint Refactor → **post–Stage 3 follow-up** (Stage 3 in the PRD is already marked “Complete – all process-only endpoints routed through `media/`”; this doc covers a deeper refactor of `/process-videos` internals).
- Current status:
  - Routing for `POST /api/v1/media/process-videos` is already modularized via `tldw_Server_API/app/api/v1/endpoints/media/process_videos.py` as a thin wrapper that delegates to `_legacy_media.process_videos_endpoint`.
  - The full implementation still lives in `_legacy_media.py`.

**Goal**

Move the implementation of `/process-videos` out of `_legacy_media.py` into the modular `media/` layer (and a small core helper), while:

- Keeping the HTTP contract **identical**:
  - Same path (`POST /api/v1/media/process-videos`), tags, rate limits, and auth behavior.
  - Same status codes and semantics (200/207/400/422/500 as in the legacy implementation).
  - Same response envelope:
    - Batch: `results`, `processed_count`, `errors_count`, `errors`, `confabulation_results`.
    - Per item: `status`, `input_ref`, `processing_source`, `media_type`, `metadata`, `content`, `segments`, `chunks`, `analysis`, `analysis_details`, `keywords`, `warnings`, `error`, `db_id`, `db_message`, `message`.
- Preserving test expectations that:
  - Import `tldw_Server_API.app.api.v1.endpoints.media` / `_legacy_media`.
  - Assert on specific error messages and `input_ref` values.

**Invariants to Preserve**

- `input_ref`:
  - For URLs: the original URL (e.g., `VALID_VIDEO_URL`), not a temp path.
  - For uploads: the original filename (e.g., `SAMPLE_VIDEO_PATH.name`).
- `db_id` / `db_message`:
  - `db_id` remains `None`.
  - `db_message` is `"Processing only endpoint."` for processing-only routes.
- Error messages:
  - `"No valid video sources supplied."` when nothing valid is provided.
  - Metadata / network failures must continue to match existing tests (including `Download failed for <URL>` being appended when appropriate).
- Counts and codes:
  - `processed_count` and `errors_count` computed from `status` fields (`Success` vs `Error`).
  - Status codes: 200 when all items succeed/warn, 207 for mixed/all error, 400 when there are no results.

---

## Phase 0 – Inventory and Safety Net

**Objective:** Understand the current behavior and lock in a baseline before refactoring.

Steps:

1. Re-read the existing implementation:
   - `tldw_Server_API/app/api/v1/endpoints/_legacy_media.py::process_videos_endpoint`
   - `tldw_Server_API/app/api/v1/endpoints/media/process_videos.py`
2. Identify key tests to rely on:
   - `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py::TestProcessVideos`
   - `tldw_Server_API/tests/Media_Ingestion_Modification/test_add_media_endpoint.py::test_process_video_with_analysis_mocked`
   - `tldw_Server_API/tests/e2e/fixtures.py` (uses `"process-videos"`), plus any relevant WebUI tests.
3. Run the focused tests before making changes to confirm the current baseline behavior.

Success criteria:

- All identified tests are green prior to refactor.
- Clear understanding of:
  - How `TempDirManager`, `_save_uploaded_files`, and `file_validator_instance` are used.
  - How `Video_DL_Ingestion_Lib.process_videos` is invoked and how its output is merged into the batch.

---

## Phase 1 – Extract a Video Batch Helper (Core Logic)

**Objective:** Move the “call video library + merge results” part into a dedicated helper without changing behavior.

Steps:

1. Create a new helper module, e.g.:
   - `tldw_Server_API/app/core/Ingestion_Media_Processing/video_batch.py`
2. Implement an async helper that encapsulates the core processing logic from `_legacy_media.process_videos_endpoint`, for example:
   - `async def run_video_batch(all_inputs_to_process: List[str], *, form_data, current_user, temp_dir: str, temp_path_to_original_name: Dict[str, str], file_handling_errors_structured: List[Dict[str, Any]]) -> Dict[str, Any]:`
3. Inside this helper, **lift logic verbatim** from `_legacy_media.process_videos_endpoint`:
   - Build `video_args` exactly as done today:
     - `inputs`, `start_time`, `end_time`, `diarize`, `vad_use`,
     - transcription options,
     - analysis and chunking options,
     - cookies / timestamp / confabulation flags,
     - `temp_dir`, `user_id`.
   - Call `Video_DL_Ingestion_Lib.process_videos` via `loop.run_in_executor` with `functools.partial`, just like the legacy endpoint.
   - Merge `processing_output` into a combined `batch_result`:
     - Start from `file_handling_errors_structured`.
     - Map `input_ref` values from temp paths back to original filenames/URLs using `temp_path_to_original_name`.
     - Attach `db_id = None` and `db_message = "Processing only endpoint."`.
     - Wire `confabulation_results` if present.
     - Standardize “download failed” errors for remote URLs exactly as in legacy.
   - Handle:
     - Unexpected return types from `process_videos` (log and create per-input error entries).
     - Exceptions during execution (wrap into `Error` results for all attempted inputs).
   - Compute and set:
     - `processed_count` (number of `status == "Success"` items).
     - `errors_count` (number of `status == "Error"` items).
     - `errors` (deduplicated list of error messages).
4. The helper should import and use the **same logging/config context** as the legacy endpoint:
   - Reuse the existing `logger` and `config` objects (no new logging or config behavior).
   - Do **not** introduce `run_batch_processor` from `pipeline.py` at this stage; the goal is a behavior-preserving extraction, not a semantic change in counting/normalization.
4. The helper should **not** decide the final HTTP status code; it should return a fully-populated `batch_result` dict.

Success criteria:

- `run_video_batch` returns a dict with the same structure that `_legacy_media.process_videos_endpoint` used to build before returning.
- There is no change in visible behavior yet (the endpoint still runs through `_legacy_media`).

---

## Phase 2 – Move HTTP-Layer Logic into `media/process_videos.py`

**Objective:** Let the modular `media` package own the actual endpoint implementation, using shared helpers and the new video batch helper.

Steps:

1. Replace the current thin wrapper in `tldw_Server_API/app/api/v1/endpoints/media/process_videos.py` with a full endpoint implementation that:
   - Keeps the same FastAPI signature and dependencies:
     - `background_tasks: BackgroundTasks`
     - `db: MediaDatabase = Depends(get_media_db_for_user)`
     - `form_data: ProcessVideosForm = Depends(get_process_videos_form)`
     - `files: Optional[List[UploadFile]] = File(None, ...)`
     - `current_user: User = Depends(get_request_user)`
     - `usage_log: UsageEventLogger = Depends(get_usage_event_logger)`
2. Port all HTTP-layer and orchestration logic from `_legacy_media.process_videos_endpoint` into this function:
   - Usage logging:
     - `usage_log.log_event("media.process.video", tags=["no_db"], metadata={...})`
   - Form normalization:
     - `if form_data.urls == ['']: form_data.urls = None`.
   - Input validation:
     - Call `_validate_inputs("video", form_data.urls, files)` via the `media` shim (i.e., through `tldw_Server_API.app.api.v1.endpoints.media` / `_legacy_media`) to avoid duplicating validation rules.
   - Temporary directory setup:
     - Use `TempDirManager(cleanup=True, prefix="process_video_")`.
   - File saving:
     - Call `save_uploaded_files` (aliased via `_save_uploaded_files` from `input_sourcing`) to get `saved_files_info` + `file_handling_errors_raw`.
   - `temp_path_to_original_name` mapping and `file_handling_errors_structured` construction:
     - Use exactly the same transformation and error messages as in the legacy code.
   - Input preparation:
     - `url_list = form_data.urls or []`
     - `uploaded_paths = [str(sf["path"]) for sf in saved_files_info if sf.get("path")]`
     - `all_inputs_to_process = url_list + uploaded_paths`
   - Early-exit behavior:
     - If no inputs but there were file errors → return 207 with the structured file errors.
     - If no inputs at all → raise `HTTPException(400, "No valid video sources supplied.")`.
3. Build an initial `batch_result` dict in `media/process_videos.py`:
   - Include:
     - `results` seeded with `file_handling_errors_structured`.
     - `processed_count`, `errors_count`, and `errors` reflecting just the file errors (mirroring legacy behavior).
     - `confabulation_results: None`.
4. Call the new core helper:
   - `batch_result = await run_video_batch(all_inputs_to_process=..., form_data=form_data, current_user=current_user, temp_dir=str(temp_dir), temp_path_to_original_name=temp_path_to_original_name, file_handling_errors_structured=file_handling_errors_structured)`
   - The helper should return a full batch, merged with any file errors.
5. Determine the final HTTP status code **in `media/process_videos.py`** using the existing rules:
   - `total_items = len(batch_result["results"])`
   - `final_error_count = batch_result["errors_count"]`
   - If `total_items == 0` → 400.
   - Else if `final_error_count == 0` → 200.
   - Else (all errors or mixed) → 207.
   - Preserve the existing logging (INFO vs WARNING) and debug logging for the final batch.
6. Return the response:
   - `return JSONResponse(status_code=final_status_code, content=batch_result)`

Notes:

- For the initial migration, it is acceptable **not** to use `run_batch_processor` from `pipeline.py` directly; the priority is behavior parity. A later iteration can consider layering `run_batch_processor` on top of `run_video_batch`.

Success criteria:

- All `/process-videos` HTTP behavior is now implemented in `media/process_videos.py` + `video_batch.py`.
- `_legacy_media.process_videos_endpoint` is no longer responsible for the real work, but tests remain green.

---

## Phase 3 – Turn `_legacy_media.process_videos_endpoint` into a Shim

**Objective:** Keep `_legacy_media` import compatibility without owning the endpoint implementation.

Steps:

1. In `_legacy_media.py`, remove the `@router.post("/process-videos", ...)` decorator from `process_videos_endpoint`.
2. Replace the body of `process_videos_endpoint` with a thin delegating wrapper:
   - Import the modular implementation:
     - `from tldw_Server_API.app.api.v1.endpoints.media.process_videos import process_videos_endpoint as _process_videos_impl`
   - Forward all parameters:
     - `return await _process_videos_impl(background_tasks=background_tasks, db=db, form_data=form_data, files=files, current_user=current_user, usage_log=usage_log)`
3. Ensure the function signature remains identical so any direct calls in tests or other modules still succeed.
4. Confirm that `media/__init__.py` continues to prepend `process_videos.router.routes` before `legacy_router.routes`, so the only active HTTP route is the modular one.

Success criteria:

- Importers of `_legacy_media.process_videos_endpoint` still work.
- Actual HTTP traffic for `/process-videos` is handled only by the modular endpoint.

---

## Phase 4 – Testing and Verification

**Objective:** Prove that behavior is unchanged from the client and test perspective.

Steps:

1. Run focused tests:
   - `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py::TestProcessVideos`
   - `python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_add_media_endpoint.py::test_process_video_with_analysis_mocked`
   - Optionally: any additional E2E tests that touch `/process-videos`.
2. Compare key expectations:
   - Status codes (200/207/400/422) under the same scenarios.
   - `input_ref` values for:
     - URL inputs (`VALID_VIDEO_URL`).
     - Uploaded files (`SAMPLE_VIDEO_PATH.name`).
   - Error messages:
     - “No valid video sources supplied.”
     - Metadata extraction errors.
     - “Download failed for …” behavior for blocked/failed URLs.
   - `db_id` / `db_message` fields for process-only endpoints.
3. If any discrepancy appears:
   - Adjust the helper / endpoint to match the legacy behavior rather than changing tests (unless a test is clearly wrong and covered by PRD decisions).

Success criteria:

- All identified tests remain green.
- Manual inspection (or logging) confirms that response payloads match legacy behavior for representative scenarios (single URL, upload, mixed valid/invalid, no inputs).

---

## Future Optional Work (Post-Migration)

These are **not** required for the initial migration, but become easier once the endpoint is modularized:

- Consider introducing `run_batch_processor` from `pipeline.py` as a thin layer around the per-item video processing:
  - Define a per-item processor that turns `ProcessItem`s into result dicts.
  - Use `run_batch_processor` to handle counts and normalization, then merge with any video-specific fields.
- Factor out common patterns between video and audio processing (e.g., shared input mapping / error normalization), once both are modular and well-tested.

This migration should be treated as complete once:

- `media/process_videos.py` + a small core helper own the `/process-videos` logic.
- `_legacy_media.process_videos_endpoint` is a shim-only function.
- No external behavior changes are observable from API clients and tests.
