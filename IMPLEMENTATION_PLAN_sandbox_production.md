## Stage 1: Access Control & Ownership
**Goal**: Enforce JWT/session auth for sandbox WS and ownership checks for sessions/runs/artifacts/cancel.
**Success Criteria**: Non-owners receive 403/404; WS requires authenticated principal; tests updated/added.
**Tests**: sandbox auth/ownership unit tests; WS auth tests.
**Status**: Not Started

## Stage 2: Lifecycle & Storage Hygiene
**Goal**: Create session workspaces on create; implement destroy/TTL cleanup; drain queue on completion; persist artifact usage bytes.
**Success Criteria**: Upload works; queue doesn’t leak; artifacts usage caps enforced; cleanup paths covered.
**Tests**: lifecycle tests for workspace creation/destroy; queue drain; artifact usage accounting.
**Status**: Not Started

## Stage 3: Runtime Hardening & Firecracker PRD
**Goal**: Harden Docker path (policy enforcement, fail-closed egress allowlist); implement Firecracker backend per PRD behind feature flag.
**Success Criteria**: Docker enforcement per policy; Firecracker fake/real gated; PRD acceptance criteria met (when enabled).
**Tests**: docker policy clamp tests; Firecracker fake/real gating tests (unit + optional integration).
**Status**: Not Started
