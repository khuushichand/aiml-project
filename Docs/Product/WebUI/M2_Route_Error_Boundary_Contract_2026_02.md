# M2 Route Error Boundary Contract (WebUI)

Status: Complete (Core + Prioritized Non-Core)  
Owner: WebUI  
Date: February 13, 2026  
Roadmap Link: `Docs/Product/WebUI/WebUI_UX_Strategic_Roadmap_2026_02.md`

## 1) Purpose

Provide a consistent, route-scoped recovery experience when a page crashes at render/runtime, so users can immediately continue with core workflows instead of seeing a blank screen or generic overlay.

## 2) Scope

In scope for this pass:
- Core WebUI routes:
  - `/chat`
  - `/media`
  - `/knowledge`
  - `/notes`
  - `/prompts`
  - `/settings*` (via `SettingsRoute`)
- Shared route-level fallback behavior and copy
- Stable automation selectors for smoke and QA verification
- Prioritized non-core routes with elevated instability risk from UX audit evidence (admin/tools/workspace knowledge surfaces)

Out of scope:
- Remaining long-tail experimental routes not prioritized in this iteration
- Backend error contract/API shape changes
- Feature-level domain error cards (these remain route-internal responsibilities)

## 3) Contract Requirements

### A. Fallback Surface

When a route throws during render/lifecycle:
- Render a centered recovery panel with:
  - Title: `"This page hit an unexpected error"`
  - Route context line: `"Affected route: <route label>"`
  - Brief guidance: retry first, then navigate to stable destinations
- Include diagnostic details only in non-production environments.

### B. Action Hierarchy

Fallback actions (in order):
1. Primary: `Try again` (boundary-local reset)
2. Secondary: `Go to Chat`
3. Secondary: `Open Settings`
4. Secondary: `Reload page` (hard recovery)

### C. Instrumentation + Selectors

Required `data-testid` values:
- Container: `error-boundary`
- Route scope: `route-error-boundary-<route-id>`
- Title: `route-error-title`
- Message: `route-error-message`
- Route label: `route-error-route-label`
- Actions:
  - `route-error-retry`
  - `route-error-go-chat`
  - `route-error-open-settings`
  - `route-error-reload`
- Dev diagnostics block: `route-error-details`

### D. Logging

On catch:
- Log `console.error` with route id and component stack.
- Do not expose component stack in production UI.

## 4) Adoption Map (This Iteration)

Shared boundary component:
- `apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx`

Applied routes:
- `apps/packages/ui/src/routes/option-chat.tsx`
- `apps/packages/ui/src/routes/option-media.tsx`
- `apps/packages/ui/src/routes/option-knowledge.tsx`
- `apps/packages/ui/src/routes/option-notes.tsx`
- `apps/packages/ui/src/routes/option-prompts.tsx`
- `apps/packages/ui/src/routes/settings-route.tsx`
- `apps/tldw-frontend/extension/routes/settings-route.tsx` (parity)
- `apps/packages/ui/src/routes/option-admin-server.tsx`
- `apps/packages/ui/src/routes/option-admin-llamacpp.tsx`
- `apps/packages/ui/src/routes/option-admin-mlx.tsx`
- `apps/packages/ui/src/routes/option-content-review.tsx`
- `apps/packages/ui/src/routes/option-data-tables.tsx`
- `apps/packages/ui/src/routes/option-kanban-playground.tsx`
- `apps/packages/ui/src/routes/option-chunking-playground.tsx`
- `apps/packages/ui/src/routes/option-moderation-playground.tsx`
- `apps/packages/ui/src/routes/option-flashcards.tsx`
- `apps/packages/ui/src/routes/option-quiz.tsx`
- `apps/packages/ui/src/routes/option-collections.tsx`
- `apps/packages/ui/src/routes/option-world-books.tsx`
- `apps/packages/ui/src/routes/option-dictionaries.tsx`
- `apps/packages/ui/src/routes/option-characters.tsx`
- `apps/packages/ui/src/routes/option-items.tsx`
- `apps/packages/ui/src/routes/option-document-workspace.tsx`
- `apps/packages/ui/src/routes/option-speech.tsx`
- `apps/tldw-frontend/extension/routes/option-admin-server.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-admin-llamacpp.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-admin-mlx.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-content-review.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-data-tables.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-kanban-playground.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-chunking-playground.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-moderation-playground.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-flashcards.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-quiz.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-collections.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-world-books.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-dictionaries.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-characters.tsx` (parity)
- `apps/tldw-frontend/extension/routes/option-speech.tsx` (parity)

## 5) Verification Plan

Unit tests:
- Boundary catches errors and renders contract UI.
- Reset action retries route content.
- Recovery actions render in expected order with required test IDs.
- Forced-error fixture query (`__forceRouteError`) triggers boundary fallback deterministically in non-production mode.

Smoke checks:
- Existing smoke assertion for `[data-testid="error-boundary"]` remains valid.
- Key-nav + wayfinding smoke slice stays green after boundary rollout.
- New forced-error fixture smoke slice validates non-core route recovery contract controls.

## 6) Exit Criteria for M2 Prep

- Contract document published.
- Shared boundary merged and applied to core routes.
- Unit and focused smoke validation passing.
- Roadmap + execution plan updated with implementation evidence.

## 7) Validation Evidence (February 13, 2026)

- `bunx vitest run src/components/Common/__tests__/RouteErrorBoundary.test.tsx` (`5 passed`).
- `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - Route Error Boundaries" --reporter=line` (`15 passed`).
- `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding|Route Error Boundaries)" --reporter=line` (`25 passed`).
