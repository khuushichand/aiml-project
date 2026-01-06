# Auth + Registration Consolidation PRD

## Summary
Consolidate authentication endpoints into a single router and make the AuthNZ
DB pool RegistrationService the only registration path. Remove duplicate auth
modules and the unused registration_service_updated implementation to reduce
maintenance overhead and behavioral drift.

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
Auth endpoints live in separate modules (auth.py and auth_enhanced.py) with
overlapping paths and shared dependencies. Registration has two service
implementations with the same class name, only one of which is wired in. This
creates drift risk, test complexity, and confusion over the authoritative path.

## Scope
- Merge auth_enhanced endpoints into auth.py (or a single shared module).
- Remove auth_enhanced router inclusion from app startup.
- Remove registration_service_updated.py and any dead wiring.
- Update dependencies and tests to use the single RegistrationService.

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

## Observability
- Maintain existing audit logging and metrics.
- Add a startup log confirming auth router is consolidated.

## Testing
- Unit tests for auth flows (login, refresh, logout, register).
- Integration tests for MFA and password reset.
- 429 behavior tests via RG policies on auth endpoints.

## Rollout
- Stage 1: Move endpoints and validate behavior in tests.
- Stage 2: Remove old module and update docs/imports.

## Risks
- Test fixtures that import auth_enhanced directly.
- Subtle differences in error handling between modules.

## Open Questions
- Should any legacy module be retained as a re-export for external code?
