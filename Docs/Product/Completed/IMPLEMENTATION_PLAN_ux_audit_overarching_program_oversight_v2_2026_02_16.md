# Implementation Plan: UX Audit v2 Overarching Program Oversight (2026-02-16)

## Scope

Provide one control plan to oversee implementation sequencing, quality gates, and release readiness for UX Audit v2 remediation plans.

In-scope plan sequence:
1. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_cross_cutting_stage1_route_matrix_baseline_v2.md`
2. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_settings_pages_v2.md`
3. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_admin_pages_v2.md`
4. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_chat_pages_v2.md`
5. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_audio_speech_pages_v2.md`
6. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_workspace_playground_pages_v2.md`
7. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_media_knowledge_pages_v2.md`
8. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_core_pages_v2.md`
9. `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/IMPLEMENTATION_PLAN_ux_audit_interaction_tests_v2.md`

Already complete and tracked as closed dependencies:
- `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_ux_audit_cross_cutting_themes_v2.md`
- `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_circuit_breaker_distributed_semantics_admin_endpoint_2026_02_16.md`

## Oversight Model

- Program-level control: one active wave at a time, no parallel wave starts without gate sign-off.
- Entry gate for each plan: predecessor plan reaches all Stage success criteria and test evidence is attached.
- Exit gate for each plan: route and interaction evidence captured, plan status updated, and risks handed off.
- Reporting cadence: daily short status (progress, blockers, next gate), end-of-wave checkpoint with artifacts.

## Stage 1: Program Setup and Gate Definition
**Goal**: Establish non-ambiguous governance, artifacts, and acceptance thresholds before implementation sequencing continues.
**Success Criteria**:
- Ordered sequence is frozen and published in this plan.
- Each in-scope plan has a designated owner and reviewer.
- Shared pass/fail thresholds are declared:
  - zero error overlays,
  - zero unresolved template variables on audited surfaces,
  - no wrong-content routes,
  - no indefinite skeleton loaders on key surfaces.
- Artifact locations are standardized under `Docs/Plans/artifacts/`.
**Tests**:
- Verify all in-scope plans exist and show current statuses.
- Reconfirm cross-cutting baseline metrics file is available and current.
**Status**: Complete
**Progress Notes (2026-02-16)**:
- Stage 1 kickoff rerun executed with new reproducible smoke spec:
  - `apps/tldw-frontend/e2e/smoke/stage1-route-matrix-capture.spec.ts`
- New artifact captured:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-16_kickoff.json`
- Initial kickoff checks met:
  - zero runtime overlays,
  - zero uncaught `chrome` runtime errors,
  - zero unresolved template leak surfaces in the captured route set.

## Stage 2: Wave A - Navigation and Route Integrity
**Goal**: Complete route and IA correctness work before page-level UX refinements.
**Plans in wave**:
1. `IMPLEMENTATION_PLAN_ux_audit_settings_pages_v2.md`
2. `IMPLEMENTATION_PLAN_ux_audit_admin_pages_v2.md`
3. Cross-cutting checkpoint rerun using `IMPLEMENTATION_PLAN_ux_audit_cross_cutting_stage1_route_matrix_baseline_v2.md`
**Success Criteria**:
- Settings and admin dead links/misroutes are eliminated or replaced with explicit placeholders.
- Wrong-content route count is zero for Section 2 items from the audit report.
- Route contract tests and sidebar navigation tests pass for settings and admin surfaces.
**Tests**:
- Route contract and navigation tests defined in settings/admin plans.
- Full audited route smoke rerun and artifact capture.
**Status**: Complete
**Progress Notes (2026-02-16)**:
- Plan 2 (`IMPLEMENTATION_PLAN_ux_audit_settings_pages_v2.md`) kickoff validation rerun completed.
- Route-repair checks reconfirmed `200` responses for:
  - `/settings/ui`
  - `/settings/image-gen`
  - `/settings/image-generation`
  - `/settings/guardian`
  - `/settings`
- Settings-focused test reruns completed:
  - Vitest: settings nav filter/focus/guardian suites + guardian settings integration (`23 passed`).
  - Playwright: `e2e/workflows/settings.spec.ts --grep "Settings Navigation"` (`8 passed`).
- Settings E2E harness updated to current UI markers in:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/utils/page-objects/SettingsPage.ts`
- Plan 3 (`IMPLEMENTATION_PLAN_ux_audit_admin_pages_v2.md`) kickoff validation rerun completed.
- Admin-focused validations completed:
  - Playwright: `e2e/smoke/route-contract-stage2.spec.ts` (`1 passed`)
  - Playwright: `e2e/smoke/all-pages.spec.ts --grep "/admin"` (`9 passed`)
  - Vitest: admin error utils + server/llama/mlx suites (`10 passed`)
- Wave A implementation artifacts now include:
  - shared admin error sanitization/guard mapping,
  - server budget human-readable formatting,
  - MLX inactive concurrency clarity updates.
**Progress Notes (2026-02-17)**:
- Wave A closeout reruns completed:
  - Playwright route-contract: `apps/tldw-frontend/e2e/smoke/route-contract-stage2.spec.ts` with `TLDW_STAGE2_OUTPUT_DATE=2026-02-17` + `TLDW_STAGE2_OUTPUT_SUFFIX=waveA_closeout` (`1 passed`)
  - Artifact: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage2_route_contract_check_2026-02-17_waveA_closeout.json`
  - Playwright route-matrix capture: `apps/tldw-frontend/e2e/smoke/stage1-route-matrix-capture.spec.ts` with `TLDW_STAGE1_OUTPUT_DATE=2026-02-17` + `TLDW_STAGE1_OUTPUT_SUFFIX=waveA_closeout` (`1 passed`)
  - Artifact: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_waveA_closeout.json`
  - Playwright admin sweep: `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts --grep "/admin" --workers=1` (`9 passed`)
  - Artifact: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/admin_route_smoke_check_2026-02-17_waveA_closeout.json`
  - Playwright admin sweep after smoke-harness transient-runtime retry hardening: `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts --grep "/admin" --reporter=line` (`9 passed`)
- Stage 1 smoke summary snapshot:
  - `86` routes scanned, `0` runtime overlays, `0` template-leak routes.
  - single `404` route remains expected from manifest sentinel `/nonexistent-page-404-test`.
- Admin targeted regression rerun completed:
  - `apps/packages/ui/src/components/Option/Admin/__tests__/admin-error-utils.test.ts`
  - `apps/packages/ui/src/components/Option/Admin/__tests__/StatusBanner.test.tsx`
  - `apps/packages/ui/src/components/Option/Admin/__tests__/ServerAdminPage.media-budget.test.tsx`
  - `apps/packages/ui/src/components/Option/Admin/__tests__/LlamacppAdminPage.test.tsx`
  - `apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx`
  - Result: `14 passed`.
- Wave A exit gate closed; settings/admin plans are status-synced and artifact-linked.

## Stage 3: Wave B - High-Impact Interaction Reliability
**Goal**: Remove high-visibility user-facing defects on chat, audio, and workspace/playground surfaces.
**Plans in wave**:
1. `IMPLEMENTATION_PLAN_ux_audit_chat_pages_v2.md`
2. `IMPLEMENTATION_PLAN_ux_audit_audio_speech_pages_v2.md`
3. `IMPLEMENTATION_PLAN_ux_audit_workspace_playground_pages_v2.md`
**Success Criteria**:
- Template leaks are eliminated on chat, audio, and documentation/workspace surfaces.
- Indefinite loader states are replaced with timeout plus retry/error UX.
- Mobile interaction and touch-target criteria pass on prioritized flows.
- Console runtime errors trend down and remain within agreed warning budget.
**Tests**:
- Plan-defined component/integration tests for template fallback and loading transitions.
- Mobile Playwright flows for critical actions.
- Console-budget assertions for affected routes.
**Status**: Complete
**Progress Notes (2026-02-16)**:
- Plan 4 (`IMPLEMENTATION_PLAN_ux_audit_chat_pages_v2.md`) implementation started.
- Chat reliability/clarity updates in progress:
  - disconnected chat banner deduplication,
  - agent workspace prerequisite empty-state guidance,
  - persona memory labeling (`k=n` -> `Memory results: n`),
  - chat send-touch target hardening to minimum `44px`,
  - `/chat/settings` section wayfinding and save-scope label clarity.
- Plan 4 targeted unit rerun completed:
  - `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx` (`6 passed`).
**Progress Notes (2026-02-17)**:
- Plan 4 (`IMPLEMENTATION_PLAN_ux_audit_chat_pages_v2.md`) Stage 2/4 follow-up started.
- Compact chat-composer toolbar hardening completed for mobile-sized layouts:
  - compact icon controls now enforce `44x44` touch-target minimums,
  - compact icon controls now render visible short labels (`Image`, `Voice`, `Config`, `Dictate`, `Stop`) to reduce icon-only ambiguity.
  - file updated:
    - `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- Added compact-toolbar regression contract test:
  - `apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts`
- Validation rerun:
  - `cd apps/packages/ui && bunx vitest run src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts src/routes/__tests__/sidepanel-persona.test.tsx`
  - Result: `8 passed`.
- Focused Playwright chat smoke validation:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Chat (/chat)" --workers=1 --reporter=line`
  - Result: `2 passed`.
- Plan 4 Stage 2 + Stage 4 closeout completed:
  - `/chat` active composer path (`apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`) now enforces mobile `44px` touch targets for:
    - `Attach image`,
    - `More attachments`,
    - `Send message`,
    - `Open send options`.
  - Added Stage 6 interaction regression coverage:
    - `apps/tldw-frontend/e2e/smoke/stage6-interaction-stage2.spec.ts` now includes mobile chat control parity + touch-target assertions.
  - Added persona responsive parity guardrail:
    - `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx` validates session/memory controls at `390px` and `1280px`.
- Plan 4 closure validation reruns:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx src/components/Option/Playground/__tests__/TokenProgressBar.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts`
  - Result: `4 passed` test files, `16 passed` tests.
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `4 passed`.
- Plan 5 (`IMPLEMENTATION_PLAN_ux_audit_audio_speech_pages_v2.md`) implementation started.
- Audio/speech route identity fixes completed:
  - `/tts` now renders dedicated `TtsPlaygroundPage`.
  - `/stt` now renders dedicated `SttPlaygroundPage`.
  - `/speech` remains unified on `SpeechPlaygroundPage`.
- Audio loading lifecycle hardening added for ElevenLabs metadata:
  - explicit 10s request timeout in `apps/packages/ui/src/services/elevenlabs.ts`,
  - surfaced error + retry states in `apps/packages/ui/src/hooks/useTtsProviderData.ts`,
  - retry/error alerts wired in TTS and Speech playground pages.
- Plan 5 targeted test rerun completed:
  - `apps/packages/ui/src/routes/__tests__/option-audio-route-identity.test.tsx`
  - `apps/packages/ui/src/hooks/__tests__/useTtsProviderData.test.tsx`
  - `apps/packages/ui/src/utils/__tests__/template-guards.test.ts`
  - Result: `8 passed`.
- Plan 5 timeout-retry E2E validation completed:
  - `apps/extension/tests/e2e/tts-playground.spec.ts`
  - `apps/extension/tests/e2e/speech-playground.spec.ts`
  - Command: `cd apps/extension && bunx playwright test tests/e2e/tts-playground.spec.ts tests/e2e/speech-playground.spec.ts --grep "timeout hint and recovers on retry" --workers=1`
  - Result: `2 passed`.
- Audio fallback hardening added to avoid blocking settings load when browser voice APIs are unavailable:
  - `apps/packages/ui/src/services/tts.ts`
- Plan 5 Stage 1 + Stage 4 closeout completed:
  - Template fallback hardening added for TTS browser progress interpolation:
    - `apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx`
  - Added Stage 7 audio regression gate:
    - `apps/tldw-frontend/e2e/smoke/stage7-audio-regression.spec.ts`
    - coverage: audio route identity/runtime budget, unresolved-template guardrails, and timeout-to-retry recovery for `/tts`, `/speech`, and `/stt`.
  - CI wiring:
    - `apps/tldw-frontend/package.json` (`e2e:smoke:audio`)
    - `.github/workflows/frontend-ux-gates.yml` (`Run Stage 7 audio regression gate`)
    - `apps/tldw-frontend/README.md` (UX gate docs updated for Stage 7).
- Plan 5 validation reruns after Stage 7:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage7-audio-regression.spec.ts --reporter=line` -> `4 passed` (`12.0s`)
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage5-release-gate.spec.ts --reporter=line` -> `12 passed` (`22.6s`)
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line` -> `6 passed` (`12.4s`)
- Plan 5 status synced to complete in `IMPLEMENTATION_PLAN_ux_audit_audio_speech_pages_v2.md`.
- Plan 6 (`IMPLEMENTATION_PLAN_ux_audit_workspace_playground_pages_v2.md`) implementation started.
- Workspace mobile wording remediation completed for `WP-2`:
  - replaced "left pane" copy with adaptive "Sources tab" (mobile) / "Sources pane" (desktop) guidance in workspace chat and studio hints.
  - files updated:
    - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
    - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
    - `apps/packages/ui/src/components/Option/WorkspacePlayground/source-location-copy.ts`
- Plan 6 targeted unit validation completed:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `2 passed` test files, `6 passed` tests.
- Plan 6 template-hardening regression coverage added for documentation placeholders (`DOC-1`, `DOC-2`):
  - `apps/packages/ui/src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx`
- Plan 6 workflow editor mobile-layout remediation completed for `WE-2`:
  - replaced always-on sidebar behavior with responsive drawer panels on non-desktop viewports to prevent node-library overlap with canvas.
  - files updated:
    - `apps/packages/ui/src/components/WorkflowEditor/WorkflowEditor.tsx`
    - `apps/packages/ui/src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx`
- Plan 6 workflow editor accessibility hardening completed for `WE-4`:
  - validation icon control now exposes issue-count context in `aria-label` for screen readers.
  - files updated:
    - `apps/packages/ui/src/components/WorkflowEditor/WorkflowEditor.tsx`
    - `apps/packages/ui/src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx`
- Plan 6 data-tables touch-target remediation completed for `DT-2`:
  - row-level icon actions (`View`, `Export`, `Delete`) now retain explicit labels and mobile-safe `44x44` target sizing.
  - files updated:
    - `apps/packages/ui/src/components/Option/DataTables/DataTablesList.tsx`
    - `apps/packages/ui/src/components/Option/DataTables/ExportMenu.tsx`
  - test coverage:
    - `apps/packages/ui/src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx`
    - `apps/packages/ui/src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx`
- Plan 6 workflow-editor label consistency remediation completed for `WE-3`:
  - fallback step labels now preserve acronym casing for LLM-derived step names, eliminating `Llm`/`LLM` mismatch in the node library.
  - files updated:
    - `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
    - `apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Plan 6 stage-1 kanban content remediation completed for `KANBAN-1`:
  - empty-state guidance now distinguishes between true first-use (`No boards yet`) and existing-board selection (`Select an existing board`), removing contradictory copy.
  - files updated:
    - `apps/packages/ui/src/components/Option/KanbanPlayground/index.tsx`
    - `apps/packages/ui/src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx`
- Plan 6 stage-1 quiz tab-intent remediation completed for `QUIZ-1`:
  - `Take Quiz` empty-state messaging now explicitly indicates no quizzes are available to take, reducing mismatch between tab intent and copy.
  - files updated:
    - `apps/packages/ui/src/components/Quiz/tabs/TakeQuizTab.tsx`
    - `apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx`
- Plan 6 stage-1 watchlists empty-state remediation completed for `WATCH-1`:
  - first-use sources experience now uses a unified empty state (instead of dual barren empties), and table empty copy adapts for filtered results.
  - files updated:
    - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/empty-state.ts`
    - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts`
- Plan 6 stage-1 documentation functional-fallback remediation completed for `DOC-3`:
  - when runtime document discovery is unavailable, both documentation sources now expose inline fallback docs so tabs remain functional.
  - files updated:
    - `apps/packages/ui/src/components/Option/Documentation/DocumentationPage.tsx`
    - `apps/packages/ui/src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx`
- Plan 6 stage-2 chunking mobile-workflow remediation completed for `CHUNK-2`:
  - non-desktop single-mode layout now places settings ahead of output to keep chunking controls reachable without scrolling past results.
  - files updated:
    - `apps/packages/ui/src/components/Option/ChunkingPlayground/index.tsx`
    - `apps/packages/ui/src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx`
- Plan 6 stage-3 document-workspace icon-label remediation completed for `DW-1`:
  - document workspace sidebars now use icon+text tab labels with tooltip and aria-label semantics to remove ambiguous icon-only controls.
  - files updated:
    - `apps/packages/ui/src/components/DocumentWorkspace/DocumentWorkspacePage.tsx`
    - `apps/packages/ui/src/components/DocumentWorkspace/TabIconLabel.tsx`
    - `apps/packages/ui/src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx`
- Plan 6 stage-1 flashcards content-integrity remediation completed for `FLASH-1`:
  - review card selection now prefers non-instructional cards to avoid tutorial residue appearing as the first study card.
  - files updated:
    - `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
    - `apps/packages/ui/src/components/Flashcards/utils/review-card-hygiene.ts`
    - `apps/packages/ui/src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts`
- Plan 6 stage-2 flashcards mobile CTA remediation completed for `FLASH-2`:
  - review tab now includes a persistent, above-fold `Create a new card` action to keep card creation discoverable on mobile.
  - files updated:
    - `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
    - `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`
- Plan 6 stage-4 workflow visual-semantics remediation completed for `WE-1`:
  - workflow category styling now aligns to blue/indigo semantics across palette rows, node cards, and minimap coloring, removing prior purple/orange inconsistency.
  - files updated:
    - `apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
    - `apps/packages/ui/src/components/WorkflowEditor/NodePalette.tsx`
    - `apps/packages/ui/src/components/WorkflowEditor/WorkflowCanvas.tsx`
    - `apps/packages/ui/src/components/WorkflowEditor/nodes/WorkflowNode.tsx`
    - `apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Plan 6 stage-4 moderation guidance/disclosure coverage added for `MOD-1` and `MOD-2`:
  - component tests now verify onboarding banner dismissal persistence and advanced-mode progressive disclosure.
  - files updated:
    - `apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx`
- Plan 6 targeted rerun updated:
  - `cd apps/packages/ui && bunx vitest run src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `5 passed` test files, `14 passed` tests.
- Plan 6 expanded rerun after `DT-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `7 passed` test files, `16 passed` tests.
- Plan 6 workflow-editor rerun after `WE-3`:
  - `cd apps/packages/ui && bunx vitest run src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx`
  - Result: `3 passed` test files, `21 passed` tests.
- Plan 6 expanded rerun after `KANBAN-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `8 passed` test files, `27 passed` tests.
- Plan 6 expanded rerun after `QUIZ-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `9 passed` test files, `28 passed` tests.
- Plan 6 expanded rerun after `WATCH-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `10 passed` test files, `31 passed` tests.
- Plan 6 expanded rerun after `DOC-3`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `10 passed` test files, `31 passed` tests.
- Plan 6 expanded rerun after `CHUNK-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `11 passed` test files, `33 passed` tests.
- Plan 6 expanded rerun after `DW-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `12 passed` test files, `34 passed` tests.
- Plan 6 expanded rerun after `FLASH-1` + `FLASH-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `14 passed` test files, `39 passed` tests.
- Plan 6 expanded rerun after `WE-1` + `MOD-1` + `MOD-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `16 passed` test files, `46 passed` tests.
- Plan 6 Stage 5 positive-pattern guardrails completed (`DT-1`, `EVAL-1`, `CHUNK-1`, `WP-1`):
  - added chunking golden-path regression coverage for multi-input + mode navigation:
    - `apps/packages/ui/src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx`
  - added workspace desktop 3-pane structural regression coverage:
    - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx`
  - retained and revalidated data-tables/evaluations positive-pattern guardrails:
    - `apps/packages/ui/src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx`
    - `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx`
- Plan 6 Stage 5 validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx`
  - Result: `5 passed` test files, `8 passed` tests.
- Plan 6 expanded wave-B rerun after Stage 5 closeout:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts`
  - Result: `20 passed` test files, `52 passed` tests.

## Stage 4: Wave C - Domain Stabilization and Core Polish
**Goal**: Stabilize media/knowledge workflows and complete core onboarding/accessibility refinements.
**Plans in wave**:
1. `IMPLEMENTATION_PLAN_ux_audit_media_knowledge_pages_v2.md`
2. `IMPLEMENTATION_PLAN_ux_audit_core_pages_v2.md`
**Success Criteria**:
- Media/knowledge surfaces avoid raw backend errors and provide actionable retry states.
- Knowledge strong patterns are preserved with regression coverage.
- Core route identity is distinct (`/`, `/setup`, `/onboarding-test`) and mobile/a11y issues are resolved.
**Tests**:
- Plan-defined integration and responsive tests for media/knowledge/core.
- Snapshot or golden tests for preserved high-quality components.
**Status**: Complete
**Progress Notes (2026-02-17)**:
- Plan 7 (`IMPLEMENTATION_PLAN_ux_audit_media_knowledge_pages_v2.md`) Stage 1 completed.
- Media route reliability hardening (`MEDIA-1`):
  - added route boundaries for:
    - `apps/packages/ui/src/routes/option-media-multi.tsx`
    - `apps/packages/ui/src/routes/option-media-trash.tsx`
  - added route guard coverage:
    - `apps/packages/ui/src/routes/__tests__/option-media-route-guards.test.tsx`
- Chatbooks/characters error-state hardening (`CHAT-B1`, `CHAR-1`):
  - shared sanitized server error utility added:
    - `apps/packages/ui/src/utils/server-error-message.ts`
    - `apps/packages/ui/src/utils/__tests__/server-error-message.test.ts`
  - chatbooks content picker now includes sanitized section errors + `Retry` action:
    - `apps/packages/ui/src/components/Option/Chatbooks/ChatbooksPlaygroundPage.tsx`
    - `apps/packages/ui/src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx`
  - characters load-error copy now uses sanitized message formatting:
    - `apps/packages/ui/src/components/Option/Characters/Manager.tsx`
- Plan 7 Stage 1 validation run:
  - `cd apps/packages/ui && bunx vitest run src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `3 passed` test files, `6 passed` tests.
- Plan 7 Stage 2 (`KNOW-2`) mobile layout remediation completed:
  - Knowledge QA history now uses mobile overlay/drawer behavior with a floating open trigger, preserving main query area width.
  - files updated:
    - `apps/packages/ui/src/components/Option/KnowledgeQA/HistorySidebar.tsx`
    - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
- Plan 7 Stage 2 validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `4 passed` test files, `9 passed` tests.
- Wave-C expanded rerun (including Plan 7 deltas):
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
  - Result: `24 passed` test files, `61 passed` tests.
- Plan 7 Stage 3 (`CHAT-B1`, `CHAR-1`) UX recovery completed:
  - Chatbooks per-section load errors now provide sanitized message + retry + log-hint with correlation ID when available.
  - Characters load-error surface now includes log-hint guidance with correlation ID support.
  - utility/test updates:
    - `apps/packages/ui/src/utils/server-error-message.ts`
    - `apps/packages/ui/src/utils/__tests__/server-error-message.test.ts`
- Plan 7 Stage 3 validation run:
  - `cd apps/packages/ui && bunx vitest run src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `4 passed` test files, `12 passed` tests.
- Wave-C expanded rerun after Stage 3:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
  - Result: `24 passed` test files, `64 passed` tests.
- Plan 7 Stage 4 (`KNOW-1`) strong-pattern guardrails completed:
  - golden layout guardrails for Knowledge QA hero/search-first and results view transitions:
    - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
  - interaction guardrails for history recall + citation jump:
    - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
    - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
- Plan 7 Stage 4 validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `6 passed` test files, `18 passed` tests.
- Wave-C expanded rerun after Plan 7 completion:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
  - Result: `26 passed` test files, `70 passed` tests.
- Plan 8 (`IMPLEMENTATION_PLAN_ux_audit_core_pages_v2.md`) Stage 4 started (`CORE-7` route identity):
  - Added dedicated onboarding-test route components and unique route-intent copy for `/`, `/setup`, and `/onboarding-test`.
  - updated files:
    - `apps/packages/ui/src/routes/option-index.tsx`
    - `apps/packages/ui/src/routes/option-setup.tsx`
    - `apps/packages/ui/src/routes/option-onboarding-test.tsx`
    - `apps/packages/ui/src/routes/route-registry.tsx`
    - `apps/tldw-frontend/extension/routes/option-onboarding-test.tsx`
    - `apps/tldw-frontend/extension/routes/route-registry.tsx`
    - `apps/tldw-frontend/pages/onboarding-test.tsx`
  - added route identity regression test:
    - `apps/packages/ui/src/routes/__tests__/core-route-identity.test.tsx`
- Plan 8 targeted validation run:
  - `cd apps/packages/ui && bunx vitest run src/routes/__tests__/core-route-identity.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `2 passed` test files, `3 passed` tests.
- Plan 8 Stage 2 + Stage 3 completion (`CORE-1` through `CORE-6`):
  - Core route shells now support and apply `hideSidebar` on first-run onboarding routes, eliminating mobile left-rail width loss and overlap risk.
  - Onboarding demo hero now stacks cleanly on mobile and skip-link affordance/contrast has been hardened.
  - Status badge unknown-state wording moved from ambiguous “waiting” to explicit “not checked yet” copy.
  - validation and mapping files updated:
    - `apps/packages/ui/src/components/Layouts/Layout.tsx`
    - `apps/packages/ui/src/routes/option-index.tsx`
    - `apps/packages/ui/src/routes/option-setup.tsx`
    - `apps/packages/ui/src/routes/option-onboarding-test.tsx`
    - `apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
    - `apps/packages/ui/src/components/Option/Onboarding/OnboardingWizard.tsx`
    - `apps/packages/ui/src/components/Option/Settings/tldw.tsx`
    - `apps/packages/ui/src/components/Option/Settings/tldw-connection-status.ts`
    - `apps/packages/ui/src/components/Option/Settings/__tests__/tldw-connection-status.test.ts`
    - `apps/packages/ui/src/assets/locale/en/settings.json`
    - `apps/packages/ui/src/public/_locales/en/settings.json`
- Plan 8 validation runs after Stage 2/3 closeout:
  - `cd apps/packages/ui && bunx vitest run src/routes/__tests__/core-route-identity.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/Settings/__tests__/tldw-connection-status.test.ts`
  - Result: `3 passed` test files, `5 passed` tests.
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Settings/__tests__/ChatSettings.test.tsx src/components/Option/Settings/__tests__/GuardianSettings.test.tsx src/components/Option/Settings/__tests__/rag.test.tsx src/components/Option/Settings/__tests__/tldw-connection-status.test.ts`
  - Result: `4 passed` test files, `17 passed` tests.
- Plan 8 closeout status synced to complete in its plan document.
- Wave-C expanded rerun after Plan 8 Stage 4 start:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx src/routes/__tests__/core-route-identity.test.tsx`
  - Result: `27 passed` test files, `71 passed` tests.

## Stage 5: Interaction Gate and Release Readiness
**Goal**: Convert all validated behaviors into durable release gates and close the program.
**Plans in wave**:
1. `IMPLEMENTATION_PLAN_ux_audit_interaction_tests_v2.md`
2. Final cross-cutting rerun against the route matrix baseline plan
**Success Criteria**:
- Interaction positives and prior defects are encoded as stable CI tests.
- Release gate includes route smoke plus interaction suite for web UI changes.
- All in-scope plan files are updated to complete status with linked artifacts.
- Final summary reports before/after metrics for severity 4 and severity 3 issues.
**Tests**:
- Interaction E2E suite in CI with route/action-level diagnostics.
- Full smoke plus release-gate suite pass with no critical regressions.
**Status**: Complete
**Progress Notes (2026-02-17)**:
- Plan 9 (`IMPLEMENTATION_PLAN_ux_audit_interaction_tests_v2.md`) Stage 1 completed (`INT-1`, `INT-5`):
  - Added explicit theme toggle control in shared shell header for home discoverability.
  - Added interaction smoke coverage for `/chat` unresolved-template detection and `/` theme toggle behavior:
    - `apps/tldw-frontend/e2e/smoke/stage6-interaction-stage1.spec.ts`
  - Added `/chat` to Stage 5 release-gate critical routes:
    - `apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`
  - Supporting unit coverage added for header toggle semantics:
    - `apps/packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx`
- Plan 9 Stage 1 validation runs:
  - `cd apps/packages/ui && bunx vitest run src/components/Layouts/__tests__/ChatHeader.test.tsx src/components/Option/Playground/__tests__/TokenProgressBar.test.tsx`
  - Result: `2 passed` test files, `7 passed` tests.
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts --reporter=line`
  - Result: `2 passed` tests.
- Plan 9 Stage 2 completed (`INT-2`, `INT-3`, `INT-4`, `INT-6`):
  - Added deterministic interaction-positive smoke suite:
    - `apps/tldw-frontend/e2e/smoke/stage6-interaction-stage2.spec.ts`
  - New coverage gates:
    - `/search` -> `/knowledge` typed query + deterministic no-results AI response.
    - keyboard-only command palette open/focus/execute via `Cmd/Ctrl+K`.
    - settings sidebar navigation click + active-state verification.
- Plan 9 Stage 2 validation run:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `3 passed` tests.
- Plan 9 Stage 2 suite expansion:
  - Added `/chat` mobile composer parity + touch-target assertions to Stage 6 interaction suite:
    - `apps/tldw-frontend/e2e/smoke/stage6-interaction-stage2.spec.ts`
  - Backed by control sizing hardening in:
    - `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Plan 9 Stage 2 validation rerun after expansion:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `4 passed` tests.
- Plan 9 Stage 3 completed (release-gate wiring + stability evidence):
  - Added Stage 6 interaction gate scripts in:
    - `apps/tldw-frontend/package.json`
  - Updated frontend UX CI gate to execute interaction suite on PRs:
    - `.github/workflows/frontend-ux-gates.yml`
    - new step: `Run Stage 6 interaction regression gate`
  - Documented baseline UX release-gate acceptance criteria in:
    - `apps/tldw-frontend/README.md`
- Plan 9 Stage 3 validation run:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `5 passed` tests.
- Plan 9 Stage 3 gate rerun after Stage 2 expansion:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `6 passed` tests.
- Plan 9 Stage 3 flake-rate run:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --repeat-each=3 --reporter=line`
  - Result: `15 passed`, `0` flakes observed in this run.
- Plan 9 status: all three stages complete in `IMPLEMENTATION_PLAN_ux_audit_interaction_tests_v2.md`.
- Stage 5 closeout cross-cutting rerun completed:
  - `cd apps/tldw-frontend && TLDW_STAGE1_OUTPUT_DATE=2026-02-17 TLDW_STAGE1_OUTPUT_SUFFIX=stage5_interaction_closeout bunx playwright test e2e/smoke/stage1-route-matrix-capture.spec.ts --reporter=line`
  - Result: `1 passed`
  - Artifact: `Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_stage5_interaction_closeout.json`
  - Snapshot from artifact summary:
    - `86` routes scanned, `0` error overlays, `0` chrome runtime errors, `0` template-leak routes, `0` max-depth routes.
- Stage 5 release-gate stability hardening applied:
  - `apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`
    - added transient navigation retry handling and diagnostics reset between retry attempts.
    - route marked unavailable (skip) after repeated transient navigation failure, matching existing unavailable-route semantics.
- Stage 5 release-gate rerun:
  - `cd apps/tldw-frontend && TLDW_WEB_URL=http://localhost:8081 TLDW_WEB_CMD='bun run dev -- -p 8081' bunx playwright test e2e/smoke/stage5-release-gate.spec.ts --reporter=line`
  - Result: `11 passed`, `1 skipped` (`/chat/settings` unavailable in this local runtime after transient retries).
- Stage 5 strict-availability closeout (follow-up):
  - Root cause isolated for skipped `/chat/settings`: Turbopack dev route compile stall on that URL segment.
  - Replaced page-module alias with server redirect:
    - `apps/tldw-frontend/next.config.mjs`
      - `source: '/chat/settings'` -> `destination: '/settings/chat'` (`permanent: false`)
    - removed: `apps/tldw-frontend/pages/chat/settings.tsx`
  - Tightened Stage 5 release gate semantics in:
    - `apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`
      - strict failure on transient-unavailable critical routes (no skip fallback)
      - strict failure on non-2xx/3xx statuses
      - `/chat/settings` expected canonical path set to `/settings/chat`
  - Direct probe confirmation:
    - `/chat/settings` returns `307` immediately
    - `/settings/chat` returns `200`
  - Validation runs:
    - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage5-release-gate.spec.ts -g "Chat Settings" --reporter=line`
      - Result: `1 passed` (`6.7s`)
    - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage5-release-gate.spec.ts --reporter=line`
      - Result: `12 passed` (`21.4s`), `0` skipped
    - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
      - Result: `6 passed` (`10.4s`)
- Stage 5 program closeout validation rerun (2026-02-17):
  - `cd apps/tldw-frontend && bun run e2e:smoke:stage5` -> `12 passed` (`25.0s`)
  - `cd apps/tldw-frontend && bun run e2e:smoke:interaction` -> `6 passed` (`12.8s`)
  - `cd apps/tldw-frontend && bun run e2e:smoke:audio` -> `4 passed` (`11.9s`)
- Post-closeout remediation rerun (2026-02-17):
  - `cd apps/tldw-frontend && NEXT_DISABLE_TURBOPACK=1 TLDW_WEB_CMD='NEXT_DISABLE_TURBOPACK=1 bun run dev -- -p 8080' TLDW_STAGE1_OUTPUT_DATE=2026-02-17 TLDW_STAGE1_OUTPUT_SUFFIX=gap_remediation bunx playwright test e2e/smoke/stage1-route-matrix-capture.spec.ts --reporter=line`
  - Result: `1 passed` (`3.4m`)
  - Artifact: `Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_gap_remediation.json`
  - Route-evidence deltas captured:
    - `/chat/settings` now canonicalizes to `/settings/chat` (`redirected: true`, `consoleErrorCount: 0`)
    - `/settings/ui` and `/settings/image-generation` are `200` with `consoleErrorCount: 0`
- All in-scope UX remediation plans are now status-synced to `Complete` (Plans 1-9).
- Final severity closeout summary (baseline -> current):

| Metric | Baseline (Audit v2, 2026-02-14) | Current (Closeout, 2026-02-17) | Evidence |
|---|---:|---:|---|
| Severity 4 findings (total) | 6 | 0 open | Baseline: `Docs/UX_AUDIT_REPORT_v2.md` Section 6. Current: no route overlays (`withErrorOverlay: 0`), no wrong-content Stage 2 contracts (`11/11` expected route titles), no template leaks (`templateLeakRoutes: 0`). |
| Severity 3 findings (total) | 22 | 0 open (in-scope audited surfaces) | Baseline: `Docs/UX_AUDIT_REPORT_v2.md` Section 6. Current: Section 2 audited-nav 404 count `0` and wrong-content count `0` in route matrix/contract artifacts; `maxDepthRoutes: 0`, `timeoutStatus0: 0`, `templateLeakRoutes: 0` in Stage 1 closeout artifact; loading timeout+retry gates pass in Stage 7 (`4 passed`). |
| Manifest failed routes | 12 | 1 (intentional sentinel 404) | `Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_stage5_interaction_closeout.json` (`failed: 1`, route `/nonexistent-page-404-test`). |

- Final artifact set for program closeout:
  - `Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_stage5_interaction_closeout.json`
  - `Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_gap_remediation.json`
  - `Docs/Plans/artifacts/stage2_route_contract_check_2026-02-17_waveA_closeout.json`
  - `Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_waveA_closeout.json`
  - `Docs/Plans/artifacts/admin_route_smoke_check_2026-02-17_waveA_closeout.json`

## Ordered Implementation Tracker

| Order | Plan | Wave | Dependency | Gate to Close |
|---|---|---|---|---|
| 1 | `IMPLEMENTATION_PLAN_ux_audit_cross_cutting_stage1_route_matrix_baseline_v2.md` | Foundation | none | Baseline and rerun template ready |
| 2 | `IMPLEMENTATION_PLAN_ux_audit_settings_pages_v2.md` | A | 1 | Settings links/routes contractually valid |
| 3 | `IMPLEMENTATION_PLAN_ux_audit_admin_pages_v2.md` | A | 2 | Admin route correctness and safety controls verified |
| 4 | `IMPLEMENTATION_PLAN_ux_audit_chat_pages_v2.md` | B | 3 | Chat template and mobile usability defects closed |
| 5 | `IMPLEMENTATION_PLAN_ux_audit_audio_speech_pages_v2.md` | B | 4 | Audio template/loader lifecycle defects closed |
| 6 | `IMPLEMENTATION_PLAN_ux_audit_workspace_playground_pages_v2.md` | B | 5 | Workspace/playground content and mobile defects closed |
| 7 | `IMPLEMENTATION_PLAN_ux_audit_media_knowledge_pages_v2.md` | C | 6 | Media/knowledge reliability stabilized |
| 8 | `IMPLEMENTATION_PLAN_ux_audit_core_pages_v2.md` | C | 7 | Core route identity and a11y/mobile issues closed |
| 9 | `IMPLEMENTATION_PLAN_ux_audit_interaction_tests_v2.md` | Closure | 8 | CI interaction gate active and passing |

## Program Risks and Controls

- Risk: regression from broad route changes.
  - Control: mandatory cross-cutting smoke rerun at end of each wave.
- Risk: console-warning cleanup stalls feature delivery.
  - Control: separate runtime errors from low-risk deprecations; enforce budget by route.
- Risk: mobile fixes drift from desktop parity.
  - Control: paired viewport checks on every wave exit.
- Risk: plan drift and incomplete status updates.
  - Control: no new wave start until predecessor plan status and artifacts are updated.
