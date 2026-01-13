# Admin Invite Codes (Registration Codes) PRD

## Summary
Admins need a controlled, auditable way to invite new users. The system already supports registration codes and admin endpoints; this PRD defines the UX, API contract, permissions, and expected behavior to make invite codes a first-class admin workflow. Organization invites remain a separate system managed via org invite endpoints.

## Goals
- Allow admins to create, manage, and revoke invite codes without direct user creation.
- Provide a consistent experience for distributing codes and tracking usage.
- Keep registration gated behind admin control when required by policy.
- Allow org-scoped invites that add users to an org automatically on signup or acceptance.

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
- Org-scoped extension (admin only):
  - org_id input (admin-provided).
  - org_role selector (owner|admin|lead|member).
  - optional team_id input when teams exist.
- Provide a "copy acceptance link" when org-scoped invites can be accepted by existing users.
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
- Org-scoped invite behavior:
  - registration auto-assigns org membership and org role; no org selection UI.
  - if the user already exists, use `/api/v1/orgs/invites/accept` to add membership without re-registering.
- Domain allowlist behavior:
  - if a code specifies `allowed_email_domain`, only emails in that domain may redeem it.
  - applies to registration codes and org invites.

### Permissions and Scoping
- Default: only admins can create/list/delete invite codes.
- Org invites are a separate system:
  - org admins manage org invites via `/api/v1/orgs/{org_id}/invites`.
  - preview (unauthenticated) via `/api/v1/invites/preview`.
  - acceptance (authenticated) via `/api/v1/invites/redeem`.
  - admin registration codes can include org fields, but creation/listing remains admin-only.
- Org-scoped registration codes require `enable_org_scoped_registration_codes=true`.

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

Optional extension for org-scoped invites:
- org_id (or metadata.org_id)
- org_role (or metadata.org_role)
- team_id (or metadata.team_id)

Org invites (separate system) should store:
- allowed_email_domain (optional)

## UX Details
- "Copy invite link" uses the configured Web UI base URL plus `/webui/auth.html?code=XXXX`.
- "Copy acceptance link" uses `/webui/accept-invite.html?code=XXXX` when accepting into an existing account.
- "Copy redeem link" for org invites uses `/webui/redeem-invite.html?code=XXXX`.
- Web UI base URL is configurable via `Server.webui_base_url` or `TLDW_WEBUI_BASE_URL`.
- If registration is disabled, the UI shows a warning and disables code creation.
- Revoke action is destructive and requires confirmation.
- List defaults to active codes; expired/inactive are dimmed if shown.
- Org-scoped invites display the org name and role in the list and detail view.

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
- Org-scoped registration codes are gated behind a config flag (`enable_org_scoped_registration_codes`).
- Invite codes support email domain allowlists (`allowed_email_domain`).
- Code redemption auto-assigns org/team membership when org-scoped fields are present.
