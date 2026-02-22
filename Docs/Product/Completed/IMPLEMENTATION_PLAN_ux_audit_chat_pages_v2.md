# Implementation Plan: UX Audit v2 Chat Pages

## Scope

Pages: Chat, Chat Settings, Chat Agent, Persona, Quick Chat Popout  
Issue IDs: `CHAT-1` through `CHAT-11`

## Issue Grouping Coverage

- `CHAT-1`: Raw `{{percentage}}` template leak
- `CHAT-2`: Redundant connect-to-server messaging
- `CHAT-3`: Mobile toolbar icon density too high
- `CHAT-4`: SEND touch target under 44x44px
- `CHAT-5`: Long settings page lacks section navigation
- `CHAT-6`: Multiple ambiguous Save actions
- `CHAT-7`: Agent empty state lacks explanation
- `CHAT-8`: "Select a workspace" input affordance confusion
- `CHAT-9`: Persona icons missing labels/tooltips
- `CHAT-10`: Desktop/mobile control parity mismatch
- `CHAT-11`: "k=3" jargon labeling

## Stage 1: Data Rendering and Empty-State Clarity
**Goal**: Eliminate template leaks and improve chat/agent state comprehension.
**Success Criteria**:
- `{{percentage}}` never renders to users; fallback value logic is in place.
- Redundant connection placeholders are consolidated into one clear state.
- Chat Agent empty state explains capability, prerequisites, and next action.
- Workspace selector affordance is visually distinct from chat input.
**Tests**:
- Component tests for memory indicator fallback rendering.
- Snapshot tests for chat disconnected/connected states.
- Agent empty-state copy/CTA integration test.
**Status**: Complete

## Stage 2: Mobile Input and Toolbar Usability
**Goal**: Make chat actions reliably usable on small viewports.
**Success Criteria**:
- Toolbar actions collapse/prioritize without losing discoverability.
- SEND button and key controls meet minimum touch target sizes.
- Persona/chat icon actions expose labels via visible text or tooltips.
**Tests**:
- Mobile viewport E2E tests for send, attach, and settings actions.
- Accessibility checks for button labels and focus behavior.
**Status**: Complete

## Stage 3: Settings Information Architecture
**Goal**: Reduce cognitive load in chat settings and clarify save scope.
**Success Criteria**:
- Settings sections are navigable (anchors/tabs/segmented navigation).
- Save actions are scoped and labeled by section or unified consistently.
- "k=3" terminology replaced with user-facing label (for example, "Memory results").
**Tests**:
- Integration tests for section navigation and scoped save behavior.
- Copy regression tests for updated terminology.
**Status**: Complete

## Stage 4: Cross-Viewport Parity and Regression Guardrails
**Goal**: Ensure controls and capabilities are consistent across desktop and mobile.
**Success Criteria**:
- Critical controls (new session, memory settings, retrieval count) are available and discoverable on both viewports.
- No hidden control regressions between responsive breakpoints.
- Chat route console noise remains below defined threshold.
**Tests**:
- Responsive parity checklist tests for chat and persona.
- Console warning budget assertions in Playwright run.
**Status**: Complete

## Implementation Notes (2026-02-16)

- Consolidated disconnected-chat messaging by suppressing header `ConnectionBanner` on empty transcripts so users see one clear offline state card instead of duplicated guidance.
- Clarified Agent route prerequisites:
  - added explicit workspace-required empty state copy,
  - added CTA to focus/open workspace selector,
  - updated disabled composer placeholder copy to reference workspace selection.
- Added stable test hook on workspace selector trigger (`data-testid="agent-workspace-selector"`).
- Improved touch-target sizing on chat send controls:
  - desktop/pro send and send-options controls use minimum `44px` target height,
  - compact/mobile send button now enforces minimum `44px` target height.
- Added section navigation chips to `/chat/settings` for long-form settings wayfinding.
- Scoped ambiguous settings save actions with explicit labels:
  - `Save normal prompt`,
  - `Save RAG prompts`,
  - `Save server URL`,
  - `Save RAG defaults`.
- Replaced persona `k=<n>` jargon with `Memory results: <n>` across control labels and memory plan diagnostics (`requested/applied`).

## Kickoff Validation (2026-02-16)

- Persona route unit suite rerun:
  - `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
  - Result: `6 passed`.
- Added persona test assertions for:
  - visible `Memory results: 3` label,
  - absence of raw `k=3` label,
  - memory diagnostics copy (`requested memory results`, `applied results`).
- Full-package TypeScript compile check remains red due pre-existing, unrelated type/test-env issues in the UI package baseline; no new compile gate was introduced for this plan slice.

## Progress Update (2026-02-17)

- Stage 2 (`CHAT-3`, `CHAT-4`) implementation advanced in compact chat composer:
  - compact icon controls now use minimum `44x44` touch targets,
  - compact icon controls now include visible short labels (`Image`, `Voice`, `Config`, `Dictate`, `Stop`) to reduce icon-only ambiguity on mobile-sized layouts.
  - file updated:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- Added regression contract coverage for compact toolbar a11y/interaction affordances:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts`
  - validates:
    - compact control touch target class contract (`min-h/min-w 44px`),
    - presence of compact visible-label keys for icon actions.
- Validation rerun:
  - `cd apps/packages/ui && bunx vitest run src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts src/routes/__tests__/sidepanel-persona.test.tsx`
  - Result: `8 passed`.
- Focused route smoke validation:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Chat (/chat)" --workers=1 --reporter=line`
  - Result: `2 passed`.
- Stage 2 + Stage 4 closure updates:
  - mobile chat composer controls on `/chat` now enforce touch-target minimums in the active `PlaygroundForm` path:
    - `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
    - attachment controls (`Attach image`, `More attachments`) now use mobile `lg` sizing (`44px` targets),
    - send + send-options controls now enforce mobile `min-h/min-w` `44px`.
  - added Stage 6 mobile interaction parity coverage for chat controls:
    - `apps/tldw-frontend/e2e/smoke/stage6-interaction-stage2.spec.ts`
    - validates on mobile viewport:
      - `Attach image`, `Send message`, and `Open send options` controls are visible,
      - each control reports measurable touch targets `>= 44px`.
  - added responsive parity guardrail coverage for persona controls:
    - `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
    - validates `Resume session`, `Memory`, and `Memory results` controls at `390px` and `1280px`.
- Validation reruns after Stage 2/4 closure:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx src/components/Option/Playground/__tests__/TokenProgressBar.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts`
  - Result: `4 passed` test files, `16 passed` tests.
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `4 passed`.
