## Stage 1: Reproduce and Pinpoint UX Breaks
**Goal**: Confirm why Knowledge QA flows show blank/blocked states in extension options.
**Success Criteria**: Identified concrete root causes with code-level targets.
**Tests**: Run targeted extension E2E tests for Knowledge QA/landing flow.
**Status**: Complete

## Stage 2: Patch Navigation and Translation Reliability
**Goal**: Ensure "Do Research" routes to the Knowledge QA workspace and settings labels render translated text.
**Success Criteria**: Research CTA opens Knowledge QA route; settings nav labels no longer display raw i18n keys.
**Tests**: Run focused E2E/spec checks for landing flow and settings rendering.
**Status**: Complete

## Stage 3: Preserve RAG Option Coverage and Validate Constraints
**Goal**: Keep complete RAG option availability while respecting backend schema limits and UI defaults.
**Success Criteria**: UI option set remains in parity with backend schema; problematic ranges/defaults corrected.
**Tests**: Existing Knowledge QA UX/spec runs and local key-parity check script.
**Status**: Complete

## Stage 4: End-to-End Validation (Live + Local)
**Goal**: Verify behavior in mocked and live-server paths.
**Success Criteria**: Live and local Knowledge QA entry flows are deterministic; failures have clear diagnostics.
**Tests**: Playwright `knowledge-rag-ux.spec.ts` and `live-ux-review.spec.ts` targeted cases.
**Status**: Complete
