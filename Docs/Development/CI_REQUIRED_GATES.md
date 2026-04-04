# CI Required Gates

This document defines the required pull-request gate contract during the phased CI rollout.

## Required Check Names

Configure branch protection to require these checks:

1. `backend-required`
2. `security-required`
3. `coverage-required`
4. `frontend-required`
5. `e2e-required`
6. `container-build-check`

These check names are stable and should remain unchanged once branch protection is configured.

Branch protection is configured in GitHub repository settings, not in workflow YAML. Add `container-build-check` to the protected-branch required checks after it has reported successfully at least once.

## Conditional Execution and No-op Behavior

Each required gate always reports a status for deterministic branch protection behavior.

- If relevant paths changed, the gate executes its full checks.
- If relevant paths did not change, the gate exits with an explicit no-op success message.

Examples:

- UI-only PRs no-op `backend-required` and `coverage-required`.
- Backend-only PRs no-op `frontend-required`.
- `e2e-required` runs on frontend changes and selected backend API/schema/auth paths.

## Security Threshold Policy

`security-required` enforces blocking findings at `HIGH`/`CRITICAL` severity with an allowlist.

- Allowlist file: `.github/security/ci-allowlist.yml`
- Every allowlist entry must include:
  - vulnerability id
  - owner
  - expiry date (ISO format)

Expired allowlist entries are ignored by the gate.

## Rollout Phases (2-4 Weeks)

1. Introduce required lanes and deterministic no-op semantics.
2. Tighten blocking behavior across required lanes.
3. Refine path coupling and flake handling in `e2e-required`.
4. Finalize branch protection to required lane names above.

## Legacy CI Workflow

The large legacy `.github/workflows/ci.yml` workflow remains available during rollout for broad visibility and historical comparison.
Required merge protection is provided by the six lanes listed above.
