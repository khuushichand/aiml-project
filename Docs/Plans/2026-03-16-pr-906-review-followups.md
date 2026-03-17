## Stage 1: Review Validation
**Goal**: Verify each new PR review comment against the current implementation and separate actionable fixes from non-actionable feedback.
**Success Criteria**: Security/correctness items are confirmed with code references; maintainability suggestions are either accepted with small-scope fixes or explicitly rejected with rationale.
**Tests**: N/A
**Status**: Complete

## Stage 2: Targeted Fixes
**Goal**: Implement the accepted review fixes without widening scope.
**Success Criteria**: OIDC verification no longer trusts token header `alg`, federation callback is rate-limited, managed secret readiness respects ref lifecycle state and avoids repeated per-slot lookups, federation endpoint helpers are centralized, and admin IdP endpoints gain required annotations/docstrings.
**Tests**: Targeted `pytest` for AuthNZ federation, admin identity provider API, MCP Hub slot status, and external access resolver coverage.
**Status**: Complete

## Stage 3: Verification And PR Follow-Up
**Goal**: Verify the touched scope and update the PR threads with concrete dispositions.
**Success Criteria**: Targeted tests and Bandit pass on the changed files; the branch is ready to push; each open review thread has either a code fix or a technical reply.
**Tests**: `pytest` on touched suites, `bandit` on touched Python files.
**Status**: In Progress
