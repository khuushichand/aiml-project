# Companion Home Layout Customization Task 6 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add local-only, per-surface Companion Home layout persistence and a constrained customize-home drawer on top of the existing Task 5 page architecture.

**Architecture:** Keep the current Companion Home header, setup/status band, summary strip, and quick-action shell intact. Add a small layout store module that loads/saves a card order plus visibility overrides per surface, then let `CompanionHomePage` render system cards plus visible core cards from that layout while a drawer handles hide/reorder controls.

**Tech Stack:** React, Vitest, Testing Library, local `chrome.storage.local` or `localStorage` persistence, existing Companion Home card components.

---

## Stage 1: Layout Store
**Goal**: Create a boring, testable layout module with shared defaults and per-surface persistence.
**Success Criteria**: Defaults include the current Task 5 card IDs; system cards remain visible/pinned; saved surface overrides round-trip through `chrome.storage.local` first and `localStorage` fallback second.
**Tests**: `src/store/__tests__/companion-home-layout.test.ts`
**Status**: Complete

## Stage 2: Customize Drawer
**Goal**: Add a drawer component that exposes constrained visibility and reorder controls for the current core cards.
**Success Criteria**: System cards show as fixed; core cards can be hidden/shown and moved; interactions emit updated layout data through callbacks.
**Tests**: `src/components/Option/CompanionHome/__tests__/CustomizeHomeDrawer.test.tsx`
**Status**: Complete

## Stage 3: Page Integration
**Goal**: Wire the layout store and drawer into `CompanionHomePage` without disturbing the Task 5 header/summary/quick-action structure.
**Success Criteria**: A `Customize Home` action opens the drawer, the page renders cards in persisted order, and hidden core cards are omitted while system cards stay present.
**Tests**: `src/components/Option/CompanionHome/__tests__/CompanionHomePage.test.tsx`
**Status**: Complete

## Stage 4: Verification and Commit
**Goal**: Run the focused suite, run Bandit on touched Python scope only if any Python files changed, and create the requested commit.
**Success Criteria**: Focused Vitest suite passes cleanly and the worktree has a commit with message `feat: add companion home layout customization`.
**Tests**: `bunx vitest run --config vitest.config.ts src/store/__tests__/companion-home-layout.test.ts src/components/Option/CompanionHome/__tests__/CustomizeHomeDrawer.test.tsx src/components/Option/CompanionHome/__tests__/CompanionHomePage.test.tsx`
**Status**: Complete
