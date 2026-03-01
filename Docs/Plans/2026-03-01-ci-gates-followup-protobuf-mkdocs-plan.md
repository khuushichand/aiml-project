## Stage 1: Confirm New Root Causes
**Goal**: Validate post-portaudio failures for dev CI runs.
**Success Criteria**: Identify exact failing steps and error signatures for Frontend UX and onboarding-docs-gate.
**Tests**: Inspect failed job logs for run 22534506310 and 22534506299.
**Status**: Complete

## Stage 2: Workflow Remediation
**Goal**: Patch workflows for protobuf runtime compatibility and docs gate stability.
**Success Criteria**: Frontend UX jobs export protobuf python implementation env; onboarding docs gate no longer hard-fails on baseline strict warnings and uses full fetch depth.
**Tests**: Review diffs for `.github/workflows/frontend-ux-gates.yml` and `.github/workflows/onboarding-docs-gate.yml`.
**Status**: In Progress

## Stage 3: Verification
**Goal**: Validate syntax and touched-scope security.
**Success Criteria**: YAML parse check passes; Bandit on touched workflows reports no findings.
**Tests**: YAML parse script; `python -m bandit -r .github/workflows -f json`.
**Status**: Not Started

## Stage 4: Push and Re-check CI
**Goal**: Push dev updates and check the targeted workflow outcomes.
**Success Criteria**: New dev runs complete and produce actionable status for all target gates.
**Tests**: `gh run list` + `gh run view` for new runs.
**Status**: Not Started
