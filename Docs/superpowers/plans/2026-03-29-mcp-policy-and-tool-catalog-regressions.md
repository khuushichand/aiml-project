# MCP Policy And Tool Catalog Regressions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the failing MCP Hub policy provenance test and verify the Postgres MCP tool catalog tests against the checked-in code.

**Architecture:** Treat the failures as two separate paths until reproduction proves otherwise. Reproduce the provenance mismatch directly, then use a controlled local import stub to run the Postgres-gated MCP tests far enough to determine whether the reported `get_db_pool` error still exists on the checked-in code before changing production behavior.

**Tech Stack:** FastAPI, pytest, MCP unified protocol, AuthNZ database pool, Postgres integration tests

---

## Stage 1: Reproduce And Isolate
**Goal:** Confirm the exact assertion delta and capture the full traceback for the Postgres errors.
**Success Criteria:** Each failing node is reproduced with enough detail to identify the layer that regressed.
**Tests:** The three reported pytest node IDs.
**Status:** Complete

- [x] Run the failing provenance test directly
- [x] Run the two failing Postgres tool catalog tests directly
- [x] Capture the exact traceback and failing payload diffs
- [x] Map each failure to the owning production module

## Stage 2: Patch Minimal Root Causes
**Goal:** Apply the smallest correction supported by reproduction evidence.
**Success Criteria:** The provenance expectation matches the current resolver contract and no unsupported production fix is applied for the non-reproducing Postgres report.
**Tests:** Re-run the failing node after each change.
**Status:** Complete

- [x] Add or tighten a failing test only if the existing failures do not isolate the regression cleanly
- [x] Fix the policy provenance expectation drift in the override test
- [x] Verify the reported `get_db_pool` error does not reproduce on the checked-in MCP tool catalog path

## Stage 3: Verify And Close
**Goal:** Prove the targeted MCP investigation is resolved and document any residual limits.
**Success Criteria:** The provenance test is green, the Postgres catalog tests are shown passing when run through the local import gate workaround, and Bandit adds no meaningful new findings beyond expected test-file `assert` notices.
**Tests:** The three reported failing nodes plus any immediately adjacent MCP tests touched during debugging.
**Status:** Complete

- [x] Re-run all originally failing MCP tests together
- [x] Re-run nearby MCP tests covering the touched behavior
- [x] Run `python -m bandit` on touched production files from the project venv
