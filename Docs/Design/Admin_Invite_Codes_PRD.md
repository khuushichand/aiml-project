# Admin Invite Codes (Registration Codes) PRD

## Summary
Admins need a controlled, auditable way to invite new users. The system already supports registration codes and admin endpoints; this PRD defines the UX, API contract, permissions, and expected behavior to make invite codes a first-class admin workflow, including optional org-scoped invites that auto-assign membership (no manual org selection).

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
- Org admin: create invite codes for their org if org-scoped invites are enabled.
- Invited user: sign up or accept an invite and land in the correct org automatically.
- Security reviewer: audit who created an invite and how it was used.

## User Stories
- As an admin, I can create a code with an expiry and maximum uses.
- As an admin, I can set the role granted on registration.
- As an admin, I can copy a registration link containing the code.
- As an admin, I can revoke a code and see its usage count.
- As a reviewer, I can see who created each code and when it was used.
- As an org admin, I can generate an org invite that automatically assigns membership.

## Functional Requirements
### Admin UI
- Add an Invite Codes panel in the Users section (not only the dashboard).
- List active codes by default, with a toggle to include expired/inactive codes.
- Display: code, created_at, expires_at, max_uses, times_used, role_to_grant, created_by.
- Actions: copy code, copy registration link, revoke/delete code.
- Create modal with fields:
  - max_uses (1-100)
  - expiry_days (1-365)
  - role_to_grant (user|admin|service)
  - optional metadata (advanced JSON field, hidden by default)
- Org-scoped extension:
  - org selector (defaults to current org when org filter is active).
  - org_role selector (owner|admin|lead|member).
  - optional team_id selector when teams exist.
- Provide a "copy acceptance link" when org-scoped invites can be accepted by existing users.
- Surface registration settings:
  - enable_registration
  - require_registration_code
  - profile gating (self-registration blocked in single_user profile)

### Registration Flow
- Register endpoint accepts `registration_code` in the request body.
- When registration requires codes, the API rejects registrations without a valid code.
- When a valid code is used, usage count increments and is recorded in audit logs.
- Org-scoped invite behavior:
  - registration auto-assigns org membership and org role; no org selection UI.
  - if the user already exists, use a dedicated accept-invite flow to add membership without re-registering.

### Permissions and Scoping
- Default: only admins can create/list/delete invite codes.
- Optional org-scoped mode (future):
  - invite code includes org_id in metadata (or a new column).
  - redemption auto-assigns org membership and role.
  - org admins can only manage codes for their org.

## API Contract (Existing Endpoints)
### Admin
- GET `/api/v1/admin/registration-settings`
  - Response: `{ enable_registration, require_registration_code, auth_mode, profile, self_registration_allowed }`
- POST `/api/v1/admin/registration-settings`
  - Body: `{ enable_registration?: bool, require_registration_code?: bool }`
- POST `/api/v1/admin/registration-codes`
  - Body: `{ max_uses, expiry_days, role_to_grant, metadata? }`
  - Response: `{ id, code, max_uses, times_used, expires_at, created_at, role_to_grant }`
- GET `/api/v1/admin/registration-codes?include_expired=bool`
  - Response: `{ codes: [...] }`
- DELETE `/api/v1/admin/registration-codes/{code_id}`
  - Response: `{ message }`

### Registration
- POST `/api/v1/register`
  - Body includes: `{ username, email, password, confirm_password, registration_code? }`

## API Contract (Org-Scoped Extensions)
### Admin
- POST `/api/v1/admin/registration-codes`
  - Body add-ons: `{ org_id?, org_role?, team_id? }` (or `metadata.org_id/org_role/team_id`).
  - Response includes `metadata` or explicit org fields if supported.

### Invite Acceptance (Existing User)
- POST `/api/v1/orgs/invites/accept`
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
- metadata (JSON, optional)

Optional extension for org-scoped invites:
- org_id (or metadata.org_id)
- org_role (or metadata.org_role)
- team_id (or metadata.team_id)

## UX Details
- "Copy invite link" uses the configured Web UI base URL plus `/register?code=XXXX`.
- "Copy acceptance link" uses `/accept-invite?code=XXXX` when accepting into an existing account.
- If registration is disabled, the UI shows a warning and disables code creation.
- Revoke action is destructive and requires confirmation.
- List defaults to active codes; expired/inactive are dimmed if shown.
- Org-scoped invites display the org name and role in the list and detail view.

## Audit and Observability
- Create/revoke actions must produce audit log entries.
- Code redemption logs the user id and code id.

## Edge Cases
- Code reaches max uses: treated as invalid.
- Code expires: treated as invalid.
- Registration disabled: no codes usable.
- Profile blocks self-registration: warn and disable code creation.
- Existing user attempts to register with an org invite: return a clear error with an accept-invite path.

## Open Questions
- Should org-scoped invites be enabled by default or behind a config flag?
- Should invite codes support email domain allowlists?
- Should code redemption auto-assign org/team membership in the first release?
- Should accept-invite be a separate endpoint or reuse registration with a different payload?
