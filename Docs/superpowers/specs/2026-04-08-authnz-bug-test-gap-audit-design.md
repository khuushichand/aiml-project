# AuthNZ Bug And Test-Gap Audit Design

## Overview

This review will audit the AuthNZ subsystem in `tldw_server` for bugs, unsafe edge cases, and missing or weak tests. The goal is not a broad style review. The goal is a prioritized findings report that identifies concrete correctness and security risks, then maps those risks to the test coverage that should exist.

## Goals

- Produce a prioritized set of findings focused on real bugs, regressions, and unsafe behavior.
- Include missing-test and weak-test findings when they materially increase regression risk.
- Cover the runtime path from request authentication through authorization and stateful session/key handling.
- Keep findings grounded in exact code references and current project behavior.

## Non-Goals

- No broad refactor proposal unless it directly addresses a bug pattern or persistent test gap.
- No style-only review.
- No review of unrelated modules outside AuthNZ and its directly related auth/admin entry points.

## Audit Scope

The audit covers:

- `tldw_Server_API/app/core/AuthNZ/`
- `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`
- Related auth and admin API endpoints that depend on AuthNZ enforcement paths
- AuthNZ integration, unit, and property tests that exercise those paths

The audit will treat the following areas as highest-risk surfaces:

- Single-user vs multi-user auth branching
- JWT parsing, validation, refresh, and revocation
- Session lifecycle and blacklist behavior
- API key validation, rotation, and scope enforcement
- Admin and privileged endpoint protection
- RBAC and permission resolution
- Lockout, rate limit, quota, and governor interactions
- Test mode and environment guardrails

## Review Method

The review will use a risk-driven method with a test-gap overlay.

### Pass 1: Trust Boundary Review

Inspect the request entry points where principals are resolved and privileged routes are gated. Focus on authentication precedence, token/key parsing, mode-specific behavior, and any branches that could bypass intended checks.

### Pass 2: Stateful Flow Review

Trace flows that depend on mutable state:

- login
- refresh rotation
- session validation and revocation
- token blacklist usage
- API key lifecycle
- lockout and rate-limit state transitions

The purpose of this pass is to catch correctness bugs that emerge only when state changes across requests.

### Pass 3: Authorization Review

Inspect how permissions are derived, propagated, and enforced across auth/admin endpoints. Focus on privilege escalation risks, incorrect default behavior, inconsistent permission checks, and org/team/admin edge cases.

### Pass 4: Test-Gap Review

Compare the high-risk behaviors from the first three passes against current AuthNZ tests. Flag:

- behavior with no direct test coverage
- tests that assert happy paths but not failure paths
- tests that mock away the exact logic that should be verified
- coverage that exists at unit level but not at integration boundaries

## Prioritization Model

Findings will be ranked by operational impact:

- High: auth bypass, privilege escalation, revocation failure, broken admin enforcement, unsafe test-mode or environment behavior
- Medium: correctness bugs that deny valid access, break refresh or lockout flows, or create inconsistent authorization outcomes
- Low: missing tests, brittle abstractions, duplicate enforcement paths, or maintainability issues likely to cause future regressions

## Finding Format

Each finding should include:

- title
- severity
- affected file and exact line reference
- concrete failure mode
- reason the behavior is risky or incorrect
- current test coverage status
- specific test that should be added or strengthened

## Evidence Standards

- Prefer direct code-path evidence over inference.
- Use tests to confirm intended behavior when the implementation alone is ambiguous.
- Treat inconsistencies between endpoint wiring, dependency logic, and test assumptions as findings when they could hide real regressions.
- Keep the final output focused on findings first. Any summary should be secondary.

## Deliverable

The resulting review should be a concise, prioritized audit report with:

1. Findings ordered by severity
2. Open questions or assumptions that affected confidence
3. Brief residual-risk notes where coverage or runtime verification remains incomplete

## Success Criteria

This audit is successful if it:

- identifies real, code-backed AuthNZ risks instead of generic advice
- distinguishes bugs from lower-signal cleanup suggestions
- maps important gaps in tests to the behaviors they fail to protect
- gives the maintainer a clear order of operations for follow-up fixes
