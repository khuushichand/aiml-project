# AuthNZ Stage 1 Coverage Verification (February 7, 2026)

## Scope
- Module: `tldw_Server_API/app/api/v1/endpoints/auth.py`
- Question: whether Resource Governor (RG) coverage is equivalent after AuthNZ limiter checks became no-op.

## Key Evidence
- AuthNZ limiter checks are no-op allow:
  - `tldw_Server_API/app/core/AuthNZ/rate_limiter.py:55`
  - `tldw_Server_API/app/core/AuthNZ/rate_limiter.py:65`
- RG policy mapping exists for auth routes:
  - policy: `authnz.default` in `tldw_Server_API/Config_Files/resource_governor_policies.yaml:61`
  - path map: `"/api/v1/auth*": authnz.default` in `tldw_Server_API/Config_Files/resource_governor_policies.yaml:374`
- RG ingress enforcement is conditional on middleware enablement (`RG_ENABLED`):
  - `tldw_Server_API/app/main.py:3974`
- Auth router is mounted at API v1 prefix (`/api/v1/auth/*`):
  - `tldw_Server_API/app/main.py:4814`

## Auth Endpoint Control Matrix
| Endpoint Group | Current Controls | Notes |
|---|---|---|
| `/api/v1/auth/login`, `/register`, `/magic-link/request` | `Depends(check_auth_rate_limit)` + RG ingress (if enabled) | `check_auth_rate_limit` fallback relies on AuthNZ limiter no-op when RG not active. |
| `/api/v1/auth/forgot-password` | Endpoint-local `rate_limiter.check_rate_limit` + RG ingress (if enabled) | Endpoint-local call is no-op now; effective protection is RG-only unless additional control added. |
| `/api/v1/auth/reset-password` | Endpoint-local `rate_limiter.check_rate_limit` + RG ingress (if enabled) | Same gap pattern as forgot-password. |
| `/api/v1/auth/resend-verification` | Endpoint-local `rate_limiter.check_rate_limit` + RG ingress (if enabled) | Same gap pattern. |
| `/api/v1/auth/magic-link/request` | Endpoint-local `rate_limiter.check_rate_limit` (IP + email) + `check_auth_rate_limit` + RG ingress (if enabled) | Per-email limiter intent currently not enforced due no-op limiter. |
| `/api/v1/auth/mfa/verify`, `/mfa/login` | Endpoint-local `rate_limiter.check_user_rate_limit` + RG ingress (if enabled) | Per-user limiter intent currently not enforced due no-op limiter. |
| Remaining auth routes (`/logout`, `/sessions*`, `/refresh`, `/verify-email`, `/magic-link/verify`, `/mfa/setup`, `/mfa/disable`, `/me`) | RG ingress baseline only (if enabled) + functional auth checks | No endpoint-local abuse limiter behavior remains outside RG baseline. |

## Stage 1 Conclusion
- RG does provide baseline auth coverage **when enabled** and route mapping is loaded.
- Coverage is **not equivalent** to prior endpoint-specific limiter semantics:
  - endpoint-local per-IP/per-email/per-user checks now effectively allow.
  - behavior depends on RG middleware presence; if RG is disabled, fallback paths are permissive.

## Stage 1 Verification Tests Added
- `tldw_Server_API/tests/Resource_Governance/test_auth_route_map_coverage.py`
  - validates all auth router paths resolve to `authnz.default` via middleware route-map derivation.
- `tldw_Server_API/tests/AuthNZ_Unit/test_auth_deps_hardening.py`
  - adds test showing `check_auth_rate_limit` is permissive when RG is disabled and fallback uses no-op AuthNZ limiter.
