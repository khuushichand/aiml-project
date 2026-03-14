# Presentation Studio Transition And Timing Controls Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add slide-level transition presets and timing controls so Presentation Studio can show effective slide duration beyond narration-only timing.

**Architecture:** Extend `metadata.studio` with a small, typed timing model and transition preset. Keep narration-derived timing as the default, then layer a manual duration override on top for UX control without changing backend contracts.

**Tech Stack:** React, Zustand, Vitest, Playwright

---

## Stage 1: Define Slide Timing Metadata
**Goal**: Add normalized transition and timing fields to the Presentation Studio store.
**Success Criteria**: Blank, loaded, duplicated, and merged slides all preserve a stable `transition`, `timing_mode`, and optional `manual_duration_ms`.
**Tests**: Store tests for normalization and manual-duration updates.
**Status**: Not Started

## Stage 2: Add Failing UX Tests
**Goal**: Describe the new editor and readiness behavior in tests before implementation.
**Success Criteria**: Tests fail because the UI does not yet show transition/timing controls or effective duration messaging.
**Tests**: `PresentationStudioPage.test.tsx`, `presentationStudioReadiness.test.ts`, `presentation-studio.store.test.tsx`
**Status**: Not Started

## Stage 3: Implement Editor And Readiness UI
**Goal**: Add the transition/timing panel and surface effective duration in editor, rail, and readiness summaries.
**Success Criteria**: Selected slide can switch transition preset, toggle auto/manual timing, and show the resulting duration consistently.
**Tests**: Targeted Vitest suite passes.
**Status**: Not Started

## Stage 4: Verify Browser Flow
**Goal**: Confirm the new controls work in the real UI without regressing the prior create/load or overflow fixes.
**Success Criteria**: Playwright audit passes and still reports successful create/detail flow with no mobile overflow.
**Tests**: `e2e/ux-audit/presentation-studio.spec.ts`
**Status**: Not Started
