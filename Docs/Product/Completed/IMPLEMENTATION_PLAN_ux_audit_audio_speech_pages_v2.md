# Implementation Plan: UX Audit v2 Audio and Speech Pages

## Scope

Pages: TTS, STT, Speech  
Issue IDs: `TTS-1`, `TTS-2`, `STT-1`, `STT-2`, `SPEECH-1`

## Issue Grouping Coverage

- `TTS-1`: Raw template variables rendered (`{{model}}`, `{{task}}`, `{{format}}`, `{{count}}`)
- `TTS-2`: Voice/provider selectors stuck in skeleton loading state
- `STT-1`: Same template leak class as TTS
- `STT-2`: Output skeleton bars never resolve
- `SPEECH-1`: `/speech` and `/stt` content duplication

## Stage 1: Template Binding and Fallback Defaults
**Goal**: Eliminate raw placeholder rendering on audio surfaces.
**Success Criteria**:
- TTS/STT template placeholders always resolve to real values or safe defaults.
- Missing backend metadata produces user-friendly fallback copy.
- Placeholder syntax is blocked from direct user rendering.
**Tests**:
- Unit tests for formatter/default value helpers.
- Component snapshot tests for loaded vs missing metadata states.
**Status**: Complete

## Stage 2: Loading Lifecycle and Retry UX
**Goal**: Replace indefinite skeletons with deterministic load/error flows.
**Success Criteria**:
- Voice/provider and output loaders use timeout threshold with explicit error state.
- Error state includes actionable retry and setup guidance.
- Silent API failures are surfaced in non-technical user language.
**Tests**:
- Integration tests with mocked delayed/failed API responses.
- E2E test validating timeout-to-retry transition.
**Status**: Complete

## Stage 3: Route Purpose Differentiation
**Goal**: Ensure `/speech` and `/stt` are clearly distinct or intentionally unified.
**Success Criteria**:
- Route definitions and navigation labels match actual page behavior.
- If unified, one route redirects with clear rationale and docs update.
- If separate, each page has distinct purpose, heading, and controls.
**Tests**:
- Route contract tests for `/speech`, `/stt`, and `/tts`.
- Navigation and breadcrumb assertions for route identity.
**Status**: Complete

## Stage 4: Regression Coverage and Performance Budget
**Goal**: Prevent recurrence of audio UX regressions.
**Success Criteria**:
- Audio route smoke tests run in CI with console error threshold.
- Loading states complete within expected budget under mocked latency.
- Documentation updated for audio page state model.
**Tests**:
- Playwright smoke suite for core audio interactions.
- Console warning/error budget assertions for audio routes.
**Status**: Complete

## Progress Notes (2026-02-16)
- Stage 3 implemented:
  - `/tts` now renders `TtsPlaygroundPage`.
  - `/stt` now renders `SttPlaygroundPage`.
  - `/speech` remains the unified `SpeechPlaygroundPage`.
  - Added route identity tests in `apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx`.
- Stage 2 completed:
  - Added explicit 10s timeout to ElevenLabs metadata requests (`getVoices`, `getModels`) in `apps/packages/ui/src/services/elevenlabs.ts`.
  - Updated `useTtsProviderData` to surface `elevenLabsError` and `refetchElevenLabs` for retry UX.
  - Added alert + retry handling to both:
    - `apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx`
    - `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`
  - Added hook tests in `apps/packages/ui/src/hooks/__tests__/useTtsProviderData.test.tsx`.
  - Added extension Playwright timeout-to-retry coverage:
    - `apps/extension/tests/e2e/tts-playground.spec.ts`
    - `apps/extension/tests/e2e/speech-playground.spec.ts`
  - Hardened browser-voice loading to fail soft (`[]`) instead of blocking settings load:
    - `apps/packages/ui/src/services/tts.ts`
- Validation run:
  - `bunx vitest run src/routes/__tests__/option-audio-route-identity.test.tsx src/hooks/__tests__/useTtsProviderData.test.tsx src/utils/__tests__/template-guards.test.ts`
  - Result: 3 test files passed, 8 tests passed.
  - `cd apps/extension && bunx playwright test tests/e2e/tts-playground.spec.ts tests/e2e/speech-playground.spec.ts --grep "timeout hint and recovers on retry" --workers=1`
  - Result: `2 passed`.

## Progress Notes (2026-02-17)
- Stage 1 fallback hardening completed for remaining audio interpolation edge:
  - Wrapped TTS browser-segment progress copy with template guard fallback:
    - `apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx`
  - Outcome: unresolved interpolation tokens are blocked even when translation payloads fail to resolve.
- Stage 4 regression gate implementation completed:
  - Added dedicated Stage 7 audio smoke suite:
    - `apps/tldw-frontend/e2e/smoke/stage7-audio-regression.spec.ts`
  - Coverage includes:
    - route identity + runtime budget checks for `/tts`, `/stt`, `/speech`, and `/audio` alias behavior.
    - unresolved-template guardrails (`{{...}}`) on audio surfaces.
    - timeout-to-retry recovery on ElevenLabs metadata for `/tts` and `/speech`.
    - timeout-to-retry recovery on STT model loading for `/stt`.
  - Added script for local/CI execution:
    - `apps/tldw-frontend/package.json`
    - `e2e:smoke:audio`
  - Wired CI UX gate to run Stage 7 audio suite:
    - `.github/workflows/frontend-ux-gates.yml`
    - new step: `Run Stage 7 audio regression gate`
  - Updated frontend gate docs with Stage 7 expectations:
    - `apps/tldw-frontend/README.md`
- Validation runs:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage7-audio-regression.spec.ts --reporter=line`
  - Result: `4 passed` (`12.0s`)
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage5-release-gate.spec.ts --reporter=line`
  - Result: `12 passed` (`22.6s`)
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `6 passed` (`12.4s`)
