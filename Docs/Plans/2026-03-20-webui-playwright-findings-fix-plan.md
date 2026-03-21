# WebUI Playwright Findings Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the user-facing issues found during the live Playwright walkthrough across Knowledge QA, onboarding/Quick Ingest, sidebar navigation, and backend error delivery.

**Architecture:** Keep the fixes narrow and behavior-driven. Use targeted regression tests to lock each failure first, then apply the smallest production changes: bind the Knowledge QA streaming client call, send the onboarding ingest CTA to a route that mounts the global Quick Ingest host, route the Chat shortcut directly to `/chat`, and preserve CORS headers on unhandled backend errors so browser clients receive readable JSON failures instead of opaque fetch errors.

**Tech Stack:** React, Vitest, FastAPI, Starlette/FastAPI middleware, pytest

---

## Stage 1: Knowledge QA Streaming
**Goal:** Fix the unbound `ragSearchStream` call so streaming Knowledge QA works instead of silently falling back.
**Success Criteria:** A regression test proves the provider calls the client method with the correct `this` binding and streaming results are used without throwing `normalizeRagQuery` errors.
**Tests:** `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
**Status:** Complete

## Stage 2: Onboarding and Chat Entry UX
**Goal:** Make the onboarding ingest CTA open Quick Ingest reliably and make the Chat shortcut land on the actual chat surface.
**Success Criteria:** The onboarding CTA navigates to a route that mounts the Quick Ingest modal host before dispatching the intro event, and the chat shortcut target is `/chat`.
**Tests:** `apps/packages/ui/src/components/Option/Onboarding/__tests__/OnboardingConnectForm.test.tsx`, `apps/packages/ui/src/components/Layouts/__tests__/HeaderShortcuts.test.tsx`
**Status:** Complete

## Stage 3: Backend 500 CORS Delivery
**Goal:** Preserve CORS headers on backend unhandled-error responses so browser clients can read JSON 500s instead of surfacing opaque network failures.
**Success Criteria:** Requests with an allowed `Origin` still receive `Access-Control-Allow-Origin` on the global exception path.
**Tests:** `tldw_Server_API/tests/Config/test_route_and_cors_guards.py` or a new focused CORS error-path test under `tldw_Server_API/tests`
**Status:** Complete

## Stage 4: Verification
**Goal:** Confirm the targeted regressions pass and the browser walkthrough no longer reproduces the original failures.
**Success Criteria:** Targeted Vitest/pytest/Bandit runs pass and a final Playwright walkthrough confirms the fixed flows.
**Tests:** targeted suites above plus a live Playwright sanity pass
**Status:** Complete
