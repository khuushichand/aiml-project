# Media Legacy Cleanup Plan

This document tracks the remaining legacy media helpers and the
planned deprecation/removal path now that the modular `/media`
endpoints and core ingestion helpers are canonical.

## Scope

File: `tldw_Server_API/app/api/v1/endpoints/_legacy_media.py`

Only helpers that are not used by modular endpoints, core ingestion
modules, or the test suite are listed here. Shims that forward into
modular/core code remain part of the supported surface for now.

## Candidates (Group 1 – legacy-only, unused in modular pipeline)

Status: **Completed** – helpers removed from `_legacy_media.py`
after auditing external usage and updating the changelog.

- `parse_advanced_query` (`_legacy_media.py:1480`)
  - Previous status: Not called by `search_media_items` or any other
    function.
  - Outcome: Removed from `_legacy_media.py` after confirming no
    external imports; future advanced-search work should live under
    the modular media listing/search helpers instead.

- Claims helpers (`_legacy_media.py:1667`–`1688`)
  - `_claims_extraction_enabled`
  - `_resolve_claims_parameters`
  - `_prepare_claims_chunks`
  - Notes:
    - Behavior is implemented and documented in
      `core/Ingestion_Media_Processing/claims_utils.py`.
    - No call sites in `_legacy_media` or modular endpoints.
  - Outcome: Removed from `_legacy_media.py` after one minor release,
    leaving `claims_utils` as the canonical implementation.

- `_single_pdf_worker` (`_legacy_media.py:4158`)
  - Notes:
    - Legacy async worker for PDF processing.
    - Modular `/process-pdfs` endpoint uses core ingestion helpers
      instead; no direct callers reference this worker.
  - Outcome: Removed after confirming no external imports; the
    `normalise_pdf_result` helper is retained for debugging/tests and
    is used by the modular PDF processing endpoint.

## Candidates (Group 2 – heavy implementations replaced by shims)

These implementations are not on any live code path; the exported
names are rebound to shim functions that delegate into core helpers.
The alias lines must be preserved until we are certain no external
code imports these names directly.

- `_process_batch_media` (formerly heavy implementation, `_legacy_media.py:1723`)
  - Live behavior: `core.Ingestion_Media_Processing.persistence.process_batch_media`.
  - Alias: `_process_batch_media = _process_batch_media_shim` at the
    bottom of `_legacy_media.py`.
  - Status:
    - Heavy legacy body has been retired; only the shim helper and alias
      remain so that any historical imports of `_process_batch_media`
      continue to resolve.

- `_add_media_impl` (formerly heavy legacy `/media/add` implementation, `_legacy_media.py:2124`)
  - Live behavior: `core.Ingestion_Media_Processing.persistence.add_media_orchestrate`
    via `add_media_persist` and `media/add.py`.
  - Alias: `_add_media_impl = _add_media_impl_shim` at the bottom of
    `_legacy_media.py`.
  - Status:
    - Heavy legacy body has been retired; only the shim helper and alias
      remain so that any historical imports of `_add_media_impl` continue
      to resolve.

## Safety Checks Before Removal

Before deleting any of the above:

1. Confirm no external imports:
   - Run a project-wide search for the fully-qualified names (e.g.,
     `tldw_Server_API.app.api.v1.endpoints._legacy_media._add_media_impl`).
2. Ensure CI covers:
   - `tldw_Server_API/tests/Media/`
   - `tldw_Server_API/tests/MediaIngestion_NEW/`
   - `tldw_Server_API/tests/Media_Ingestion_Modification/`
   - Under both default mode and `TLDW_DISABLE_LEGACY_MEDIA=1`.
3. Announce in changelog:
   - Note removal of legacy-only helpers and direct callers (if any)
     should migrate to `endpoints.media` and core helpers.

## Current Status

- Group 1 helpers (`parse_advanced_query`, claims wrappers, and
  `_single_pdf_worker`) have been removed from `_legacy_media.py`
  after auditing external usage and updating the changelog.
- Group 2 helpers (`_process_batch_media`, `_add_media_impl`) have been
  fully cleaned up:
  - Their heavy legacy implementations have been removed.
  - The exported names are bound only to shim functions
    (`_process_batch_media_shim`, `_add_media_impl_shim`) that delegate
    into core ingestion helpers in `Ingestion_Media_Processing.persistence`.
- `_legacy_media.py` now serves as:
  - A thin compatibility layer exposing historical endpoint definitions
    that forward into modular `endpoints.media.*` implementations.
  - A small collection of shared constants, enums, and Pydantic form
    models used by code outside `endpoints.media`.
  - A set of shims that keep legacy helper names importable while all
    real ingestion and persistence behavior lives under core helpers and
    the modular media package.
