# M3.2 Core Flow Accessibility QA Script

Status: Complete (Evidence Captured February 13, 2026)  
Owner: QA + WebUI  
Date: February 13, 2026  
Execution Plan: `Docs/Product/Completed/WebUI-related/M3_Design_System_A11y_Execution_Plan_2026_02.md`

## 1) Purpose

Provide a repeatable keyboard/focus accessibility script for core journeys. This script is intended for manual QA pairing with smoke automation.

## 2) Preconditions

1. Server reachable and authenticated session seeded.
2. Browser zoom 100%.
3. Test both desktop and mobile viewport.
4. For desktop keyboard checks, use hardware keyboard with visible focus ring enabled.

## 3) Route Matrix

| Flow | Route | Primary Keyboard Objective |
|---|---|---|
| Chat | `/chat` | Reach composer, send action, and header controls in predictable order |
| Media | `/media` | Reach search/filter controls and result list via keyboard only |
| Knowledge QA | `/knowledge` | Reach query field and submit action without pointer |
| Notes | `/notes` | Reach note list, editor fields, and save controls with visible focus |
| Prompts | `/prompts` | Reach tab controls and create/import actions |
| Settings | `/settings/tldw` | Reach section nav and primary actions (`Save`, `Test Connection`) |

## 4) Per-Route Steps

For each route in the matrix:

1. Navigate to route.
2. Press `Tab` repeatedly from top of page.
3. Confirm each interactive element shows a visible focus indicator.
4. Confirm focus order follows visual reading order (left-to-right, top-to-bottom in each region).
5. Use `Shift+Tab` to verify reverse order is predictable.
6. Trigger one key action (`Enter` or `Space`) and verify expected result.
7. Confirm no keyboard trap occurs in modal/panel contexts.

## 5) App Shell Checks

Run once per session:

1. Sidebar collapsed and expanded modes both expose visible focus ring on buttons.
2. Header controls (`Search`, `New Chat`, `Settings`, shortcuts) show focus ring and remain keyboard-invokable.
3. Unknown route fallback (`404`/shell fallback) exposes focusable recovery actions in deterministic order.

## 6) Pass/Fail Rules

Mark a route **Fail** when any of the following occur:

- Focus is not visible on interactive controls.
- Focus order skips critical controls or loops unexpectedly.
- Keyboard trap with no `Esc` or natural exit path.
- Primary action is mouse-only.

## 7) Evidence Format

Capture per route:

1. One screenshot with visible focus ring.
2. One short note of tab sequence outcome.
3. Any blocker with route + control identifier.

Store artifacts under:

- `Docs/Product/Completed/WebUI-related/evidence/m3_2_a11y_focus_2026_02_13/`

## 8) Execution Evidence (February 13, 2026)

Command:

- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/m3-2-a11y-focus-evidence.spec.ts --reporter=line`

Outcome:

- `2 passed` (desktop + mobile capture suites)
- Route matrix coverage: 6/6 core flows on desktop and 6/6 on mobile
- Focus target reached: `12/12` via keyboard tab sequence (no programmatic fallback required)
- Key input verification: `12/12` pass

Artifacts:

- `Docs/Product/Completed/WebUI-related/evidence/m3_2_a11y_focus_2026_02_13/desktop-route-matrix-results.json`
- `Docs/Product/Completed/WebUI-related/evidence/m3_2_a11y_focus_2026_02_13/mobile-route-matrix-results.json`
