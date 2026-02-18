## Stage 1: Reproduce Current Failures
**Goal**: Validate current failing assertions in speech and TTS playground E2E specs and confirm exact failure points.
**Success Criteria**: Targeted tests fail deterministically with actionable assertion messages.
**Tests**: `bunx playwright test tests/e2e/tts-playground.spec.ts tests/e2e/speech-playground.spec.ts -g "shows browser TTS segment controls|disables Play when ElevenLabs config is incomplete|supports transcript lock/unlock, copy toast, and download tooltip" --reporter=line`
**Status**: Complete

## Stage 2: Harden TTS Provider Selection Helpers
**Goal**: Make TTS provider selection robust against AntD rendering/state differences and preselected-provider state.
**Success Criteria**: `chooseTtsProvider` and dependent tests reliably detect/select Browser TTS and ElevenLabs.
**Tests**: Targeted TTS tests above.
**Status**: Complete

## Stage 3: Stabilize Speech Playground Action Locators
**Goal**: Update speech lock/unlock test selectors for copy/download actions to match current UI structure.
**Success Criteria**: Speech lock/unlock test passes without flaky locator failures.
**Tests**: Targeted speech test above.
**Status**: Complete

## Stage 4: Verify and Finalize
**Goal**: Re-run targeted suites and confirm pass/fail outcomes with clear residual risks.
**Success Criteria**: Targeted tests pass locally, or remaining failures are isolated and documented with exact blocker.
**Tests**: Same targeted command plus file-level reruns.
**Status**: Complete
