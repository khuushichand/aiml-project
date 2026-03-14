## Stage 1: Audit Setup
**Goal**: Prepare an isolated audit workflow for Presentation Studio on latest `origin/dev`.
**Success Criteria**: Clean worktree confirmed, target route/components identified, and a focused audit path chosen.
**Tests**: Verify Presentation Studio routes/components exist and Playwright can target them.
**Status**: Complete

## Stage 2: Focused Playwright Coverage
**Goal**: Add a dedicated Playwright spec that exercises Presentation Studio project creation and captures audit artifacts.
**Success Criteria**: A deterministic spec opens `/presentation-studio/new`, reaches the editor route, and stores screenshots/diagnostics for review.
**Tests**: Run the new Playwright spec locally against the dev server/backend.
**Status**: In Progress

## Stage 3: Live UX Validation
**Goal**: Run the app locally and collect evidence from the real UI on desktop and mobile viewports.
**Success Criteria**: Backend/frontend start successfully, the spec passes, and audit artifacts are generated.
**Tests**: Execute the focused Playwright test and inspect resulting screenshots/logs.
**Status**: Not Started

## Stage 4: Heuristic Review
**Goal**: Evaluate the captured UI against Nielsen Norman Group heuristics and identify concrete UX improvements.
**Success Criteria**: Findings are prioritized, tied to evidence from the audit, and translated into actionable design recommendations.
**Tests**: Manual review of screenshots, captured diagnostics, and relevant component code.
**Status**: Not Started
