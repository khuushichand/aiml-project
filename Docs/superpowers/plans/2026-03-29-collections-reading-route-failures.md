# Collections Reading Route Failures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the failing Collections item/reading/digest API tests by identifying the route registration or prefix regression and fixing the smallest production path.

**Architecture:** Treat the 404s as a router wiring problem first, not eleven unrelated endpoint bugs. Reproduce the failures in isolation, compare the expected test paths against the registered FastAPI routes and endpoint modules, then patch the smallest missing include/prefix/alias path and verify with focused tests.

**Tech Stack:** FastAPI, pytest, Collections endpoints, reading digest jobs, API router registration

---

## Stage 1: Reproduce And Map Missing Routes
**Goal:** Confirm which exact request paths are returning 404 and whether the failure is route registration or handler-level behavior.
**Success Criteria:** Each failing test is reproduced directly or narrowed to the specific missing route path.
**Tests:** The 11 failing pytest node IDs from the report plus route inspection.
**Status:** Complete

- [x] Run `test_items_get_by_id`
- [x] Run `test_reading_bulk_alias`
- [x] Run the reading digest CRUD/job tests
- [x] Run the reading highlight/import-export tests
- [x] Inspect registered `/api/v1/...` routes and expected prefixes

## Stage 2: Patch Router/Endpoint Regression
**Goal:** Fix the smallest code path responsible for the missing Collections reading endpoints.
**Success Criteria:** The originally missing routes resolve to the intended handlers and the failing tests pass in isolation.
**Tests:** Re-run the failing tests immediately after each code change.
**Status:** Complete

- [x] Add a failing reproduction if existing tests do not isolate the route mismatch cleanly
- [x] Fix the missing router include, alias route, or prefix mismatch
- [x] Verify reading digest output creation behavior if any handler-level failure remains after routing is fixed

## Stage 3: Verify And Close
**Goal:** Prove the routing fix holds across the Collections reading surface and does not introduce new security findings.
**Success Criteria:** Focused Collections tests are green and Bandit shows no new findings from the touched code.
**Tests:** Original failing subset, nearby Collections reading tests, and Bandit on touched files.
**Status:** Complete

- [x] Re-run all originally failing Collections tests together
- [x] Re-run nearby Collections reading/item tests identified during debugging
- [x] Run `python -m bandit` on touched files from the project venv
