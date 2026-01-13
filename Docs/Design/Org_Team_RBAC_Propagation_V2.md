# Org/Team RBAC Propagation (v2)

## Summary
Introduce scoped RBAC propagation so organization/team membership roles map to permission grants and can be enforced per request using an active org/team context. The system remains backward-compatible via feature flags and defaults to legacy (global) permission resolution.

## Goals
- Map org/team membership roles to permission grants without granting platform-wide admin powers.
- Support active org/team scoping for permission checks (opt-in enforcement).
- Keep single-user mode behavior unchanged.
- Preserve existing RBAC tables and permissions while adding scoped overlays.

## Non-Goals (v2)
- Full per-resource ACLs for every domain object (tracked as a follow-up once scoped RBAC is stable).
- Automatic cross-org role propagation beyond explicit membership (no implicit org-to-org role bridging).
- Replacing the global roles/permissions system; scoped RBAC is additive.

## Current State (v1)
- Global RBAC tables: `roles`, `permissions`, `role_permissions`, `user_roles`, `user_permissions`.
- Org/team membership roles stored in `org_members` and `team_members` and used by `org_deps` only.
- `AuthPrincipal.permissions` is computed from global RBAC and used by `require_permissions`.
- `request.state` includes `org_ids`/`team_ids` and optional `active_org_id`/`active_team_id` (JWT claims or membership lookup).

## Design Overview
Scoped RBAC adds a second layer of permission grants derived from org/team membership roles. These scoped grants are merged into `AuthPrincipal.permissions` based on the active org/team context.

### Feature Flags
- `ORG_RBAC_PROPAGATION_ENABLED` (bool, default: false)
  - Enables org/team role-to-permission propagation.
- `ORG_RBAC_SCOPE_MODE` (str, default: "union")
  - `union`: union scoped permissions across all org/team memberships (backward-compatible).
  - `active_only`: only apply scoped permissions for the active org/team.
  - `require_active`: if no active org/team, scoped permissions are empty and endpoints using scoped checks can fail closed.
- `ORG_RBAC_SCOPED_PERMISSION_PREFIXES` (list[str], optional)
  - Allowlist prefixes for scoped permissions (e.g., `media.`, `chat.`, `rag.`). Helps avoid granting system-level permissions from org/team roles.

### Active Org/Team Resolution
Priority order for active scope:
1) JWT claims: `active_org_id`/`active_team_id`.
2) Request headers: `X-TLDW-Org-Id`, `X-TLDW-Team-Id` (new, optional).
3) First org/team from membership lists.

Active scope is stored in `request.state.active_org_id` / `request.state.active_team_id` and propagated to `AuthPrincipal`.

## Data Model
Add mapping tables for org/team membership roles to permission grants:

- `org_role_permissions`:
  - `org_role` TEXT (e.g., owner/admin/lead/member)
  - `permission_id` INTEGER
  - PK: (`org_role`, `permission_id`)

- `team_role_permissions`:
  - `team_role` TEXT
  - `permission_id` INTEGER
  - PK: (`team_role`, `permission_id`)

Optional (future): scoped overrides per user within org/team:
- `org_member_permissions` (`org_id`, `user_id`, `permission_id`, `granted`, `expires_at`)
- `team_member_permissions` (`team_id`, `user_id`, `permission_id`, `granted`, `expires_at`)

## Permission Resolution Algorithm
1) Resolve global permissions from `user_roles` + `user_permissions` (existing behavior).
2) Resolve scoped permissions:
   - Fetch membership roles from `org_members` / `team_members`.
   - Map roles to permissions via `org_role_permissions` / `team_role_permissions`.
   - Apply `ORG_RBAC_SCOPED_PERMISSION_PREFIXES` if configured.
3) Apply scoping mode:
   - `union`: union all scoped permissions for all memberships.
   - `active_only`: include only permissions for `active_org_id` / `active_team_id`.
   - `require_active`: same as `active_only`, but when no active scope, return only global permissions.
4) Merge global + scoped permissions and attach to `AuthPrincipal.permissions`.

## API/Service Changes
- Add a scoped permission resolver in `tldw_Server_API/app/core/AuthNZ/rbac.py` or a new `org_rbac.py`.
- Update `User_DB_Handling.verify_jwt_and_fetch_user` and API-key auth flows to:
  - populate active org/team IDs from claims or headers,
  - compute scoped permissions when enabled,
  - attach results to `AuthPrincipal` and user model.
- Optional admin endpoints to manage role-permission mappings:
  - `GET/POST/DELETE /api/v1/admin/rbac/org-roles/{role}/permissions`
  - `GET/POST/DELETE /api/v1/admin/rbac/team-roles/{role}/permissions`

## Compatibility & Rollout
- Default flags keep behavior unchanged (no scoped propagation).
- `union` mode can be used for zero-regression adoption.
- `active_only`/`require_active` can be enabled per deployment once clients set active org/team.

## Testing Plan
- Unit tests: scoped permission resolution with union vs active_only.
- Integration tests: admin endpoints update mappings; scoped permissions applied to `require_permissions`.
- Regression: single-user mode unaffected; JWT/API-key auth still works with no active scope.

## Open Questions
- Should scoped permissions include team memberships when active org is set but team is not?
- Which permission prefixes are safe for scoped grants in v2 (default allowlist)?
- Do we need an explicit header for active org/team in non-JWT flows?

