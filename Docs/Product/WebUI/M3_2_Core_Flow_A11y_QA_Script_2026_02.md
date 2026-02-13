# M3.2 Core Flow Accessibility QA Script

Status: In Progress  
Owner: QA + WebUI  
Date: February 13, 2026  
Execution Plan: `Docs/Product/WebUI/M3_Design_System_A11y_Execution_Plan_2026_02.md`

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

- `Docs/Product/WebUI/evidence/m3_2_a11y_focus_<date>/`
