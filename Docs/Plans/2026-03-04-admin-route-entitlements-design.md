# Admin Route Entitlements Design (WebUI + Extension)

Date: 2026-03-04  
Status: Revised after issue review

## Summary

Introduce a server-authoritative route entitlement system that allows admins to enforce enable/disable decisions for specific WebUI/extension routes per user, org, and team scope.

Approved product constraints:
- Primary model: permission -> route mapping
- Unknown entitlement state: fail closed
- Managers: platform admins + org admins + delegated team admins
- Client scope: one shared policy system for WebUI and extension
- Conflict rule: deny wins
- V1 granularity: route/page level (not component-level)

## Problem

Current UI gating mostly uses server capability flags (`docs-info` + route capability checks), which controls whether features exist on a server but not whether a specific user is entitled to access them.

Required behavior:
- Admins can restrict users to specific pages/features.
- Restricted routes are not shown in nav and cannot be opened directly.
- WebUI and extension enforce the same decisions.
- Scoped admins cannot grant beyond delegated authority.

## Goals

1. Enforce route access server-side and client-side with a shared contract.
2. Keep capability gating (feature exists) and entitlement gating (user allowed) separate but composable.
3. Preserve secure fail-closed behavior while preventing total lockout during transient outages.
4. Make policy merges deterministic and auditable.
5. Ensure revocation takes effect quickly.

## Non-Goals (V1)

- Component-level/field-level UI entitlements.
- Replacing existing RBAC permission semantics.
- Policy DSL for arbitrary conditions beyond route scope + subject scope.

## Existing Surfaces Reused

Frontend:
- `apps/packages/ui/src/routes/route-registry.tsx`
- `apps/packages/ui/src/routes/app-route.tsx`
- `apps/packages/ui/src/routes/route-capabilities.ts`
- `apps/packages/ui/src/components/Layouts/settings-nav.ts`
- `apps/packages/ui/src/services/tldw/server-capabilities.ts`

Backend:
- `tldw_Server_API/app/api/v1/endpoints/config_info.py`
- `tldw_Server_API/app/api/v1/endpoints/users.py`
- `tldw_Server_API/app/api/v1/endpoints/admin/admin_rbac.py`
- `tldw_Server_API/app/services/admin_scope_service.py`
- `tldw_Server_API/app/core/AuthNZ/principal_model.py`

## Design

### 1. Route Entitlement Contract (fixes route identity drift)

Add a canonical route ID for every routed page.

Contract source of truth:
- Frontend exports a typed manifest (`route_id`, `path`, metadata).
- Backend stores/evaluates policies by `route_id`, never raw path.

Route schema (conceptual):
- `route_id`: stable string (example: `settings.admin.server`)
- `path`: route path (`/settings/admin/server`)
- `targets`: `webui|extension|both`
- `requires_capabilities`: optional capability keys
- `sensitivity`: `normal|admin|security_critical`

Rules:
- Path changes must not change `route_id`.
- New routes require route manifest entry + entitlement default decision.
- Removed route IDs are retained as deprecated aliases for one minor release, then removed.

### 2. Policy Model and Deterministic Merge (fixes merge ambiguity)

Policy row shape:
- `id`
- `scope_type`: `platform|org|team|user`
- `scope_id`: nullable for platform
- `subject_type`: `role|user|team|org`
- `subject_id`
- `route_id`
- `effect`: `allow|deny`
- `priority`: integer (optional explicit tie-break)
- `reason`
- `created_by`, `created_at`, `updated_at`

Effective decision algorithm (deterministic):
1. Collect candidate rules for principal in this order:
   - platform-wide
   - org-scoped (active org + memberships)
   - team-scoped (active team + memberships)
   - user-specific
2. Sort by precedence tuple:
   - `(scope_specificity, priority, updated_at, rule_id)`
   - `scope_specificity`: `user > team > org > platform`
3. Resolve by effect with hard rule:
   - any matching `deny` => final `deny`
   - else if any matching `allow` => final `allow`
   - else `default_deny`

Result payload includes `evaluation_trace` in admin debug mode for auditability.

### 3. Delegated Admin Scope Matrix (fixes privilege-escalation risk)

Enforcement principle:
- An admin may only manage rules inside scopes they administer.
- They may not create policies that grant authority above their own scope.

Matrix:
- Platform admin:
  - Can read/write platform, org, team, user policies.
- Org admin:
  - Can read/write org policies in own org.
  - Can read/write team/user policies only within own org.
  - Cannot mutate platform scope.
- Team delegated admin/lead:
  - Can read/write team policies for own team.
  - Can write user policies only for users in own team.
  - Cannot write org/platform scope.

All write endpoints call shared scope guard services (`admin_scope_service`) and return 403 on boundary violations.

### 4. APIs

#### Read effective entitlements

`GET /api/v1/entitlements/me/routes`

Query params:
- `target=webui|extension`
- `include_trace=false|true` (admin-only)

Response (conceptual):
- `version`: monotonic policy version/hash
- `issued_at`
- `ttl_seconds`
- `routes`: map by `route_id`
  - `decision`: `allow|deny`
  - `source_scope`: `platform|org|team|user|default`
  - `reason_code`

#### Admin policy management

- `GET /api/v1/admin/entitlements/policies`
- `POST /api/v1/admin/entitlements/policies`
- `PATCH /api/v1/admin/entitlements/policies/{policy_id}`
- `DELETE /api/v1/admin/entitlements/policies/{policy_id}`

Mandatory write fields:
- `reason`
- `change_ticket` (optional but recommended)
- `dry_run=true` support for impact preview

#### Dry-run impact endpoint

`POST /api/v1/admin/entitlements/simulate`

Input:
- proposed policy change

Output:
- affected users count
- top affected route IDs
- sampled before/after decisions

### 5. Client Enforcement Flow

1. Bootstrap:
   - Fetch server capabilities (`docs-info`) and route entitlements in parallel.
2. Compose decision per route:
   - `final_visible = capability_allows AND entitlement_allows`
3. Apply everywhere:
   - navigation filters
   - route registration/guards
   - direct URL navigation checks
4. Denied UX:
   - redirect to safe landing page with non-sensitive explanation.
5. Unknown state handling:
   - fail closed for non-safe routes.

### 6. Resilience Mode (fixes fail-closed outage lockout)

Because fail-closed can lock users out during control-plane outages, define minimal always-available routes:
- `/`
- `/chat`
- `/settings`
- `/settings/profile` (if present)
- auth/session recovery route(s)

Resilience behavior:
- If entitlement fetch fails and cache is fresh (`<= ttl_seconds`), use cached decisions.
- If cache stale and network unavailable:
  - only allow minimal safe routes above.
  - deny all others.
- Display “policy sync unavailable” banner with retry.

### 7. Revocation Freshness SLA (fixes stale-permission window)

Target:
- 95% of revocations enforced in UI within 60 seconds.
- 99% within 5 minutes.

Mechanics:
- Use ETag/version polling every 30-60s (or admin event stream trigger).
- Invalidate entitlement cache on login refresh, org/team context switch, role change signal.
- Hard max cache age: 5 minutes.

### 8. Auditing and Operations

Audit record per policy write:
- actor principal
- scope
- route_id
- old decision/new decision
- reason
- correlation/request id

Operational endpoints/metrics:
- policy version
- evaluation latency
- cache hit ratio
- revocation lag percentile
- denied-route attempt counters

## Security Notes

- Server remains source of truth; client checks are UX and defense-in-depth.
- Deny wins globally.
- Scoped admins cannot self-elevate by cross-scope writes.
- Avoid exposing sensitive policy internals in standard user responses.

## Rollout

1. Backend scaffolding (schema + read endpoint + admin CRUD with scope enforcement).
2. Frontend route ID contract adoption (no behavior change yet).
3. Client gating switched to combined capability + entitlement checks behind feature flag.
4. Canary with audit-only dry-run metrics.
5. Full enforcement; remove legacy route-by-route special cases where covered.

## Test Strategy

Backend:
- Unit tests for merge order, deny precedence, and scope boundaries.
- Integration tests for entitlement read endpoint per admin level.
- Regression tests for single-user mode behavior.

Frontend:
- Unit tests for route manifest + gating combinator.
- Route guard tests for hidden nav and direct path block.
- WebUI/extension parity tests for identical entitlement payload.

E2E:
- Admin applies deny on route -> target user loses nav + direct access.
- Revocation timing assertions within SLA envelope.
- Outage simulation verifies resilience mode safe-route behavior.

## Acceptance Criteria

1. Admin can enforce route-level allow/deny for user/org/team scopes.
2. Restricted routes disappear from nav and are blocked on direct access.
3. Deny always overrides allow.
4. Delegated admins cannot write outside authorized scope.
5. Revocation freshness meets SLA targets.
6. WebUI and extension show consistent route availability for same principal.
