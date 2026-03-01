# Issue #752 Image Prompt Refinement Implementation Plan

## Stage 1: Add Shared Prompt Refinement Utility
**Goal**: Introduce a deterministic helper for improving sparse image prompts without external model calls.
**Success Criteria**:
- New utility exposes mode normalization (`off|auto|basic`) and prompt refinement behavior.
- Refinement is deterministic and safe (whitespace normalization, optional quality suffix, no duplicate suffix).
**Tests**:
- Unit tests for mode normalization and refinement behavior.
**Status**: Complete

## Stage 2: Integrate Into Image Generation Entry Points
**Goal**: Apply refinement in both file-artifacts image generation and workflows `image_gen`.
**Success Criteria**:
- File Artifacts image requests honor `payload.prompt_refinement` (`true|false|auto/basic/off`).
- Workflows image_gen honors `config.prompt_refinement`.
- Opt-out keeps prompt unchanged.
**Tests**:
- Files image endpoint test verifies request prompt changes with opt-in and not with opt-out.
- Workflows image_gen tests verify refined vs unchanged prompt in test mode.
**Status**: Complete

## Stage 3: Verify + Document + Track Progress
**Goal**: Validate changes and record local closure evidence for #752.
**Success Criteria**:
- Targeted tests pass.
- Bandit passes on touched scope.
- Checklist entry for #752 updated with evidence.
**Tests**:
- `pytest` targeted suites for Image_Generation, Files image endpoint, Workflows image adapter tests.
- `bandit` on touched paths.
**Status**: Complete
