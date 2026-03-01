# M1.3 Wayfinding Manual QA Script

Status: Active  
Owner: WebUI + QA  
Milestone: M1.3 (Wayfinding + recovery UX alignment)  
Last Updated: February 12, 2026  
Related:
- `Docs/Product/Completed/WebUI-related/M1_Navigation_IA_Execution_Plan_2026_02.md`
- `Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`

## Goal

Validate that users can identify where they are and recover quickly from moved or missing routes using keyboard and pointer input.

## Test Environment

- WebUI: `http://localhost:3000`
- API: `http://127.0.0.1:8000`
- Auth: single-user API key mode
- Browser: Chromium latest
- Viewports:
  - Desktop: `1440x900`
  - Mobile: `375x812`

## Evidence Capture

For each scenario capture:
- URL visited
- Screenshot before and after action
- Pass/Fail
- Notes on copy clarity and keyboard behavior

Store evidence under:
- `apps/tldw-frontend/test-results/` (automated)
- `Docs/Product/Completed/WebUI-related/evidence/m1_3_wayfinding/README.md` (manual artifacts)

## Scenario A: Settings Active-Route Clarity

1. Open `/settings/tldw`.
2. Confirm left settings nav has exactly one active destination marker (`aria-current="page"` visual state).
3. Confirm "Current section" summary is visible above settings content.
4. Keyboard check:
   - Press `Tab` until first settings nav item is focused.
   - Continue to next settings item and activate with `Enter`.
   - Confirm URL and "Current section" update to the selected route.

Expected:
- Active route is visually and semantically indicated.
- Current-section summary matches selected settings destination.

## Scenario B: Alias Redirect Clarity

1. Open alias route `/search?q=qa-check`.
2. Confirm navigation lands on canonical route `/knowledge` and retains query string.
3. Repeat for:
   - `/config` -> `/settings`
   - `/review` -> `/media-multi`

Expected:
- User lands on canonical destination with no blank/empty intermediate state.
- Recovery actions remain available if route transition is interrupted.

## Scenario C: 404 Recovery Language + Keyboard Path

1. Open `/__wayfinding-manual-missing-route__`.
2. Confirm 404 page copy:
   - Title: "We could not find that route"
   - Route context line includes the attempted URL.
3. Confirm recovery controls appear in this order:
   - Go to Chat
   - Open Knowledge
   - Open Media
   - Open Settings
   - Go back
4. Keyboard check:
   - Focus first recovery action.
   - Use `Tab` to step through each control in order.
   - Activate "Go to Chat" with `Enter` and confirm route change to `/`.

Expected:
- Recovery language is consistent and action-oriented.
- Keyboard traversal order matches visual order.
- Primary action returns user to a known-safe route.

## Scenario D: Mobile Wayfinding Sanity

1. Repeat Scenarios A-C at `375x812`.
2. Confirm no control clipping, overlap, or unreachable actions.
3. Confirm tap targets are reachable without zooming.

Expected:
- Wayfinding and recovery controls are usable at mobile breakpoint.

## Defect Logging Template

Use this format per issue:

```
ID:
Scenario:
Viewport:
Route:
Observed:
Expected:
Severity:
Screenshot:
```

## Exit Criteria

- No P1/P2 issues on wayfinding or recovery interactions.
- Keyboard traversal for settings and 404 recovery is verified on desktop.
- Alias redirects consistently land on canonical routes without blank states.
