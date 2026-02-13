# M2 Route Error Boundary Contract (WebUI)

Status: Draft Implemented (M2 Prep)  
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

Out of scope:
- Non-core routes (admin/tools/playgrounds) unless they opt in later
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

## 5) Verification Plan

Unit tests:
- Boundary catches errors and renders contract UI.
- Reset action retries route content.
- Recovery actions render in expected order with required test IDs.

Smoke checks:
- Existing smoke assertion for `[data-testid="error-boundary"]` remains valid.
- Key-nav + wayfinding smoke slice stays green after boundary rollout.

## 6) Exit Criteria for M2 Prep

- Contract document published.
- Shared boundary merged and applied to core routes.
- Unit and focused smoke validation passing.
- Roadmap + execution plan updated with implementation evidence.
