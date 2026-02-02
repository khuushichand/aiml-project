## Stage 1: Scope & Design
**Goal**: Identify all workflow/watchlists endpoints that read filesystem paths and define a safe validation strategy.
**Success Criteria**: List of endpoints + intended validation rules captured here.
**Tests**: N/A (design-only).
**Status**: Complete

## Stage 2: Implement Path Guards
**Goal**: Enforce path containment for workflow artifact file access and watchlists log reads.
**Success Criteria**: Workflow artifact download/verify/manifest/bulk endpoints validate paths; watchlists log readers validate log_path under a safe base.
**Tests**: Existing tests continue to pass.
**Status**: Not Started

## Stage 3: Add Targeted Tests
**Goal**: Cover new workflow artifact path validation behavior.
**Success Criteria**: New test asserts out-of-scope artifact download is rejected.
**Tests**: `tests/Workflows/test_artifact_download_range.py` (new case).
**Status**: Not Started

## Stage 4: Review & Wrap
**Goal**: Sanity-check changes and summarize.
**Success Criteria**: Clear summary + next steps.
**Tests**: Optional (user-directed).
**Status**: Not Started
