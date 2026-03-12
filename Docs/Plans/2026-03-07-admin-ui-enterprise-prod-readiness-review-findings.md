# 2026-03-07 Admin UI Enterprise Prod Readiness Review Findings

## Verdict

`admin-ui` is **not ready** to manage live customer accounts in an enterprise-sensitive production environment.

The current app is structurally solid as an internal operations dashboard. Lint, unit tests, and production build all pass. That does not change the control-plane conclusion: the privileged identity model, high-risk admin workflows, and audit posture are not yet strong enough for enterprise-sensitive live-account administration.

## Blockers

### 1. MFA-enabled admins cannot complete login in the admin UI

The backend can return an MFA challenge instead of an access token during login, but the UI login flow assumes every successful response contains `access_token`.

- UI evidence:
  - [admin-ui/lib/auth.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/lib/auth.ts#L94) stores `data.access_token` on any `response.ok`.
  - [admin-ui/app/login/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/login/page.tsx#L49) treats any truthy login result as a completed login and redirects immediately.
  - No `admin-ui` code handles `mfa_required`, `session_token`, or `/auth/mfa/login`.
- Backend evidence:
  - [tldw_Server_API/app/api/v1/endpoints/auth.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/auth.py#L1185) checks whether MFA is required.
  - [tldw_Server_API/app/api/v1/endpoints/auth.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/auth.py#L1268) returns `202 Accepted` with `session_token` and `mfa_required=True` instead of an access token.

Impact:
- Enterprise admins with MFA enabled cannot reliably use the admin console.
- The control plane is incompatible with a basic enterprise security requirement.

### 2. Privileged JWT sessions are stored in browser `localStorage`

The UI stores admin bearer tokens in `localStorage` and replays them in `Authorization` headers on each request.

- Evidence:
  - [admin-ui/lib/auth.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/lib/auth.ts#L80) reads the JWT from `localStorage`.
  - [admin-ui/lib/auth.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/lib/auth.ts#L117) writes the JWT to `localStorage`.
  - [admin-ui/lib/http.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/lib/http.ts#L26) builds auth headers from that stored token.
  - [admin-ui/README.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/README.md#L56) documents that JWTs are stored in `localStorage`.

Impact:
- Any XSS or browser compromise yields reusable privileged bearer tokens.
- That session model is below the bar for an enterprise-sensitive admin surface.

### 3. The product still supports API-key-based human admin login and single-user admin bypass

The login screen exposes API key auth for humans, and the backend single-user flow effectively treats the configured global API key as the authenticated admin credential.

- UI evidence:
  - [admin-ui/app/login/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/login/page.tsx#L120) always renders an `API Key` auth tab.
  - [admin-ui/README.md](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/README.md#L56) documents single-user API key login as a supported admin mode.
- Backend evidence:
  - [tldw_Server_API/app/api/v1/endpoints/auth.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/auth.py#L1202) returns the configured single-user API key as the access and refresh token in single-user mode.
  - [tldw_Server_API/app/services/admin_scope_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_scope_service.py#L49) bypasses admin scope checks for single-user principals.

Impact:
- Shared or static “god credentials” undermine operator identity, accountability, and separation of duties.
- This model is not acceptable for enterprise-sensitive live customer administration.

### 4. High-risk admin actions lack step-up auth or dual-control protections

Password resets, MFA disable, session revocation, role changes, and user deletion are executed after ordinary authentication and a single confirmation dialog. I did not find evidence of re-authentication, step-up MFA, recent-auth enforcement, approval workflows, or dual control in these admin paths.

- UI evidence:
  - [admin-ui/app/users/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/page.tsx#L618) bulk-deletes users after a single confirm.
  - [admin-ui/app/users/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/page.tsx#L700) bulk-resets passwords after a single confirm.
  - [admin-ui/app/users/[id]/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/[id]/page.tsx#L692) disables MFA after a single confirm.
  - [admin-ui/app/users/[id]/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/[id]/page.tsx#L753) resets a password after a single confirm.
- Backend evidence:
  - [tldw_Server_API/app/api/v1/endpoints/admin/admin_user.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/admin/admin_user.py#L201) exposes password reset, MFA requirement, and delete-user endpoints with normal auth dependency only.
  - [tldw_Server_API/app/api/v1/endpoints/admin/admin_sessions_mfa.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/admin/admin_sessions_mfa.py#L32) exposes session revoke and MFA disable endpoints with normal auth dependency only.
  - [tldw_Server_API/app/services/admin_users_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_users_service.py#L331) and [admin_sessions_mfa_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_sessions_mfa_service.py#L118) enforce scope/hierarchy but do not show step-up or approval checks.

Impact:
- Stolen or unattended privileged sessions can immediately perform customer-impacting actions.
- Operators can make irreversible mistakes too easily for the target environment.

## Major Gaps

### 5. High-risk account actions do not appear to emit durable audit events

This is an inference from the implementation paths I inspected. I did not find explicit unified-audit writes in the admin password reset, MFA disable, session revoke, or user delete services. Those paths appear to rely on ordinary application logging instead.

- Evidence:
  - [tldw_Server_API/app/services/admin_users_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_users_service.py#L399) logs password reset with `logger.info`.
  - [tldw_Server_API/app/services/admin_users_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_users_service.py#L545) logs user deactivation with `logger.info`.
  - [tldw_Server_API/app/services/admin_sessions_mfa_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_sessions_mfa_service.py#L68) revokes sessions without visible audit emission.
  - [tldw_Server_API/app/services/admin_sessions_mfa_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/admin_sessions_mfa_service.py#L130) disables MFA without visible audit emission.

Why it matters:
- Enterprise incident response needs durable, queryable, customer-scoped evidence for who changed what and when.
- Application logs are not a sufficient substitute for a privileged admin audit trail.

### 6. Password reset returns a new password to the browser and renders it in the UI

The backend response includes a plaintext temporary password and the UI displays it on the page.

- Evidence:
  - [tldw_Server_API/app/api/v1/schemas/admin_schemas.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/schemas/admin_schemas.py#L39) defines `temporary_password` in the admin password reset response.
  - [admin-ui/app/users/[id]/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/[id]/page.tsx#L765) reads `temporary_password` from the response.
  - [admin-ui/app/users/[id]/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/[id]/page.tsx#L1232) renders the new password into the page DOM.

Why it matters:
- New credentials become visible to the browser, extensions, screenshots, and operator workstation history.
- Enterprise admin tooling should prefer controlled recovery or one-time enrollment flows over displaying reusable secrets.

### 7. Role administration is inconsistent between the UI and backend contract

The user detail page offers roles that the backend update schema does not accept.

- UI evidence:
  - [admin-ui/app/users/[id]/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/[id]/page.tsx#L63) offers `member`, `admin`, `super_admin`, and `owner`.
  - [admin-ui/app/users/[id]/page.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/app/users/[id]/page.tsx#L405) normalizes unsupported role values back to `member`.
- Backend evidence:
  - [tldw_Server_API/app/api/v1/schemas/admin_schemas.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/schemas/admin_schemas.py#L18) only accepts `user`, `admin`, or `service` for `UserUpdateRequest.role`.

Why it matters:
- Reliable live-account administration requires a single, coherent privilege model.
- UI/backend role drift creates failed updates, operator confusion, and possible privilege mistakes.

## Hardening Gaps

### 8. Middleware can temporarily accept revoked auth for up to 30 seconds

- Evidence:
  - [admin-ui/middleware.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/middleware.ts#L8) caches auth checks.
  - [admin-ui/middleware.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/middleware.ts#L14) explicitly notes revoked tokens may remain accepted until cache expiry.

Why it matters:
- This is not the biggest problem in the current design, but it weakens revocation responsiveness for a privileged surface.

## What Is Already Healthy

- Current repo automation does gate `admin-ui` changes through lint, unit tests, and build in [frontend-required.yml](/Users/macbook-dev/Documents/GitHub/tldw_server2/.github/workflows/frontend-required.yml#L102).
- Local verification completed successfully on 2026-03-07:
  - `bun run lint`
  - `bun run test`
  - `bun run build`
- The UI has broad automated test coverage and many accessibility-focused tests, which is a good base for hardening work.

## Recommended Readiness Sequence

### Before any live customer-account administration

1. Implement MFA challenge handling and complete admin login parity with backend auth.
2. Replace browser-stored bearer tokens with an admin-safe session model.
3. Remove API-key-based human login from enterprise deployments and formally deprecate single-user admin mode for this use case.
4. Add step-up auth for password reset, MFA disable, session revoke-all, user delete, role changes, and key rotation.
5. Add explicit durable audit events for every high-risk admin action.

### Before wider internal production use

1. Replace plaintext password reveal with a safer recovery flow.
2. Align role vocabulary and enforcement across UI and backend.
3. Tighten middleware/session revocation behavior.

### Before scaled enterprise operations

1. Add operator reason capture and review tooling for high-risk actions.
2. Add approval or dual-control support for especially dangerous workflows.
3. Expand compliance-oriented audit export and customer-support investigation tooling.
