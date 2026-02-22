# Organization Membership APIs (v1)

Status: Deployed
Owner: AuthNZ Maintainers
Audience: Core backend contributors, admin tooling owners

## 1. Summary
Organization membership APIs provide admin endpoints to add, list, update, and remove users at the organization level. They complement existing team membership APIs and align SQLite/Postgres behavior through shared service helpers. v1 shipped with idempotent member adds, pagination, role updates, audit logging hooks, and a per-user membership lookup.

## 2. Problem Statement
Teams already exposed CRUD APIs, but organizations lacked equivalent membership management. The schema (`org_members`) existed, yet callers could not programmatically add or inspect org-level membership, forcing manual DB manipulation or ad-hoc tools. Delivering a consistent API surface is needed for admin consoles, privilege maps, and org-scoped rate limits.

## 3. Goals & Non-Goals
### Goals
1. Mirror team membership capabilities at the org level (add/list/update/remove).
2. Keep operations idempotent and consistent across SQLite/Postgres.
3. Provide pagination and filtering (role/status) for large organizations.
4. Emit audit events for membership changes.
5. Offer a reverse lookup endpoint to list org memberships for a user.

### Non-Goals
- Automatic propagation to team memberships (default-team auto-join scheduled as a follow-up, not part of v1 delivery).
- Invitation workflows, email notifications, or RBAC inheritance beyond basic roles.
- Advanced roles beyond `owner|admin|member`.
- Cross-organization migration utilities.

## 4. Data Model
`org_members (org_id, user_id, role, status, added_at)`
- Primary key: `(org_id, user_id)`
- Role defaults to `member`, status defaults to `active`
- Indexed by `user_id`
- Created via migration `016_create_orgs_teams` (SQLite) and `initialize.ensure_basic_schema` (Postgres)

## 5. API Surface
All endpoints live under the Admin router and require admin privileges.

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/admin/orgs/{org_id}/members` | Idempotently add a user with optional role (default `member`). Returns existing row on duplicate. |
| `GET /api/v1/admin/orgs/{org_id}/members` | Paginated list (`limit`, `offset`) with optional `role`/`status` filters. |
| `PATCH /api/v1/admin/orgs/{org_id}/members/{user_id}` | Update role (owner/admin/member). 404 if membership missing. |
| `DELETE /api/v1/admin/orgs/{org_id}/members/{user_id}` | Remove membership; returns status message (no error if already absent). |
| `GET /api/v1/admin/users/{user_id}/org-memberships` | Reverse lookup: list `{ org_id, role }` for the user. |

## 6. Services & Schemas
- Service helpers in `app/core/AuthNZ/orgs_teams.py` (`add_org_member`, `list_org_members`, `remove_org_member`, `update_org_member_role`, `list_org_memberships_for_user`) handle both SQLite and Postgres via `get_db_pool`.
- Pydantic models in `app/api/v1/schemas/org_team_schemas.py` define request/response validation (`OrgMemberAddRequest`, `OrgMemberResponse`, `OrgMemberRoleUpdateRequest`, `OrgMemberListItem`, `OrgMembershipItem`).

## 7. Audit Logging
- Add, remove, and role update actions emit best-effort events through Unified Audit Service (`AuditEventCategory.AUTHORIZATION`).
- Metadata includes target user ID and role deltas.
- Failures in audit logging do not block API responses; errors are logged at debug level.

## 8. Error Handling
- Missing org/user references surface as 404 when foreign key checks fail.
- Duplicate adds return the existing membership (HTTP 200) instead of 409.
- DELETE on non-existent membership returns `{ "message": "No membership found", ... }`.
- PATCH on non-existent membership yields HTTP 404.

## 9. Testing
- SQLite + Postgres integration suites (`tests/AuthNZ_SQLite/test_admin_org_members_sqlite.py`, `tests/AuthNZ_Postgres/test_admin_org_members_pg.py`) cover lifecycle operations, idempotency, pagination, and audit hooks.
- Negative cases ensure duplicate adds are idempotent and deletes of missing memberships succeed with a friendly message.

## 10. Rollout Notes
- Feature shipped alongside privilege map updates and MCP catalog management (which rely on `list_org_members`).
- No backward incompatibilities; team membership APIs continue unaffected.
- Future enhancements include enforcing a per-org `Default-Base` team auto-enrollment, owner-count validation, and richer status handling when use cases solidify.

## 11. Decisions & Follow-Ups
1. **Default team auto-enrollment:** `Default-Base` team creation/auto-enroll now implemented; add migration tooling for pre-existing orgs if needed.
2. **Owner enforcement:** At least one `owner` per org is enforced on role changes/removals; document transfer workflows for admins.
3. **Membership statuses:** Keep `active|inactive` only for now. Revisit when a concrete use case emerges (e.g., pending invitations, suspended users).

## 12. Future Status States
- Candidate statuses:
  - `pending`: invitation sent, awaiting acceptance.
  - `suspended`: temporarily disabled while keeping historical links.
  - `expired`: membership ended automatically (e.g., contract lapse).
- The `status` column already exists and filters are exposed via the list endpoint; future work can standardize allowed values and add lifecycle endpoints without breaking compatibility.
