# Admin UI Enterprise Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the blocker and major-gap set that prevents `admin-ui` from safely managing live customer accounts in an enterprise-sensitive production environment.

**Architecture:** Treat the admin UI as a privileged control plane. Fix authentication parity first, then move privileged actions behind stronger controls and durable audit instrumentation, then clean up contract mismatches and workflow safety gaps.

**Tech Stack:** Next.js 15, React 19, TypeScript, FastAPI, Pydantic, AuthNZ services, Vitest, pytest

---

### Task 1: Add MFA-Challenge Login Support

**Files:**
- Modify: `admin-ui/lib/auth.ts`
- Modify: `admin-ui/app/login/page.tsx`
- Test: `admin-ui/lib/auth.test.ts`
- Test: `admin-ui/app/login/__tests__/page.test.tsx` or the nearest existing login test file
- Reference: `tldw_Server_API/app/api/v1/endpoints/auth.py`

**Step 1: Write the failing tests**

- Add a frontend auth test that mocks `/auth/login` returning:
  ```json
  {
    "session_token": "mfa-session-token",
    "mfa_required": true,
    "expires_in": 300,
    "message": "MFA required. Submit your TOTP or backup code."
  }
  ```
- Assert the UI does not store `access_token` and instead enters an MFA challenge state.
- Add a UI test for submitting TOTP/backup code to `/auth/mfa/login`.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run admin-ui/lib/auth.test.ts admin-ui/app/login/__tests__/page.test.tsx`

Expected: FAIL because the current login flow assumes `access_token` exists on every successful response.

**Step 3: Write minimal implementation**

- Introduce a discriminated login result type in `admin-ui/lib/auth.ts`.
- Handle both:
  - completed login with `access_token`
  - MFA challenge with `session_token`
- Add an MFA challenge step in `admin-ui/app/login/page.tsx`.
- Submit the challenge to `/auth/mfa/login` and only persist auth after that response returns an access token.

**Step 4: Run tests to verify they pass**

Run: `bunx vitest run admin-ui/lib/auth.test.ts admin-ui/app/login/__tests__/page.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/lib/auth.ts admin-ui/app/login/page.tsx admin-ui/lib/auth.test.ts admin-ui/app/login/__tests__/page.test.tsx
git commit -m "feat(admin-ui): support MFA challenge login"
```

### Task 2: Replace Browser-Stored Admin Bearer Tokens

**Files:**
- Modify: `admin-ui/lib/auth.ts`
- Modify: `admin-ui/lib/http.ts`
- Modify: `admin-ui/middleware.ts`
- Modify: `admin-ui/README.md`
- Test: `admin-ui/lib/auth.test.ts`
- Test: `admin-ui/lib/http.test.ts` or add one if absent
- Reference: `tldw_Server_API/app/core/AuthNZ/csrf_protection.py`

**Step 1: Write the failing tests**

- Add tests asserting admin auth is not persisted in `localStorage`.
- Add request tests verifying privileged requests use the new session model.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run admin-ui/lib/auth.test.ts admin-ui/lib/http.test.ts`

Expected: FAIL because the current implementation reads/writes `access_token` in `localStorage`.

**Step 3: Write minimal implementation**

- Move privileged session state to secure cookie-backed auth or a server-mediated session strategy.
- Remove `localStorage` storage for `access_token`.
- Update request helpers and logout handling accordingly.
- Update docs to remove `localStorage`-based JWT guidance.

**Step 4: Run tests to verify they pass**

Run: `bunx vitest run admin-ui/lib/auth.test.ts admin-ui/lib/http.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/lib/auth.ts admin-ui/lib/http.ts admin-ui/middleware.ts admin-ui/README.md admin-ui/lib/auth.test.ts admin-ui/lib/http.test.ts
git commit -m "feat(admin-ui): harden privileged session storage"
```

### Task 3: Remove Human API-Key Login for Enterprise Admin Use

**Files:**
- Modify: `admin-ui/app/login/page.tsx`
- Modify: `admin-ui/README.md`
- Modify: `admin-ui/.env.example`
- Modify: `tldw_Server_API/app/api/v1/endpoints/auth.py`
- Modify: `tldw_Server_API/app/services/admin_scope_service.py`
- Test: `admin-ui/app/login/__tests__/page.test.tsx`
- Test: `tldw_Server_API/tests/AuthNZ/...` relevant auth tests

**Step 1: Write the failing tests**

- Add a UI test asserting API-key login is hidden or disabled in enterprise mode.
- Add a backend test asserting enterprise deployments reject single-user admin mode for this surface.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run admin-ui/app/login/__tests__/page.test.tsx`

Expected: FAIL because the API key login tab is always rendered.

**Step 3: Write minimal implementation**

- Gate or remove the API-key login tab for enterprise deployments.
- Document that single-user mode is not valid for enterprise-sensitive live-account management.
- Prevent enterprise admin flows from relying on single-user bypass behavior.

**Step 4: Run tests to verify they pass**

Run: `bunx vitest run admin-ui/app/login/__tests__/page.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/login/page.tsx admin-ui/README.md admin-ui/.env.example tldw_Server_API/app/api/v1/endpoints/auth.py tldw_Server_API/app/services/admin_scope_service.py
git commit -m "feat(auth): disable API-key admin login for enterprise mode"
```

### Task 4: Add Step-Up Auth and Reasons for High-Risk Admin Actions

**Files:**
- Modify: `admin-ui/app/users/page.tsx`
- Modify: `admin-ui/app/users/[id]/page.tsx`
- Modify: `admin-ui/app/api-keys/page.tsx`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_user.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_sessions_mfa.py`
- Modify: `tldw_Server_API/app/services/admin_users_service.py`
- Modify: `tldw_Server_API/app/services/admin_sessions_mfa_service.py`
- Test: matching Vitest page tests
- Test: matching pytest admin endpoint tests

**Step 1: Write the failing tests**

- Add frontend tests that password reset, MFA disable, revoke-all, delete user, and bulk role changes require:
  - reason text
  - a recent-auth or step-up confirmation
- Add backend tests rejecting those actions when recent-auth proof is missing.

**Step 2: Run test to verify it fails**

Run: targeted Vitest and pytest commands for the changed admin flows.

Expected: FAIL because current flows only require ordinary auth plus a confirm dialog.

**Step 3: Write minimal implementation**

- Add a reusable “privileged action confirmation” flow in `admin-ui`.
- Require reason capture in the UI.
- Add backend enforcement for recent-auth / step-up proof on those endpoints.

**Step 4: Run tests to verify they pass**

Run: targeted Vitest and pytest commands, then full admin-ui test suite.

Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/users/page.tsx admin-ui/app/users/[id]/page.tsx admin-ui/app/api-keys/page.tsx tldw_Server_API/app/api/v1/endpoints/admin/admin_user.py tldw_Server_API/app/api/v1/endpoints/admin/admin_sessions_mfa.py tldw_Server_API/app/services/admin_users_service.py tldw_Server_API/app/services/admin_sessions_mfa_service.py
git commit -m "feat(admin): require step-up auth for high-risk actions"
```

### Task 5: Emit Durable Audit Events for High-Risk Admin Actions

**Files:**
- Modify: `tldw_Server_API/app/services/admin_users_service.py`
- Modify: `tldw_Server_API/app/services/admin_sessions_mfa_service.py`
- Modify: any audit dependency wiring required under `tldw_Server_API/app/api/v1/API_Deps/`
- Test: pytest admin endpoint/service tests
- Reference: `tldw_Server_API/app/core/Audit/unified_audit_service.py`

**Step 1: Write the failing tests**

- Add tests asserting unified audit events are written for:
  - password reset
  - user deactivation
  - MFA disable
  - session revoke
  - session revoke-all

**Step 2: Run test to verify it fails**

Run: targeted pytest commands for the affected services/endpoints.

Expected: FAIL because current paths only emit ordinary log messages.

**Step 3: Write minimal implementation**

- Inject audit service access into these paths.
- Emit structured durable events with actor, target user, action type, scope, and operator-supplied reason.

**Step 4: Run tests to verify they pass**

Run: targeted pytest commands.

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_users_service.py tldw_Server_API/app/services/admin_sessions_mfa_service.py tldw_Server_API/app/api/v1/API_Deps
git commit -m "feat(audit): log high-risk admin account actions"
```

### Task 6: Remove Plaintext Temporary Password Reveal and Align Role Contracts

**Files:**
- Modify: `admin-ui/app/users/[id]/page.tsx`
- Modify: `tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Modify: `admin-ui/types` or role helpers if needed
- Test: `admin-ui/app/users/[id]/__tests__/page.test.tsx`
- Test: relevant backend admin schema tests

**Step 1: Write the failing tests**

- Add a UI test asserting password reset no longer renders a plaintext reusable password.
- Add tests asserting role options and backend role schema accept the same vocabulary.

**Step 2: Run test to verify it fails**

Run: targeted Vitest and pytest commands.

Expected: FAIL because the current UI displays `temporary_password` and the role vocabularies differ.

**Step 3: Write minimal implementation**

- Replace plaintext password reveal with a safer recovery or enrollment flow.
- Standardize role names across frontend and backend.

**Step 4: Run tests to verify they pass**

Run: targeted Vitest and pytest commands.

Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/app/users/[id]/page.tsx tldw_Server_API/app/api/v1/schemas/admin_schemas.py
git commit -m "fix(admin): remove plaintext reset password reveal and align roles"
```
