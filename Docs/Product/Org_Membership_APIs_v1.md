# Organization Membership APIs (v1)

## Context

The platform already supports Organizations and Teams with team-level membership APIs. The database schema includes an `org_members` table in both SQLite migrations and Postgres bootstrap, but admin APIs for managing org-level membership are not yet exposed. This document proposes v1 endpoints and services to manage organization membership.

## Goals

- Provide admin endpoints to manage organization membership:
  - Add a user to an organization with a role.
  - List organization members.
  - Remove a user from an organization.
- Keep implementation consistent with existing team membership patterns.
- Maintain backward compatibility.

## Non-Goals

- Full RBAC inheritance or per-resource ACLs.
- Invitations/workflows and email flows.
- Cross-org migration utilities.
- Advanced roles beyond `owner|admin|member` (the role field remains a simple string in v1).

- Application-level cascading between orgs and teams:
  - No automatic add/remove of team memberships when org membership changes (no default-team auto-join).
  - No automatic propagation of role changes from org to teams.
  - Database-level referential cascades still apply (e.g., deleting an org cascades to teams/team_members via FKs), but there is no extra application logic beyond that.

## Data Model

- `org_members(org_id, user_id, role, status, added_at)`
  - Primary key `(org_id, user_id)`.
  - Role default `member`.
  - Status default `active`.
  - Index on `user_id`.

The table is already created via:
- SQLite migrations: `migration_016_create_orgs_teams`.
- Postgres bootstrap: `initialize.ensure_basic_schema`.

## API Surface (Admin)

- POST `/api/v1/admin/orgs/{org_id}/members`
  - Body: `{ "user_id": int, "role": "owner|admin|member" }`
  - Response: `{ "org_id": int, "user_id": int, "role": str }`
  - Semantics: Idempotent add. If membership already exists, returns 200 with the existing membership (no 409).

- GET `/api/v1/admin/orgs/{org_id}/members`
  - Query: `limit` (default 100), `offset` (default 0), optional `role`, optional `status`.
  - Response: `[{ "user_id": int, "role": str, "status": str, "added_at": str }]`

- DELETE `/api/v1/admin/orgs/{org_id}/members/{user_id}`
  - Response: `{ "message": "Org member removed", "org_id": int, "user_id": int, "removed": true }`

- PATCH `/api/v1/admin/orgs/{org_id}/members/{user_id}`
  - Body: `{ "role": "owner|admin|member" }`
  - Response: `{ "org_id": int, "user_id": int, "role": str }`
  - Semantics: Updates only the role; 404 if membership not found.

Optional follow-up:
- GET `/api/v1/admin/users/{user_id}/org-memberships`
  - Response: `[{ "org_id": int, "role": str }]`

## Services

Implement in `tldw_Server_API/app/core/AuthNZ/orgs_teams.py`:
- `add_org_member(org_id: int, user_id: int, role: str = "member") -> dict`
- `list_org_members(org_id: int) -> list[dict]`
- `remove_org_member(org_id: int, user_id: int) -> dict`
- `update_org_member_role(org_id: int, user_id: int, role: str) -> dict`

These mirror existing team membership helpers (`add_team_member`, `list_team_members`, `remove_team_member`).

## Schemas

Add to `tldw_Server_API/app/api/v1/schemas/org_team_schemas.py`:
- `OrgMemberAddRequest(user_id: int, role: Literal["owner","admin","member"] = "member")`
- `OrgMemberResponse(org_id: int, user_id: int, role: str)`
- `OrgMemberRoleUpdateRequest(role: Literal["owner","admin","member"])`

## Endpoints

Add handlers to `tldw_Server_API/app/api/v1/endpoints/admin.py` under the Admin router:
- `POST /orgs/{org_id}/members` → `add_org_member`
- `GET  /orgs/{org_id}/members` → `list_org_members` (with `limit`, `offset`, optional `role`, `status`)
- `DELETE /orgs/{org_id}/members/{user_id}` → `remove_org_member`
- `PATCH /orgs/{org_id}/members/{user_id}` → `update_org_member_role`

All protected by `require_admin` (consistent with current org/team admin endpoints). Future enhancements may restrict writes to org owners and org admins.

## Audit Logging

- Emit audit events (Unified Audit Service; category `orgs_teams` or `authnz`) for:
  - Add member: includes `org_id`, `user_id`, `role`.
  - Remove member: includes `org_id`, `user_id`.
  - Update role: includes `org_id`, `user_id`, `role_before`, `role_after`.
- Logging is best-effort and must not block API responses.

## Error Handling

 - 404 when adding/removing references a missing org or user (DB FK will raise; translate to HTTPException 404 where possible).
 - Duplicate membership: idempotent `POST` returns existing membership (use `ON CONFLICT DO NOTHING` / `INSERT OR IGNORE`). No 409.

## Testing Plan

- SQLite integration tests:
  - Add/list/remove org member lifecycle.
  - Idempotent add (double add returns 200 and does not duplicate).
  - Role update via PATCH.
- Postgres integration tests:
  - Same lifecycle using pg pool fixtures.
- Negative tests:
  - Duplicate add is idempotent.
  - Remove non-existent membership yields success=false or a friendly message.
  - PATCH non-existent membership returns 404.

## Rollout

1. Implement service helpers in `orgs_teams.py`.
2. Add Pydantic schemas and admin endpoints.
3. Add integration tests (SQLite + Postgres markers).
4. Update docs and quick reference tables.

## Backward Compatibility

- No breaking changes; features are additive.
- Existing team membership features remain unchanged.

## Open Questions

- Should org-level membership automatically grant team memberships to default teams? (Out of scope in v1.)
- Should we add an owner constraint per org? (Future RBAC.)
