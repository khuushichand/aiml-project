# Principal Governance PRD (v0.1 Summary)

## Summary

This document summarizes how authenticated principals (`AuthPrincipal`) and request
auth context (`AuthContext`) are governed in v0.1, and enumerates the key HTTP
surfaces where principal/state invariants are enforced by tests.

The full design and implementation notes live in:
- `Docs/Design/AuthNZ-Refactor-Implementation-Plan.md`
- `Docs/Code_Documentation/Guides/AuthNZ_Code_Guide.md`

This file acts as a compact index for “governed surfaces” and their coverage.

## Core Model

- `AuthPrincipal` (`tldw_Server_API/app/core/AuthNZ/principal_model.py`):
  - Fields: `kind` (`"user" | "api_key" | "service" | "anonymous" | "single_user"`),
    `user_id`, `api_key_id`, `roles`, `permissions`, `is_admin`, `org_ids`, `team_ids`.
  - Derived `principal_id` is a stable, pseudonymous identifier used for logs/metrics.
- `AuthContext`:
  - Wraps `AuthPrincipal` plus request metadata (`ip`, `user_agent`, `request_id`).
  - Attached at `request.state.auth` by `get_current_user` / `get_auth_principal`.
- Request-state invariants (v0.1 contract):
  - When a principal is resolved, `request.state.user_id` / `api_key_id` MUST mirror
    `AuthContext.principal.user_id` / `api_key_id`.
  - `request.state.org_ids` / `team_ids` MUST mirror `AuthContext.principal.org_ids` /
    `team_ids` when they are populated.
  - Middlewares and guardrails (usage logging, budgets, jobs admin, etc.) MUST derive
    identity from `request.state.auth.principal`, not from raw headers or mode flags.

## Governed Surfaces Matrix (v0.1)

The table below lists representative HTTP surfaces where principal/state invariants
are explicitly tested. For each, tests assert alignment between:
- `AuthPrincipal` (from `get_auth_principal`)
- `request.state.user_id` / `api_key_id` / `org_ids` / `team_ids`
- `request.state.auth.principal`

| Domain / Route                                  | Auth Path             | Principal Kind(s) | Invariant Tests                                                                                           |
|-------------------------------------------------|-----------------------|-------------------|----------------------------------------------------------------------------------------------------------|
| AuthNZ “whoami” (JWT happy path)               | Bearer JWT            | `user`            | `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_jwt_happy_path.py`                         |
| AuthNZ “whoami” (API key happy path)           | AuthNZ API key        | `api_key`         | `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_api_key_happy_path.py`                     |
| Media – process-videos                         | AuthNZ API key        | `api_key`         | `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_media_rag_invariants.py`                   |
| RAG – unified search                            | Bearer JWT            | `user`            | `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_media_rag_invariants.py`                   |
| Tools – execute (`/api/v1/tools/execute`)      | AuthNZ API key        | `api_key`         | `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_tools_invariants.py`                       |
| Evaluations – list (`/api/v1/evaluations/`)    | Bearer JWT            | `user`            | `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_evaluations_invariants.py::test_evaluations_list_jwt_principal_and_state_alignment` |
| Evaluations – admin cleanup (idempotency)      | Bearer JWT            | `user`            | `tldw_Server_API/tests/AuthNZ/integration/test_auth_principal_evaluations_invariants.py::test_evaluations_admin_cleanup_jwt_principal_and_state_alignment` |
| Single-user profile (bootstrapped admin)       | X-API-KEY (single_user) | `single_user`   | `tldw_Server_API/tests/AuthNZ/integration/test_single_user_claims_permissions.py`                        |

Additional claim-first / permissions surfaces (without dedicated principal-state
capture wrappers) include:
- Resource-Governor admin and diagnostics endpoints (`/api/v1/resource-governor/*`)
  – claim-first via `require_roles("admin")` with behavior locked in by:
  - `tldw_Server_API/tests/AuthNZ_Unit/test_resource_governor_permissions_claims.py`
  - `tldw_Server_API/tests/Resource_Governance/test_rg_capabilities_endpoint.py`
  - `tldw_Server_API/tests/Resource_Governance/test_resource_governor_endpoint.py`
- Metrics admin (`/api/v1/metrics/reset`) – claim-first admin via
  `require_roles("admin")`, covered by
  `tldw_Server_API/tests/AuthNZ_Unit/test_metrics_permissions_claims.py`.
- Sandbox admin, MCP admin, monitoring admin, scheduler workflows admin – all
  claim-first and covered by the corresponding `test_*permissions_claims.py`
  suites under `tldw_Server_API/tests/AuthNZ_Unit/`.

## Relationship to Other PRDs

- **User-Auth-Deps PRD (`Docs/Product/User-Auth-Deps-PRD.md`)**
  - Defines the dependency surface (`get_auth_principal`, `get_current_user`,
    `require_permissions`, `require_roles`) and mandates claim-first behavior.
  - Phase 1 (“AuthPrincipal + Claim Invariants”) and Phase 2 (“Claim-First
    Permissions”) reference the invariant and permissions tests listed above.

- **User-Unification PRD (`Docs/Product/User-Unification-PRD.md`)**
  - Treats single-user as a bootstrap profile of multi-user, with a real admin
    user and API key seeded in AuthNZ.
  - Notes that principal/state invariants span media, RAG, tools, and evaluations,
    in both multi-user and single-user deployments, as part of Stage 2/3 work.

These documents together specify that:
- New endpoints must use the claim-first dependency stack and participate in the
  `AuthPrincipal` / `AuthContext` model.
- New high-value domains should, where practical, add an invariant-style test
  that exercises at least one representative route (JWT and/or API-key path)
  and asserts principal/state alignment as shown above.

