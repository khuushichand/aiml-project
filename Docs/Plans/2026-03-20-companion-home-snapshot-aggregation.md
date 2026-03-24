# Companion Home Snapshot Aggregation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a typed Companion Home snapshot aggregator that combines workspace snapshot, canonical inbox notifications, reading items, and notes into `inbox`, `needsAttention`, and `resumeWork` cards with deterministic dedupe.

**Architecture:** Add a new `companion-home.ts` service that orchestrates four data sources in parallel and degrades per source. Normalize loose reading and notes payloads into small typed home-entry inputs, derive `Needs Attention` client-side, and suppress derived items when the canonical inbox already represents the same entity.

**Tech Stack:** TypeScript, Vitest, existing companion service helpers, `tldwClient`, shared notifications service

---

## Stage 1: Red Tests
**Goal:** Lock the required aggregation, dedupe, and partial-failure behavior with focused tests.
**Success Criteria:** New tests fail because `fetchCompanionHomeSnapshot` or its behavior is missing.
**Tests:** `bunx vitest run src/services/__tests__/companion-home.test.ts`
**Status:** Complete

## Stage 2: Minimal Aggregator
**Goal:** Implement `fetchCompanionHomeSnapshot(surface)` and the smallest helper surface needed to normalize reading and notes data.
**Success Criteria:** Aggregator returns typed `inbox`, `needsAttention`, and `resumeWork` sections; canonical inbox wins dedupe; failures stay scoped to the affected source.
**Tests:** `bunx vitest run src/services/__tests__/companion-home.test.ts src/services/__tests__/companion.test.ts`
**Status:** Complete

## Stage 3: Verification And Commit
**Goal:** Re-run focused tests, run Bandit on touched scope per repo policy, self-review the diff, and commit the work.
**Success Criteria:** Focused tests pass, Bandit reports no new issues in touched scope, and a commit exists with the requested message.
**Tests:** `bunx vitest run src/services/__tests__/companion-home.test.ts src/services/__tests__/companion.test.ts src/services/tldw/__tests__/notes-client.test.ts`
**Status:** In Progress
