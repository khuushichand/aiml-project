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
Scoped RBAC adds a second layer of permission grants derived from org/team membership roles. These scoped grants are merged into `AuthPrincipal.permissions` based on the active org/team context and a merge strategy (default union). `AuthPrincipal.permissions` represents the effective permission set used by `require_permissions` under `ORG_RBAC_SCOPE_MODE` (`union`, `active_only`, `require_active`); in `require_active`, when no active scope is set, it falls back to global-only permissions (graceful). Endpoints that must enforce scoped checks can still fail closed by explicitly verifying active scope presence before relying on scoped permissions.

### Feature Flags
- `ORG_RBAC_PROPAGATION_ENABLED` (bool, default: false)
  - Enables org/team role-to-permission propagation.
- `ORG_RBAC_SCOPE_MODE` (str, default: "union")
  - `union`: union scoped permissions across all org/team memberships (backward-compatible).
  - `active_only`: only apply scoped permissions for the active org/team.
  - `require_active`: same as `active_only`, but when no active scope is set, return only global permissions (graceful fallback). Endpoints that require scoped checks can still fail closed by explicitly verifying active scope presence before relying on scoped permissions.
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
  - FK: `permission_id` -> `permissions(id)` ON DELETE CASCADE ON UPDATE CASCADE
  - Indexes: `permission_id` (reverse lookup); composite PK already covers (`org_role`, `permission_id`)
  - Constraint: `org_role` must be one of `owner|admin|lead|member` (enum or CHECK)

- `team_role_permissions`:
  - `team_role` TEXT
  - `permission_id` INTEGER
  - PK: (`team_role`, `permission_id`)
  - FK: `permission_id` -> `permissions(id)` ON DELETE CASCADE ON UPDATE CASCADE
  - Indexes: `permission_id` (reverse lookup); composite PK already covers (`team_role`, `permission_id`)
  - Constraint: `team_role` must be one of `owner|admin|lead|member` (enum or CHECK)

Optional (future, deferred for this release): scoped overrides per user within org/team:
- `org_member_permissions` (`org_id`, `user_id`, `permission_id`, `granted`, `expires_at`)
- `team_member_permissions` (`team_id`, `user_id`, `permission_id`, `granted`, `expires_at`)

### Migration Notes
- Seed default role-to-permission mappings for `owner/admin/lead/member` (aligned with current org/team role semantics) before enabling scoped propagation.
- One-time migration script should populate `org_role_permissions` / `team_role_permissions` from the current defaults so existing memberships immediately resolve to scoped permissions.
- Enforce role validity via enum/CHECK constraints during migration; reject unknown role strings so the mapping tables remain consistent.

## Permission Resolution Algorithm
1) Resolve global permissions from `user_roles` + `user_permissions` (existing behavior).
2) Resolve scoped permissions:
   - Fetch membership roles from `org_members` / `team_members`.
   - Map roles to permissions via `org_role_permissions` / `team_role_permissions`.
   - Apply `ORG_RBAC_SCOPED_PERMISSION_PREFIXES` if configured.
3) Apply scoping mode:
   - `union`: union all scoped permissions for all memberships.
   - `active_only`: include only permissions for `active_org_id` / `active_team_id`.
   - `require_active`: same as `active_only`, but when no active scope is set, return only global permissions (graceful fallback). Endpoints that require scoped checks can still fail closed by explicitly verifying active scope presence before relying on scoped permissions.
4) Merge global + scoped permissions into `AuthPrincipal.permissions` (default union: permission granted if present in either set). A configurable merge strategy can be supported if needed (`union`, `intersection`, `scoped-overrides-global`).

### Performance and Caching
- Cache scoped permission computation (membership fetch + role-to-permission mapping + prefix filtering via `ORG_RBAC_SCOPED_PERMISSION_PREFIXES`).
- Suggested cache keys: per `user_id` for `union`, or `(user_id, active_org_id, active_team_id)` for `active_only`/`require_active` or when active scope affects output.
- TTL guidance: short-lived (for example 30-120 seconds) with optional jitter; use longer TTLs only when membership churn is rare.
- Explicitly invalidate caches when `org_role_permissions` / `team_role_permissions` mappings change or when `org_members` / `team_members` records change (and future per-user overrides, if added).
- Optionally cache computed `AuthPrincipal.permissions` to avoid per-request recompute, using the same keying, TTL, and invalidation triggers.

## API/Service Changes
- Create a scoped permission resolver in `tldw_Server_API/app/core/AuthNZ/org_rbac.py` (new module; do not use `rbac.py`).
- Update `User_DB_Handling.verify_jwt_and_fetch_user` (and API-key auth flow) to:
  - populate active org/team IDs from claims and/or headers,
  - call the scoped resolver when enabled,
  - attach scoped permissions to `AuthPrincipal` and the user model.
- Error handling: if the scoped resolver hits a DB timeout, return global-only permissions and set a resolver-failure flag on `AuthPrincipal`; do not fail the request.
- Admin endpoints to manage role-permission mappings are required for production:
  - `GET/POST/DELETE /api/v1/admin/rbac/org-roles/{role}/permissions`
  - `GET/POST/DELETE /api/v1/admin/rbac/team-roles/{role}/permissions`
- Create/update/delete of role-permission mappings must emit audit events.
- Expose scoped RBAC support via a capabilities endpoint or existing metadata so clients can detect when scoped RBAC is enabled.

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
