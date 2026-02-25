# CI/CD Quality Gating Testing Strategy Design

- Date: 2026-02-24
- Scope: Pull request quality gates for `main`/`dev`
- Objective: Maximize pre-merge defect prevention while preserving deterministic required checks and avoiding unnecessary lane execution

## 1. Decisions Captured

1. Primary optimization: maximum defect prevention before merge
2. Required checks policy: backend + security always required in branch protection, frontend/e2e required with path-aware execution model
3. Runtime budget: up to 60 minutes acceptable when it improves defect catch rate
4. Security blocking threshold: block on `high` and `critical`
5. Coverage model: global minimum only
6. Backend-to-frontend/e2e coupling: trigger e2e/frontend for specific backend API/schema paths used by UI
7. Rollout: phased migration over 2-4 weeks

## 2. Recommended Approach

Use a **tiered required-gates architecture** with stable required check names, where each lane always reports status but conditionally executes heavy work.

### Why this approach

- Maintains strict merge protection with transparent ownership per lane
- Avoids wasting CI time by running backend suites for UI-only PRs (and vice versa)
- Supports deterministic branch protection because lanes never disappear; irrelevant lanes no-op pass with explicit reason
- Eases phased rollout and debugging compared to a single monolithic workflow

## 3. Gate Architecture

Define these required lanes:

1. `backend-required`
2. `security-required`
3. `coverage-required`
4. `frontend-required`
5. `e2e-required`

All lanes use a shared change-detection contract and can no-op pass when out-of-scope.

### 3.1 Shared change detector

Add a fast `changes` job that emits booleans:

- `backend_changed`
- `frontend_changed`
- `e2e_changed`
- `security_relevant_changed`

These booleans gate lane execution while preserving stable lane status names.

### 3.2 Path ownership model

Initial path sets:

- Backend paths:
  - `tldw_Server_API/**`
  - `pyproject.toml`
  - `uv.lock`
  - backend GitHub actions/composite actions
- Frontend paths:
  - `apps/tldw-frontend/**`
  - `apps/packages/ui/**`
  - `apps/extension/**`
  - frontend lockfiles and UI workflows
- E2E escalation backend paths (backend changes that can break UI):
  - `tldw_Server_API/app/api/v1/endpoints/**`
  - `tldw_Server_API/app/api/v1/schemas/**`
  - selected auth/session middleware and API compatibility layers used by WebUI
- Security-relevant paths:
  - dependency manifests/locks
  - backend code
  - workflow definitions for CI/security

## 4. Lane Responsibilities

### 4.1 `backend-required`

Run only when `backend_changed=true`.

- Blocking syntax checks
- Blocking lint/type checks for backend scope (remove non-blocking behavior)
- Blocking backend unit/integration merge-protection suites

No-op behavior when false:
- Emit explicit message: `No backend paths changed; backend-required passed by policy.`

### 4.2 `security-required`

Always required as a branch-protection check name.

Execution model:
- Dependency/CVE and CodeQL status checks always run or validate freshness
- Bandit path-aware behavior:
  - full backend/security scan when backend/security paths changed
  - no-op or lightweight validation when no relevant path changed

Blocking policy:
- Fail on `high`/`critical`
- Maintain explicit allowlist with owner and expiry date

### 4.3 `coverage-required`

Run when `backend_changed=true`.

- Enforce one global coverage floor for backend test run
- No diff coverage requirement

No-op when backend unchanged.

### 4.4 `frontend-required`

Run when `frontend_changed=true`.

- Frontend lint/type/unit gates in merge-protection scope
- Keep lane focused on high-signal checks

No-op when frontend unchanged.

### 4.5 `e2e-required`

Run when either:
- `frontend_changed=true`, or
- backend changes hit `e2e_changed` API/schema/auth coupling paths

- Execute critical user-journey E2E smoke gates only
- Keep long-tail or exploratory E2E in non-required schedules/nightly

No-op otherwise.

## 5. Failure and Error-Handling Policy

1. Required lanes are blocking (`continue-on-error: false`)
2. One controlled retry allowed for designated flaky E2E segments
3. If retry still fails, lane fails
4. Each no-op lane logs decision basis for auditability
5. Hard per-lane timeouts + fail-fast command behavior

## 6. Test Strategy for Merge Protection

### 6.1 Required merge-protection tests

- Backend: fast/high-signal unit + integration smoke for changed backend domains
- Frontend: core lint/type/unit scope for changed frontend paths
- E2E: critical journeys only (auth, onboarding, ingest, core chat/playground, key settings)

### 6.2 Non-required test inventory

- Extended E2E matrices
- Long-running stress/perf suites
- Broad exploratory workflows

These remain on scheduled/nightly/manual pipelines and do not block PR merge.

## 7. Rollout Plan (Phased, 2-4 Weeks)

### Phase 1: Normalize gates and observability

- Add shared `changes` contract
- Convert lanes to stable required names with no-op pass support
- Add explicit lane-level skip/no-op messaging

Success criteria:
- Required checks deterministic on every PR
- No backend suite executed on pure UI-only PRs

### Phase 2: Enforce strict blocking semantics

- Remove non-blocking behavior from required backend lint/type/test lanes
- Enable security blocking at `high`/`critical`
- Enforce global coverage floor in `coverage-required`

Success criteria:
- Required lane failures block merge as designed
- Security findings at `high`/`critical` fail PR

### Phase 3: Tighten path coupling and flake controls

- Refine API/schema/auth path map driving `e2e-required`
- Add controlled retry policy and flake telemetry
- Promote stable E2E critical journeys to required set

Success criteria:
- Low false-skip rate for UI-impacting backend changes
- Reduced flaky failure noise in required E2E lane

### Phase 4: Branch protection finalization

- Lock required check set to the five lane names
- Document operational ownership and incident runbook

Success criteria:
- Branch protection fully aligned with lane contract
- Teams can quickly diagnose why a lane ran, failed, or no-op passed

## 8. Risks and Mitigations

1. Risk: Path filters miss UI-impacting backend changes
   - Mitigation: start conservative for API/schema/auth coupling paths, review misses weekly
2. Risk: Security scan noise slows teams
   - Mitigation: strict severity threshold (`high`/`critical`) + managed allowlist expiry
3. Risk: Required E2E flakes block merges
   - Mitigation: one-retry policy + ownership/SLA + quarantine only with explicit approval
4. Risk: Gate sprawl increases maintenance burden
   - Mitigation: stable five-lane contract and explicit lane ownership

## 9. Definition of Done for This Design

- Tiered conditional required-lane model documented and approved
- Lane responsibilities and trigger semantics explicit
- Blocking policy, coverage model, and security thresholds explicit
- Phased rollout plan and risk mitigations explicit
