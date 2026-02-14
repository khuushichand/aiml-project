# M4.1 Execution Plan: Ingestion-First Onboarding Journey

Status: Complete  
Owner: WebUI + Product  
Date: February 13, 2026  
Roadmap Link: `Docs/Product/WebUI/WebUI_UX_Strategic_Roadmap_2026_02.md`

## 1) Objective

Ship the first production slice of the M4 journey with explicit guidance through:

1. Connect to server
2. Ingest first source
3. Verify in Media
4. Ask in Chat

## 2) Milestones

| Milestone | Window | Focus | Status | Exit Criteria |
|---|---|---|---|---|
| M4.1 | Feb 13-Feb 19, 2026 | Flow contract + guided onboarding CTAs | Complete | Success state includes actionable ingest->verify->chat controls with stable selectors |
| M4.2 | Feb 20-Feb 27, 2026 | Post-ingest recommendation logic | Complete | Recommendation state reacts to first completed ingest result (not static copy only) |
| M4.3 | Feb 27-Mar 6, 2026 | Hard-gate coverage + evidence | Complete | Desktop/mobile onboarding workflow gate passing with evidence and telemetry wiring |

## 3) Implemented in This Slice

- Updated onboarding success state in:
  - `apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
- Added explicit guided-flow messaging and ordered actions:
  - `Ingest first source`
  - `Verify in Media`
  - `Ask in Chat`
  - `Explore settings` (secondary)
- Added stable onboarding selectors for automation:
  - `onboarding-connect`
  - `onboarding-success-screen`
  - `onboarding-success-ingest`
  - `onboarding-success-media`
  - `onboarding-success-chat`
  - `onboarding-success-settings`
- Wired ingest CTA to `tldw:open-quick-ingest-intro` after onboarding completion.
- Added quick-ingest last-run summary contract in global store:
  - `apps/packages/ui/src/store/quick-ingest.tsx`
  - Tracks `status`, `successCount`, `failedCount`, and first successful source/media id.
- Wired Quick Ingest run outcomes into the store:
  - `apps/packages/ui/src/components/Common/QuickIngestModal.tsx`
- Bound onboarding recommendation cards to actual ingest outcomes:
  - `apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
  - Card state now shifts from `Start` -> `Completed` and emphasizes `Verify in Media` after successful ingest.
- Added onboarding conversion telemetry contract and instrumentation:
  - `apps/packages/ui/src/utils/onboarding-ingestion-telemetry.ts`
  - `apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
  - `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
  - Tracks onboarding-success reach, first-ingest success timing, and first-chat-after-ingest conversion.
- Extended onboarding workflow gate to dual viewport evidence capture:
  - `apps/tldw-frontend/e2e/workflows/onboarding-ingestion-first.spec.ts`
  - Captures desktop + mobile screenshots and JSON summaries under:
    - `Docs/Product/WebUI/evidence/m4_3_onboarding_<tag>/`
  - Evidence tag contract:
    - `TLDW_ONBOARDING_EVIDENCE_TAG` (falls back to runtime date stamp when omitted)
- Added CI-target script entrypoint for M5 UX gates:
  - `apps/tldw-frontend/package.json` -> `e2e:onboarding`
- Bootstrapped first M5 CI UX workflow job for onboarding:
  - `.github/workflows/frontend-ux-gates.yml` (`Onboarding E2E Gate`)

## 4) Validation Evidence

Command:

- `TLDW_WEB_AUTOSTART=false TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/workflows/onboarding-ingestion-first.spec.ts --reporter=line`
- `TLDW_WEB_AUTOSTART=true TLDW_WEB_CMD="NODE_PATH=/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/node_modules bun run dev -- -p 8080" TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bun run e2e:onboarding`
- `TLDW_WEB_AUTOSTART=true TLDW_WEB_CMD="NODE_PATH=/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/node_modules bun run dev -- -p 8080" TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line`
- `bunx vitest run apps/packages/ui/src/utils/__tests__/onboarding-ingestion-telemetry.test.ts apps/packages/ui/src/store/__tests__/quick-ingest.test.ts`

Outcome:

- `2 passed` (`Onboarding Ingestion-First Journey`, desktop + mobile)
- `7 passed` (`onboarding-ingestion-telemetry` + `quick-ingest` unit tests)
- `165 passed` (`all-pages` post-change smoke confirmation)

Test artifact:

- `apps/tldw-frontend/e2e/workflows/onboarding-ingestion-first.spec.ts`
- `Docs/Product/WebUI/evidence/m4_3_onboarding_<tag>/README.md`

## 5) M5 Handoff Follow-Up (Remaining)

1. Define weekly telemetry rollup review cadence for onboarding conversion metrics.
2. Fold onboarding gate and evidence-check contract into M5 release checklist.
3. Completed: onboarding evidence directory naming is parameterized via `TLDW_ONBOARDING_EVIDENCE_TAG` and consumed in CI artifact upload paths.
