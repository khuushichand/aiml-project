# Legacy Media Ingestion Deprecation Reduction Design

Date: 2026-02-28
Owner: Documentation + Cleanup Program
Status: Approved

## Context

The media ingestion surface is in a migration phase where modular endpoint files exist, but many paths still preserve behavior through legacy shims/adapters. This increases maintenance cost, testing complexity, and regression risk.

This design defines a phased deprecation program focused on media ingestion first, with a one-release compatibility window.

## Decision Summary

- Deprecation posture: phased removal.
- First subsystem: media ingestion endpoints.
- Compatibility window: one release cycle.
- Recommended approach selected: contract-first shim retirement.

## Goals

1. Make modular media endpoint handlers the canonical execution path.
2. Retain API behavior parity during the compatibility window.
3. Add explicit, consistent deprecation signaling.
4. Remove legacy media shims in the next release once gates are met.

## Non-Goals

1. Removing non-media legacy APIs in this wave (for example auth/user legacy endpoints).
2. Frontend legacy key/storage cleanup.
3. Major request/response contract redesign.

## Approaches Considered

### Option 1: Contract-First Shim Retirement (Selected)

- Freeze behavior with contract tests for all targeted endpoints.
- Route all logic through canonical service/orchestrator paths.
- Keep legacy compatibility at the boundary with warnings.
- Remove shims after one release when gates pass.

Pros:
- Lowest regression risk.
- Clear, objective removal criteria.
- Enables fast follow-on cleanup.

Cons:
- Requires upfront test investment.

### Option 2: Big-Bang Endpoint Rewrite

Pros:
- Fastest apparent cleanup.

Cons:
- Highest regression risk.
- Difficult rollback when parity issues appear.

### Option 3: Telemetry-First, Delayed Removal

Pros:
- Operationally low risk now.

Cons:
- Debt remains and grows.
- Delays simplification benefits.

## Scope

In-scope endpoint families:

- `/process-videos`
- `/process-audios`
- `/process-pdfs`
- `/process-documents`
- `/process-ebooks`
- `/process-web-scraping`
- `/process-emails`

Primary code area:

- `tldw_Server_API/app/api/v1/endpoints/media/`

## Architecture

### 1. Canonical Execution Layer

Each media ingest endpoint adapter calls a shared canonical service/orchestrator interface. Business logic ownership moves out of legacy modules.

### 2. Compatibility Boundary

Legacy behavior remains stable at the HTTP boundary:

- request compatibility (where required),
- response envelope parity,
- status code parity,
- partial-success semantics parity.

Deprecation headers/warnings/logs are additive and non-breaking.

### 3. Removal Boundary

In the next release, delete legacy adapter indirection only when removal gates pass (parity tests green + low/no legacy usage signal + no error regression).

## Components

### Endpoint Adapters (HTTP layer)

Maintain validation, dependency wiring, and mapping to canonical request objects.

### Canonical Ingest Service (execution layer)

Central orchestration for all media ingest types:

- input normalization,
- batch orchestration,
- partial success accounting,
- result shaping for endpoint adapters.

### Legacy Compatibility Adapters

Legacy modules become pass-through only. No durable business logic remains there by end of window.

### Deprecation Signaling Utility

Single helper to emit:

- deprecation response headers,
- warning payload fields,
- structured logs/metrics.

### Parity Test Harness

Contract tests define removal readiness and block regressions.

## Data Flow

1. Endpoint adapter accepts request and resolves dependencies.
2. Adapter normalizes legacy aliases into canonical internal fields.
3. Adapter constructs canonical typed request model.
4. Canonical ingest service executes processing path for media type.
5. Service returns canonical internal result.
6. Adapter maps result to legacy-compatible response envelope/status.
7. If legacy behavior/alias was used, adapter emits deprecation signals.
8. Telemetry records usage for removal decision in next release.

## Error Handling

1. Preserve external behavior parity (status codes, envelope, error fields).
2. Use typed internal errors in canonical service.
3. Translate internal errors at adapter boundary to current external contract.
4. Deprecation signaling is non-fatal during compatibility window.
5. Fail fast with explicit logs if parity mapping is not possible.
6. Track error-rate drift; block removals if drift exceeds thresholds.

## Testing Strategy

### Contract Tests (Priority 1)

Capture/lock behavior for each in-scope endpoint:

- status codes,
- response envelope keys,
- partial success behaviors,
- error payload semantics.

### Compatibility Tests

Validate legacy aliases/routes continue to work with additive deprecation signals.

### Negative-Path Tests

Cover invalid mixed inputs, empty inputs, malformed files, upstream failures, and DB failure modes with parity assertions.

### Observability and Removal Readiness

Assert legacy-usage signals are emitted and verify adapters are shim-only before deletion.

## Deprecation Timeline

Release N (current):

- canonical paths active,
- compatibility shims retained,
- deprecation signaling enabled,
- telemetry and parity checks enforced.

Release N+1:

- remove media legacy shims/adapters,
- remove legacy alias paths approved for deletion,
- update docs/changelog with migration completion.

## Success Criteria

1. All in-scope media endpoints run through canonical orchestration.
2. Contract parity tests pass for all covered scenarios.
3. Deprecation signals are present and consistent.
4. Legacy adapter modules are shim-only before removal.
5. Next release removes targeted media shims without behavior regressions.

## Risks and Mitigations

Risk: Hidden behavior coupling in legacy code.
Mitigation: lock parity with contract tests before and during extraction.

Risk: Downstream users rely on undocumented legacy quirks.
Mitigation: additive warnings plus one-release compatibility window.

Risk: Partial-success semantics drift during consolidation.
Mitigation: endpoint-level golden contract assertions for mixed-success batches.

## Rollout Gates

1. Green contract test matrix for all in-scope endpoints.
2. No unresolved parity bugs tagged for migration.
3. Legacy usage rate below agreed threshold for removal.
4. Error-rate and support-ticket baseline unchanged within tolerance.

