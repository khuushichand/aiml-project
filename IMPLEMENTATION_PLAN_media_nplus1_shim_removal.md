## Stage 1: Inventory and Scope Lock
**Goal**: Confirm remaining compatibility shims/adapters and impacted tests.
**Success Criteria**: Concrete file list for endpoint shims, module shims, and tests.
**Tests**: N/A (analysis stage)
**Status**: Complete

## Stage 2: Remove Endpoint Indirection Shims
**Goal**: Replace `compat_patchpoints` usage with direct media/service references while preserving behavior.
**Success Criteria**: No remaining imports/usages of `compat_patchpoints` in media endpoints.
**Tests**: Targeted process endpoint tests.
**Status**: In Progress

## Stage 3: Remove Adapter Markers and Compatibility Module
**Goal**: Delete compatibility module and remove adapter-only exports/markers from `media/__init__.py`.
**Success Criteria**: No `compat_patchpoints.py`, no `LEGACY_MEDIA_SHIM_MODE`, no `_legacy_media`, no `_process_uploaded_files` alias.
**Tests**: Shim/contract tests updated and passing.
**Status**: Not Started

## Stage 4: Verify Parity and Security Gates
**Goal**: Run focused pytest and Bandit on touched scope.
**Success Criteria**: Targeted tests green; no new high-severity Bandit findings in touched files.
**Tests**: Selected `pytest` files and `python -m bandit -r` on touched paths.
**Status**: Not Started
