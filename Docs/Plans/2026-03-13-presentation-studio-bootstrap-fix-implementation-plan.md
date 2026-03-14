# Presentation Studio Bootstrap Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unblock Presentation Studio project creation and initial detail loading in the WebUI.

**Architecture:** Keep the fix local to the Presentation Studio bootstrap layer. Make `/presentation-studio/new` strict-mode-safe by sharing the in-flight create request across effect replays, and make `/presentation-studio/:projectId` clear loading state independently of lifecycle cleanup ordering so successful loads cannot strand the page on a loading banner.

**Tech Stack:** React, Zustand, Vitest, Testing Library, Playwright.

---

## Stage 1: Reproduce The Broken Bootstrap States
**Goal**: Lock the known regressions into tests before changing runtime code.
**Success Criteria**: There is a failing unit regression for strict-mode new-project creation, and a failing verification path for detail bootstrap.
**Tests**: `vitest` targeted Presentation Studio page tests; existing focused Playwright audit as integration evidence.
**Status**: In Progress

## Stage 2: Fix New And Detail Bootstrap Lifecycles
**Goal**: Make PresentationStudioPage resilient to React strict mode and rerender timing.
**Success Criteria**: Successful create redirects to detail and successful detail fetch exits the loading state reliably.
**Tests**: Re-run targeted Vitest suite.
**Status**: Not Started

## Stage 3: Verify In Browser
**Goal**: Confirm the real WebUI no longer strands users on “Creating presentation…” or “Loading presentation…”.
**Success Criteria**: The focused Playwright Presentation Studio audit reaches the editor instead of the loading banners.
**Tests**: `bunx playwright test e2e/ux-audit/presentation-studio.spec.ts --project=chromium --reporter=line`
**Status**: Not Started
