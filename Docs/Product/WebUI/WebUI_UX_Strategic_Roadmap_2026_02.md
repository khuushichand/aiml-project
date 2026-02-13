# WebUI UX Strategic Roadmap (2026 Q1-Q2)

Status: Active  
Owner: WebUI + Product  
Contributors: QA, Accessibility, Core Platform  
Last Updated: February 13, 2026  
Source Inputs: UX audit run on February 12, 2026 (`apps/tldw-frontend/cdp-artifacts/ux-audit-2026-02-12T17-06-10-791Z`)

## 1) Objective

Stabilize and align WebUI UX for technical/research users by sequencing immediate high-impact fixes first, then executing strategic improvements that reduce regressions and improve discoverability, accessibility, and task completion.

## 2) Strategic Initiatives

1. Navigation and IA Consolidation
2. Resilience and Error-State Architecture
3. Design System and Accessibility Baseline
4. Ingestion-First Onboarding Journey
5. UX Governance and Release Gates

## 3) Milestone Roadmap

| Milestone | Date Window | Focus | Owner | Status | Exit Criteria |
|---|---|---|---|---|---|
| M0 | Feb 12, 2026 | Quick-win stabilization pass | WebUI | Complete | Critical runtime crashes addressed, blank redirect routes replaced, 404 recovery actions added |
| M1 | Feb 13-Mar 6, 2026 | Navigation and IA consolidation | WebUI + Product | Complete | Canonical route map published, legacy alias behavior standardized, discoverability gaps prioritized |
| M2 | Mar 9-Mar 20, 2026 | Error-state architecture | WebUI + Platform | Complete | Route-level recovery UX and shared error contract in core flows |
| M3 | Mar 23-Apr 10, 2026 | Design system and WCAG baseline | WebUI + Accessibility | Not Started | Baseline tokens/components documented, AA checks defined for core journeys |
| M4 | Apr 13-Apr 24, 2026 | Ingestion-first onboarding | WebUI + Product | Not Started | Connect -> ingest -> verify -> chat guided journey shipped |
| M5 | Apr 27-May 15, 2026 | UX governance and release gates | QA + WebUI | Not Started | UX smoke suite and release quality gates active in CI |

## 4) Milestone Details and Tracking

## M0: Quick-Win Stabilization (Completed)
Planned Date: February 12, 2026  
Status: Complete

- [x] Fix Prompt Studio loading crash caused by object-valued translation key.
- [x] Harden message API usage fallback to prevent save-flow crash.
- [x] Replace blank alias-route transitions with explicit redirect state.
- [x] Add actionable 404 page with recovery paths.
- [x] Improve media empty-state discoverability with direct Quick Ingest CTA.
- [x] Prevent command palette shortcut from interrupting focused text entry.
- [x] Add redirect helper unit tests.

Success Metrics:
- Zero reproductions of identified runtime crashes in targeted validation.
- Redirect helper tests passing.

## M1: Navigation and IA Consolidation
Planned Date: February 13-March 6, 2026  
Status: Complete
Execution Plan: `Docs/Product/WebUI/M1_Navigation_IA_Execution_Plan_2026_02.md`

Deliverables:
- Canonical route inventory and deprecation map for aliases.
- Navigation label normalization for main IA entry points.
- Wayfinding updates for key sections (chat, knowledge, media, settings).

Tracking Checklist:
- [x] Canonical sitemap doc published under `Docs/Product/WebUI/` (`Docs/Product/WebUI/M1_1_Canonical_Route_Inventory_2026_02.md`).
- [x] Canonical route/alias inventory approved and linked from execution plan governance closeout (`Docs/Product/WebUI/M1_Navigation_IA_Execution_Plan_2026_02.md`).
- [x] Alias route telemetry added (route hit counts + source route) via `apps/packages/ui/src/utils/route-alias-telemetry.ts` and `apps/tldw-frontend/components/navigation/RouteRedirect.tsx`.
- [x] Navigation terminology inconsistencies triaged and assigned (`Docs/Product/WebUI/M1_2_Navigation_Terminology_Triage_2026_02.md`).
- [x] First key-nav smoke baseline captured (`Docs/Product/WebUI/M1_4_Route_Health_Snapshot_2026_02_12.md`).
- [x] Wayfinding keyboard/focus checks and manual QA script added (`apps/packages/ui/src/components/Layouts/__tests__/settings-layout-focus-order.test.tsx`, `apps/tldw-frontend/__tests__/navigation/not-found-page.test.tsx`, `Docs/Product/WebUI/M1_3_Wayfinding_Manual_QA_Script_2026_02.md`).
- [x] Key-nav + wayfinding focused smoke rerun passing after route parity and settings-route cycle fix (`Docs/Product/WebUI/M1_4_Route_Health_Snapshot_2026_02_12.md`).
- [x] Alias telemetry weekly rollup helper added for source/destination trend snapshots (`apps/packages/ui/src/utils/route-alias-telemetry.ts`).
- [x] Shell-level unknown-route recovery fallback aligned to wayfinding language (`apps/packages/ui/src/routes/app-route.tsx`, `apps/tldw-frontend/extension/routes/app-route.tsx`).
- [x] Full smoke parity restored after selector alignment (`apps/tldw-frontend/e2e/smoke/page-inventory.ts`, `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`).
- [x] Runtime-overlay smoke guard added for crash-signature detection (`apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`).
- [x] First weekly alias rollup capture recorded via `getRouteAliasTelemetryRollup({ topN: 10 })` and attached to M1.4 snapshot (`Docs/Product/WebUI/M1_4_Route_Health_Snapshot_2026_02_12.md`).
- [x] Controlled non-zero Week 2 alias rollup capture recorded via Playwright and persisted to snapshot artifact (`apps/tldw-frontend/e2e/smoke/alias-rollup-capture.spec.ts`, `Docs/Product/WebUI/M1_4_Alias_Rollup_Week2_Controlled_2026_02_13.json`).
- [x] M1.2 terminology closeout verified with command-palette shortcut test, focused key-nav/wayfinding smoke, full smoke rerun, and desktop/mobile evidence capture (`Docs/Product/WebUI/M1_2_Navigation_Terminology_Triage_2026_02.md`, `Docs/Product/WebUI/evidence/m1_2_label_alignment_2026_02_13/`).
- [x] Alias deprecation candidates prioritized for M2+ backlog with threshold policy (`Docs/Product/WebUI/M1_Navigation_IA_Execution_Plan_2026_02.md`).

Success Metrics:
- Alias route usage trend visible weekly.
- Reduced wrong-route landings in UX smoke runs.

## M2: Resilience and Error-State Architecture
Planned Date: March 9-March 20, 2026  
Status: Complete

Deliverables:
- Shared frontend error UI contract for empty/loading/error states.
- Route-level error boundaries for primary surfaces.
- Actionable recovery CTAs on critical failure states.

Tracking Checklist:
- [x] Error boundary pattern agreed and documented (`Docs/Product/WebUI/M2_Route_Error_Boundary_Contract_2026_02.md`).
- [x] Core routes covered: chat, knowledge, media, notes, prompts, settings (`apps/packages/ui/src/routes/option-chat.tsx`, `apps/packages/ui/src/routes/option-media.tsx`, `apps/packages/ui/src/routes/option-knowledge.tsx`, `apps/packages/ui/src/routes/option-notes.tsx`, `apps/packages/ui/src/routes/option-prompts.tsx`, `apps/packages/ui/src/routes/settings-route.tsx`).
- [x] Retry/recover actions included in failure states (`apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx`).
- [x] Prioritized non-core admin/tool routes covered with route-level boundaries (admin + review/data/playground routes in package and extension route trees).
- [x] Forced-error smoke assertions added for route-boundary recovery contract (`apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`).
- [x] Forced-error smoke coverage expanded to additional non-core knowledge/workspace routes with route-boundary parity (`/collections`, `/world-books`, `/dictionaries`, `/characters`, `/items`, `/document-workspace`, `/speech`).

Progress update (February 13, 2026):
- Added shared route-level fallback component with standardized test IDs and recovery actions (`Try again`, `Go to Chat`, `Open Settings`, `Reload page`).
- Added boundary unit tests (`apps/packages/ui/src/components/Common/__tests__/RouteErrorBoundary.test.tsx`).
- Revalidated key-nav + wayfinding smoke after rollout (`10 passed`).
- Extended boundary coverage to prioritized non-core admin/tool plus selected knowledge/workspace surfaces (Server Admin, Llama.cpp Admin, MLX Admin, Content Review, Data Tables, Kanban, Chunking, Moderation, Flashcards, Quiz, Collections, World Books, Dictionaries, Characters, Items, Document Workspace, Speech) with package/extension parity where applicable.
- Added deterministic forced-error fixture support (`__forceRouteError`) in `RouteErrorBoundary` for smoke validation.
- Added and validated route-boundary smoke slice: `15 passed` (`Smoke Tests - Route Error Boundaries`), plus combined key-nav + wayfinding + route-boundary rerun: `25 passed`.
- M1 governance closeout completed: canonical vocabulary received product sign-off, canonical inventory approval linked, and deprecation candidates were prioritized for M2+ backlog planning.
- Captured first passive natural-traffic alias rollup sample and week-over-week comparison input (`Docs/Product/WebUI/M1_4_Alias_Rollup_Week3_Natural_2026_02_13.json`, `Docs/Product/WebUI/M1_4_Route_Health_Snapshot_2026_02_12.md`).
- Added release-note template language for route-boundary recoverability and troubleshooting links (`Docs/Product/WebUI/M2_Release_Note_Template_Route_Recoverability_2026_02.md`).

Success Metrics:
- No uncaught runtime errors in core smoke suite.
- Mean time to recovery from common UI errors reduced.

## M3: Design System and Accessibility Baseline
Planned Date: March 23-April 10, 2026  
Status: Not Started

Deliverables:
- Core visual/interaction tokens documented for shared components.
- Accessibility checklist mapped to WCAG 2.2 AA for core flows.
- Keyboard and focus behavior normalized across app shell.

Tracking Checklist:
- [ ] Token coverage reviewed for buttons, inputs, alerts, and empty states.
- [ ] Focus-visible and keyboard path checks for top workflows.
- [ ] Contrast audit pass for primary UI palette.

Success Metrics:
- AA issues in core flows reduced sprint-over-sprint.
- Consistent focus and keyboard behavior in all audited routes.

## M4: Ingestion-First Onboarding Journey
Planned Date: April 13-April 24, 2026  
Status: Not Started

Deliverables:
- Guided first-run flow from connection to successful ingestion.
- Contextual prompts for next-best action after first ingest.
- Onboarding copy and affordances aligned with technical user goals.

Tracking Checklist:
- [ ] First-run flow spec approved.
- [ ] End-to-end happy path test added.
- [ ] Post-ingest recommendation states implemented.

Success Metrics:
- Time-to-first-ingest decreases.
- Higher completion rate of first chat using ingested material.

## M5: UX Governance and Release Gates
Planned Date: April 27-May 15, 2026  
Status: Not Started

Deliverables:
- UX smoke suite for empty/error/loading/responsive regressions.
- Release checklist with UX severity gates.
- Defect SLA and ownership model for UX blockers.

Tracking Checklist:
- [ ] CI workflow includes UX smoke job.
- [ ] Severity rubric mapped to release decisions.
- [ ] Regression reporting integrated into release notes.

Success Metrics:
- Fewer UX regressions escaping to integration branches.
- Clear go/no-go signal for high-severity UX defects.

## 5) Dependencies

- WebUI route and layout ownership alignment.
- QA bandwidth for smoke automation and regression triage.
- Accessibility review support for WCAG 2.2 AA checks.
- Product support for terminology and IA decisions.

## 6) Risks and Mitigations

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Cross-team dependency delays | Milestone slip | Weekly dependency review and escalation path | Product |
| Test environment instability | False-negative validation | Keep targeted unit checks plus manual smoke fallback | QA |
| Scope creep in IA and design-system work | Reduced throughput | Strict milestone exit criteria and backlog cut lines | WebUI |

## 7) Cadence and Reporting

- Weekly roadmap check-in every Friday.
- Milestone status update in this document with date stamp.
- Blockers tracked in section updates and triaged within 2 business days.

## 8) Immediate Next Actions (Week of Feb 16, 2026)

1. Completed: Collected first passive natural-traffic alias rollup capture and linked week-over-week comparison input (`Docs/Product/WebUI/M1_4_Alias_Rollup_Week3_Natural_2026_02_13.json`, `Docs/Product/WebUI/M1_4_Route_Health_Snapshot_2026_02_12.md`).
2. Completed: Added release-note template language for route-boundary recoverability and troubleshooting handoff (`Docs/Product/WebUI/M2_Release_Note_Template_Route_Recoverability_2026_02.md`).
3. Completed: Expanded forced-error route-boundary smoke coverage to selected remaining non-core routes and revalidated focused suites (`apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`).
