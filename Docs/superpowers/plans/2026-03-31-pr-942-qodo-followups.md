# PR 942 Qodo Follow-Ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address the remaining valid Qodo review findings on PR #942 without broadening the eval branch scope.

**Architecture:** Keep the fixes narrowly scoped to the current PR branch. Add regression tests first for connector callback base validation and RAG rerank metadata exposure, then implement the smallest backend changes that satisfy those tests and preserve existing behavior.

**Tech Stack:** FastAPI, pytest, SQLite/PostgreSQL connector helpers, unified RAG pipeline, Bandit

---

## Stage 1: Confirm Scope
**Goal:** Verify which Qodo items still apply on the squashed PR head.
**Success Criteria:** Remaining valid items are pinned to exact files and invalid/already-fixed items are explicitly noted.
**Tests:** None
**Status:** Complete

## Stage 2: Regression Tests
**Goal:** Add failing tests for the still-valid Qodo findings.
**Success Criteria:** New tests fail against current code for redirect-base trust and rerank metadata exposure.
**Tests:** Targeted pytest files under `tldw_Server_API/tests/External_Sources/` and `tldw_Server_API/tests/RAG_NEW/`
**Status:** Complete

## Stage 3: Minimal Fixes
**Goal:** Implement the backend changes required to satisfy the new regressions.
**Success Criteria:** Connector OAuth flows reject unsafe callback bases unless explicitly configured, and debug rerank document snapshots no longer leak into normal response metadata.
**Tests:** Re-run targeted pytest files
**Status:** Complete

## Stage 4: Verification
**Goal:** Prove the touched scope is green and security-clean.
**Success Criteria:** Targeted pytest passes and Bandit reports no new findings in the modified backend files.
**Tests:** Targeted pytest + Bandit
**Status:** Complete
