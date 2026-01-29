# Admin Invite Codes (Registration Codes) PRD

## Summary
Admins need a controlled, auditable way to invite new users. The system already supports registration codes and admin endpoints; this PRD defines the UX, API contract, permissions, and expected behavior to make invite codes a first-class admin workflow. Organization invites remain a separate system managed via org invite endpoints.

## Goals
- Allow admins to create, manage, and revoke invite codes without direct user creation.
- Provide a consistent experience for distributing codes and tracking usage.
- Keep registration gated behind admin control when required by policy.
- Allow org-scoped registration codes that add users to an org automatically on signup or acceptance.

## Non-Goals
- Full email invitation delivery pipeline.
- SSO/SAML provisioning flows.
- Automated org/team provisioning beyond what is explicitly defined in the invite.

## Users and Use Cases
- Platform admin: create invite codes for new users, assign default roles, monitor usage.
- Org admin: create org invite codes for their org via org invite endpoints.
- Invited user: sign up or accept an invite and land in the correct org automatically.
- Security reviewer: audit who created an invite and how it was used.

## User Stories
- As an admin, I can create a code with an expiry and maximum uses.
- As an admin, I can set the role granted on registration.
- As an admin, I can copy a registration link containing the code.
- As an admin, I can revoke a code and see its usage count.
- As a reviewer, I can see who created each code and when it was used.
- As an org admin, I can generate an org invite that automatically assigns membership.
- As an admin, I can restrict a code to a specific email domain.
- As an org admin, I can share a redeem link for an org invite.

## Functional Requirements
### Admin UI
- Add an Invite Codes panel in the Users section (not only the dashboard).
- List active codes by default, with a toggle to include expired/inactive codes.
- Display: code, created_at, expires_at, max_uses, times_used, role_to_grant, created_by, status.
- Actions: copy code, copy registration link, revoke/delete code.
- Create modal with fields:
  - max_uses (1-100)
  - expiry_days (1-365)
  - role_to_grant (user|admin|service)
  - allowed_email_domain (optional)
  - optional metadata (advanced JSON field, hidden by default)
- Org-scoped registration code extension (admin only):
  - org_id input (admin-provided).
  - org_role selector (owner|admin|lead|member).
  - optional team_id input when teams exist.
- Provide a "copy acceptance link" when org-scoped registration codes can be accepted by existing users.
- Surface registration settings:
  - enable_registration
  - require_registration_code
  - profile gating (self-registration blocked in single_user profile)
- Org Invites panel (admin UI):
  - create org invite codes with org_id, team_id (optional), role, max_uses, expiry_days, description.
  - set allowed_email_domain for org invites.
  - list invites with a toggle to include expired/inactive entries.
  - actions: copy code, copy redeem link, revoke invite.

### Registration Flow
- Register endpoint accepts `registration_code` in the request body (`/api/v1/auth/register`).
- When registration requires codes, the API rejects registrations without a valid code.
- When a valid code is used, usage count increments and is recorded in audit logs.
- Org-scoped registration code behavior:
  - registration auto-assigns org membership and org role; no org selection UI.
  - if the user already exists, use `/api/v1/orgs/invites/accept` to add membership without re-registering.
- Domain allowlist behavior:
  - `allowed_email_domain` is a single domain string compared case-insensitively with exact-match only.
    - No subdomains, no wildcards, no multiple domains per code.
  - Creation enforces basic domain format only; full validation happens at redemption time.
  - If a code specifies `allowed_email_domain`, only emails in that exact domain may redeem it.
  - Applies to registration codes and org invites.

### Permissions and Scoping
- Admin registration codes and org invites are separate systems with explicit overlap:
  - Admin registration codes are created/listed/deleted only by admins via `/api/v1/admin/registration-codes`.
    - Org fields (`org_id`, `org_role`, `team_id`) are allowed only when `enable_org_scoped_registration_codes=true`.
    - Redemption paths: `/api/v1/auth/register` (new user) or `/api/v1/orgs/invites/accept` (existing user).
  - Org invites are created/listed/deleted by org admins/owners via `/api/v1/orgs/{org_id}/invites`.
    - Preview is public via `/api/v1/invites/preview`; redemption is authenticated via `/api/v1/invites/redeem`.
    - Org invite endpoints do not manage admin registration codes.

Examples (org invites):
```
POST /api/v1/orgs/42/invites
{ "team_id": 7, "role_to_grant": "member", "max_uses": 10, "expiry_days": 30 }

GET /api/v1/invites/preview?code=ABCD1234

POST /api/v1/invites/redeem
{ "code": "ABCD1234" }
```

## API Contract (Existing Endpoints)
### Admin
- GET `/api/v1/admin/registration-settings`
  - Response: `{ enable_registration, require_registration_code, auth_mode, profile, self_registration_allowed }`
- POST `/api/v1/admin/registration-settings`
  - Body: `{ enable_registration?: bool, require_registration_code?: bool }`
- POST `/api/v1/admin/registration-codes`
  - Body: `{ max_uses, expiry_days, role_to_grant, allowed_email_domain?, metadata? }`
  - Response: `{ id, code, max_uses, times_used, expires_at, created_at, role_to_grant }`
- GET `/api/v1/admin/registration-codes?include_expired=bool`
  - Response: `{ codes: [...] }`
- DELETE `/api/v1/admin/registration-codes/{code_id}`
  - Response: `{ message }`

### Registration
- POST `/api/v1/auth/register`
  - Body includes: `{ username, email, password, registration_code? }`

### Invite Acceptance (Existing User - Admin Org-Scoped Codes)
- POST `/api/v1/orgs/invites/accept`
  - Body: `{ code }`
  - Requires authenticated user; adds org membership and role defined by the registration code.

## API Contract (Org Invites - Separate System)
### Org Admin
- POST `/api/v1/orgs/{org_id}/invites`
  - Body: `{ team_id?, role_to_grant?, max_uses, expiry_days, description?, allowed_email_domain? }`
  - Response: `{ id, code, max_uses, uses_count, expires_at, created_at, role_to_grant, org_id, team_id, allowed_email_domain }`
- GET `/api/v1/orgs/{org_id}/invites`
  - Response: `{ items: [...], total }`
- DELETE `/api/v1/orgs/{org_id}/invites/{invite_id}`
  - Response: 204

### Invite Preview + Acceptance (Existing User)
- GET `/api/v1/invites/preview?code=...`
  - Response: `{ org_name, team_name, role_to_grant, is_valid, status, expires_at, allowed_email_domain }`
  - Privacy: `allowed_email_domain` is intentionally returned in the unauthenticated preview response so invitees can confirm domain requirements.
- POST `/api/v1/invites/redeem`
  - Body: `{ code }`
  - Requires authenticated user; adds org membership and role defined by the invite.

## Data Model
Core fields needed in registration_codes (already present or implied):
- code (unique)
- created_by (admin user id)
- created_at
- expires_at
- max_uses
- times_used (usage count)
- role_to_grant
- is_active
- allowed_email_domain
- metadata (JSON, optional)

Optional extension for org-scoped registration codes (admin-only):
- org_id (or metadata.org_id)
- org_role (or metadata.org_role)
- team_id (or metadata.team_id)

Org invites (separate system) should store:
- allowed_email_domain (optional)

## UX Details
- "Copy invite link" uses the configured Web UI base URL plus the Next.js login/registration flow with `?code=XXXX`.
- "Copy acceptance link" targets the Next.js WebUI invite acceptance flow.
- "Copy redeem link" for org invites targets the Next.js WebUI invite redemption flow.
- Web UI base URL is configurable via deployment settings (for example, `QUICKSTART_URL` or the frontend's public base URL).
- If registration is disabled, the UI shows a warning and disables code creation.
- Revoke action is destructive and requires confirmation.
- List defaults to active codes; expired/inactive are dimmed if shown.
- Org-scoped registration codes display the org name and role in the list and detail view.

## Configuration
Feature flags referenced by this PRD:
- `enable_org_scoped_registration_codes` (default: false)
  - Toggles admin registration codes with org fields (`org_id`, `org_role`, `team_id`) and enables `/api/v1/orgs/invites/accept` to consume those codes for existing users.
  - Does not control org invites; org invite endpoints (`/api/v1/orgs/{org_id}/invites`, `/api/v1/invites/preview`, `/api/v1/invites/redeem`) remain available based on RBAC alone.
  - Security impact: allows admin codes to auto-assign org/team membership. Keep disabled unless admins explicitly need org-scoped admin codes; ensure audit logs capture org fields and redemption actions.
- `org_invite_allow_missing_email` (default: false)
  - Controls org invite redemption when `allowed_email_domain` is set but the user email is missing.
  - When false, redemption is blocked if a domain-restricted invite cannot validate an email address.
  - When true, redemption may proceed without an email only for org invites (not admin registration codes), effectively bypassing the domain check.
  - Security impact: can weaken domain-based access control. Mitigations: keep disabled by default, require email capture before redeem, and monitor audit logs for missing-email redemptions.

Feature matrix (flags -> behavior):

| enable_org_scoped_registration_codes | org_invite_allow_missing_email | Admin registration codes org fields | Org invites redeem with missing email + allowed_email_domain |
| --- | --- | --- | --- |
| false | false | blocked | blocked |
| false | true | blocked | allowed (org invites only) |
| true | false | allowed | blocked |
| true | true | allowed | allowed (org invites only) |

Recommended safe defaults: both flags false.
Telemetry/logging: emit audit logs for invite/code create/revoke/redeem; log domain allowlist failures and missing-email bypasses with request_id and code id for troubleshooting.

## Audit and Observability
- Create/revoke actions must produce audit log entries.
- Code redemption logs the user id and code id.
- Org invite create/revoke/redeem actions are recorded in audit logs.

## Edge Cases
- Code reaches max uses: treated as invalid.
- Code expires: treated as invalid.
- Code domain allowlist mismatch: treated as invalid.
- Registration disabled: no codes usable.
- Profile blocks self-registration: warn and disable code creation.
- Existing user attempts to register with an org invite: return a clear error with an accept-invite path.
- Org invite allowlist with missing user email: block redemption unless `org_invite_allow_missing_email` is enabled.

## Decisions
- Breaking change: registration moved from `/api/v1/register` to `/api/v1/auth/register`.
  - Migration: update client POSTs to `/api/v1/auth/register` with the same body shape (`{ username, email, password, registration_code? }`); responses remain the same `RegistrationResponse` payload (only the path changed).
  - Deprecation timeline: `/api/v1/register` deprecated in v0.1.0, removed in v0.2.0; no redirect/shim or backward compatibility is provided (expect 404 on the old path).
- Org-scoped registration codes are gated behind a config flag (`enable_org_scoped_registration_codes`).
- Invite codes support email domain allowlists (`allowed_email_domain`).
- Code redemption auto-assigns org/team membership when org-scoped fields are present.
