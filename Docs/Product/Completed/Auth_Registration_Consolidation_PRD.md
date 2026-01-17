# Auth + Registration Consolidation PRD

Status: Draft (planning; not yet implemented)
Target milestone: v0.1.x (AuthNZ consolidation release)
PR scope note: Included with the README/feedback doc updates to capture the
planned consolidation work and align follow-on implementation; no runtime
changes ship as part of this document update.

## Summary
Consolidate authentication endpoints into a single router and make the AuthNZ
DB pool RegistrationService the only registration path. Remove duplicate auth
modules and the unused legacy registration service implementation to reduce
maintenance overhead and behavioral drift.

## Implementation Plan
- Staged execution and tests are tracked in
  `Docs/Product/Completed/AuthNZ-Refactor/AuthNZ-PRDs_IMPLEMENTATION_PLAN.md`.

## Goals
- One auth router module for all /auth endpoints.
- Single registration implementation based on AuthNZ DB pool.
- Consistent dependency injection and RG-based rate limiting.
- Simplify router inclusion in main app startup.

## Non-Goals
- Adding new auth features or auth providers.
- Changing auth modes (single-user vs multi-user) semantics.
- Major schema migrations beyond consolidation needs.

## Background / Problem
Auth endpoints previously lived in separate modules (auth.py plus a legacy enhanced router) with
overlapping paths and shared dependencies. Registration has two service
implementations with the same class name, only one of which is wired in. This
creates drift risk, test complexity, and confusion over the authoritative path.

## Scope
- Ensure password reset, email verification, and MFA endpoints live in auth.py.
- Ensure only the auth router is included at app startup.
- Remove unused legacy registration service wiring.
- Update dependencies and tests to use the single RegistrationService.
- Provide auth-scoped session endpoints with `/users/sessions` compatibility wrappers.

## Functional Requirements
1. Endpoint coverage (single router):
   - login, logout, refresh, register, me, sessions
   - password reset
   - email verification
   - MFA setup/verify/login

2. Behavior parity:
   - Preserve request/response schemas and status codes.
   - Keep MFA gating (multi_user + Postgres) unchanged.
   - Preserve existing audit and metrics hooks.
   - Return HTTP 202 + MFA challenge payload when MFA is required during login.

3. Rate limiting:
   - Enforce RG-based auth limits via a dedicated auth policy.

4. DI and services:
   - Use AuthNZ DB pool RegistrationService.
   - Ensure password/jwt/session services remain injected via API deps.

## Migration / Compatibility
- Keep route paths unchanged.
- If needed, leave a lightweight compatibility module that re-exports the
  consolidated router for external imports.
- Update tests to target the consolidated module only.
- Maintain `/users/sessions*` as compatibility wrappers for `/auth/sessions*`.

## Observability
- Maintain existing audit logging and metrics.
- Add a startup log confirming auth router is consolidated.

## Testing
- Unit tests for auth flows (login, refresh, logout, register).
- Integration tests for MFA and password reset.
- 429 behavior tests via RG policies on auth endpoints.

## Rollout
- Target milestone: v0.1.x (AuthNZ consolidation release).
- Stage 1: Move endpoints and validate behavior in tests.
- Stage 2: Remove old module and update docs/imports.

## Risks
- Test fixtures that import legacy auth modules directly.
- Subtle differences in error handling between modules.

## Decisions
- Keep a lightweight re-export module for external imports through v0.1.x and
  remove it in the next minor/major release after the deprecation window
  (breaking change for external imports).
