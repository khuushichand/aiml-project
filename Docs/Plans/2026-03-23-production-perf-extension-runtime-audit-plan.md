# Production Perf And Extension Runtime Audit Plan

## Stage 1: Production Web Perf Baseline
**Goal**: Run the Next.js app from a production build instead of the dev server and capture route-level performance evidence.
**Success Criteria**: A production build is generated, served locally, and measured on a representative route set with actionable findings or an explicit "no product perf regression found" result.
**Tests**: `bun run build` or `bun run compile`; production server smoke via `curl`; route perf capture against the production URL.
**Status**: Complete

## Stage 2: Built Extension Runtime Review
**Goal**: Build the real WXT extension and exercise its options and sidepanel runtime against the live backend.
**Success Criteria**: The extension loads from an unpacked build, key entry points render, and any runtime errors or blocked flows are documented with repro steps.
**Tests**: `bun run build:chrome`; existing extension Playwright/runtime review scripts against the built artifact.
**Status**: In Progress

## Stage 3: Fix And Verify Real Findings
**Goal**: Implement only issues reproduced in the production web or built-extension environments and verify them.
**Success Criteria**: Any discovered defects are fixed with targeted regression coverage and revalidated in the same environment where they were found.
**Tests**: Focused Vitest/Playwright/pytest as appropriate; Bandit on touched scope.
**Status**: In Progress
