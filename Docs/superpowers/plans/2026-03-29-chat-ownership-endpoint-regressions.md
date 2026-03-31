# Chat Ownership Endpoint Regressions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the AuthNZ chat ownership behavior for chat-linked research runs and chat settings endpoints.

**Architecture:** Treat the three failures as one ownership-ordering regression until proven otherwise. Reproduce the failing nodes, trace chat lookup and deep-research attachment validation across the endpoint and service layers, then apply the smallest fix so ownership checks happen before attachment/run validation leaks through with the wrong error contract.

**Tech Stack:** FastAPI, pytest, AuthNZ multi-user integration tests, chat endpoints, research service, chat settings validation

---

## Stage 1: Reproduce And Trace
**Goal:** Confirm the exact failure paths and identify where the wrong error is produced.
**Success Criteria:** Each failing node is reproduced and mapped to the endpoint/helper responsible for the wrong status/detail.
**Tests:** The three reported pytest node IDs.
**Status:** In Progress

- [ ] Run the three failing tests directly
- [ ] Inspect the chat research runs endpoint implementation
- [ ] Inspect the chat settings endpoint and deep research attachment validator
- [ ] Compare the failing path to nearby passing ownership checks

## Stage 2: Apply Minimal Fix
**Goal:** Restore the intended ownership/error-ordering behavior with the smallest code change.
**Success Criteria:** Non-owners receive the expected ownership response and owner writes still accept valid attachment payloads.
**Tests:** Re-run the failing node after each change.
**Status:** Not Started

- [ ] Use the existing failing tests as the red state
- [ ] Patch the ownership or validation order in the responsible endpoint/helper
- [ ] Keep the fix scoped to the identified root cause

## Stage 3: Verify And Close
**Goal:** Prove the ownership regression is fixed without introducing new issues.
**Success Criteria:** The reported failing subset passes and Bandit adds no meaningful new findings in touched code.
**Tests:** The three reported tests plus nearby ownership tests touched during debugging.
**Status:** Not Started

- [ ] Re-run all originally failing tests together
- [ ] Re-run adjacent chat ownership tests if the touched code has nearby coverage
- [ ] Run `python -m bandit` on touched files from the project venv
