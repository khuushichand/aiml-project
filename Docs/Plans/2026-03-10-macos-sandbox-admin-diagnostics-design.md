# macOS Sandbox Admin Diagnostics Design

Date: 2026-03-10
Status: Approved for planning
Scope: `tldw_Server_API/app/core/Sandbox/` diagnostics, sandbox admin API, and runtime discovery reuse

## 1. Summary

This design adds a dedicated admin-only macOS diagnostics surface for sandbox runtime readiness while keeping `GET /api/v1/sandbox/runtimes` concise.

The selected direction is:

- a shared, side-effect-free diagnostics probe layer
- a new admin endpoint for detailed macOS host/helper/template/runtime posture
- summarized reuse of the same probe results in `/api/v1/sandbox/runtimes`

The design stays conservative:

- diagnostics are operator-facing, not client-facing
- detailed host paths and remediation hints remain admin-only
- readiness distinguishes `host not ready` from `policy unsupported`
- diagnostics should share low-level facts with the existing runner preflight path instead of inventing a second runtime-readiness engine

## 2. User-Confirmed Decisions

1. The next macOS sandbox milestone should optimize for production-grade host readiness and operator tooling first.
2. The first slice in that milestone is host diagnostics and preflight proof.
3. The proof should surface first through a dedicated admin diagnostics endpoint, while `/sandbox/runtimes` stays summarized.

## 3. Problem

The merged macOS sandbox runtime scaffolds expose runtime identities and preflight-based availability, but there is not yet a clear operator surface for answering basic readiness questions such as:

- Is this host actually supported for `vz_linux` or `vz_macos`?
- Is the native helper configured, present, executable, and ready?
- Are the required templates configured and ready per runtime?
- Is the runtime unavailable because of host posture, missing assets, or trust-policy restrictions?

Today that information is either not exposed, partially duplicated across preflight code, or too coarse for operators who need to bring up Apple silicon hosts reliably.

Without a dedicated diagnostics layer:

- `/sandbox/runtimes` risks expanding into an operator dump instead of a client discovery contract
- readiness rules will drift between runners, service discovery, and any future helper/image-store tooling
- support triage will be slower because detailed reasons and remediation steps are missing

## 4. Goals and Non-Goals

### Goals

1. Add a reusable macOS diagnostics module that evaluates host, helper, template, and runtime readiness.
2. Expose a new admin-only endpoint with structured diagnostics and remediation hints.
3. Keep `/api/v1/sandbox/runtimes` concise while reusing the same probe results where possible.
4. Distinguish `policy unsupported` from `host not ready` in a way operators and tests can rely on.
5. Keep the first diagnostics slice side-effect free and safe to call repeatedly.

### Non-Goals

1. Implementing real VM execution or real seatbelt command execution in this slice.
2. Replacing runtime-specific execution-time preflight checks with a one-time startup cache.
3. Exposing detailed local filesystem paths or helper posture to non-admin callers.
4. Building a full operator CLI or janitor workflow in the same change.

## 5. Selected Architecture

### 5.1 Shared diagnostics probe layer

Add a new sandbox-core module, likely `tldw_Server_API/app/core/Sandbox/macos_diagnostics.py`, with pure or near-pure probe functions:

- `probe_host()`
- `probe_helper()`
- `probe_templates()`
- `probe_runtime_statuses()`
- `collect_macos_diagnostics()`

These probes should consume the same config and environment knobs already used by the macOS runners, but they should avoid changing system state. The first release should not:

- start the helper
- mutate templates
- create clones
- boot VMs

That keeps the endpoint safe for operators, tests, and future health checks.

For runtime-level availability and reasons, phase 1 should prefer existing runner preflight contracts over a new parallel interpretation layer. In practice, the diagnostics module should derive runtime entries from the same runner preflight results already used by admission and feature discovery, then layer on extra operator metadata such as helper/template configuration detail.

### 5.2 Admin diagnostics endpoint

Add an admin-only endpoint under the existing sandbox router:

- `GET /api/v1/sandbox/admin/macos-diagnostics`

It should use the same admin auth pattern already present on sandbox admin endpoints (`require_roles("admin")`) and return a strongly typed Pydantic response model rather than a raw dict.

### 5.3 Shared reuse with `/sandbox/runtimes`

`GET /api/v1/sandbox/runtimes` should remain a discovery contract, not a full operator report. It may reuse probe results internally, but it should keep returning summarized runtime entries:

- `available`
- `reasons`
- `supported_trust_levels`
- existing enforcement and host summary fields already exposed today

The public route should not include the full helper/template posture or detailed remediation hints.

## 6. Diagnostics Payload

The admin endpoint should return four top-level sections.

### 6.1 `host`

- `os`
- `arch`
- `apple_silicon`
- `macos_version`
- `supported`
- `reasons`

This section answers whether the machine is even a valid target for the macOS runtime family.

### 6.2 `helper`

- `configured`
- `path`
- `exists`
- `executable`
- `ready`
- `transport`
- `reasons`

This section must separate “not configured” from “configured incorrectly” and “configured but not ready.” That distinction matters for operator remediation and test assertions.

Because the current scaffold only has boolean readiness flags, phase 1 should treat `path` and `transport` as optional fields. If no explicit helper-path configuration exists yet, `path` may be `null`, `configured` should be `false`, and `transport` should remain `null` except for known cases such as `fake` in test mode.

### 6.3 `templates`

Return one entry per template-backed runtime, initially at least:

- `vz_linux`
- `vz_macos`

Each entry should include:

- `configured`
- `ready`
- `source`
- `reasons`

The design intentionally avoids promising a richer image-store contract in this slice. The goal is readiness proof, not full template management.

Like helper metadata, `source` should be optional in phase 1. If the runtime only exposes template readiness booleans today, diagnostics may return `source=null` until an explicit operator-facing template source contract exists.

### 6.4 `runtimes`

Return entries for:

- `vz_linux`
- `vz_macos`
- `seatbelt`

Each runtime entry should include:

- `available`
- `supported_trust_levels`
- `reasons`
- `execution_mode` with `fake`, `real`, or `none`
- `remediation`

This section is the derived operator view. It should explain the runtime’s current usability after combining host facts, helper readiness, template readiness, and policy limits.

## 7. Readiness Semantics

The diagnostics layer should use explicit derived states internally:

- `ready`
- `degraded`
- `unavailable`

But the more important contract is the distinction between two different failure classes:

1. `host not ready`
   - unsupported OS/arch
   - helper missing or not executable
   - template missing
   - execution mode not actually wired
2. `policy unsupported`
   - runtime may be host-ready, but the requested or allowed trust level is narrower than the operator expects

Examples:

- `seatbelt` may be host-ready while still rejecting `standard` or `untrusted`
- `vz_linux` may have a valid host and template but still report `execution_mode=none` until real execution is implemented

This distinction should survive into tests and user-visible remediation text.

Phase 1 does not have to expose a separate `status` field if that would widen the schema unnecessarily. Booleans plus reason codes are acceptable as the stable contract, as long as internal derivation still distinguishes these cases consistently.

## 8. Security and Data Exposure

The admin endpoint should be treated as privileged because it can expose:

- helper paths
- template source paths
- detailed host posture
- remediation hints that reveal local setup assumptions

Design constraints:

1. Keep it behind existing sandbox admin authorization.
2. Keep `/sandbox/runtimes` summarized.
3. Prefer machine-readable reason codes plus short remediation text instead of raw exception dumps.
4. Do not expose secrets, tokens, or environment variable values directly.

## 9. Integration Strategy

### 9.1 First integration target

Land the diagnostics layer first as a standalone module and admin endpoint.

### 9.2 Reuse in runtime discovery

After the probe contract is trustworthy, refactor diagnostics and runtime discovery to share the same runner preflight inputs where practical. The goal is to reduce duplicate readiness rules without forcing a risky “big bang” refactor into one patch.

### 9.3 Execution-time truth remains authoritative

Diagnostics help operators understand readiness, but they do not replace authoritative execution-time checks in the runners and service layer. The system should still fail closed if runtime state changes after a successful diagnostic call.

## 10. Potential Problems and Improvements Identified During Review

1. Probe duplication risk
   - If diagnostics invent their own readiness logic instead of sharing runner config/rules, they will drift quickly.
   - Improvement: centralize helper/template fact gathering and have runners consume the same low-level helpers over time.

2. Over-eager helper probing
   - A “ready” check that launches processes, performs writes, or mutates state would make the endpoint unsafe and flaky.
   - Improvement: keep probes read-only in this slice, and add richer handshake checks only when the helper protocol is stable.

3. Overloading `/sandbox/runtimes`
   - Putting the full diagnostics payload into the public discovery route would weaken the API contract and leak operator internals.
   - Improvement: keep the admin endpoint detailed and the public route intentionally shallow.

4. Startup-cache trap
   - A startup-only readiness cache would hide transient local changes and produce stale operator data.
   - Improvement: compute diagnostics on demand first; add caching only if the probes become expensive and cache invalidation is well defined.

## 11. Testing Strategy

### Unit tests

1. Host probe returns correct support state for macOS versus non-macOS and Apple silicon versus non-Apple silicon.
2. Helper probe distinguishes missing path, non-executable helper, and ready helper.
3. Template probe distinguishes configured versus ready template state per runtime.
4. Runtime status derivation separates host-readiness failures from policy-limit failures.
5. Admin runtime diagnostics stay aligned with the same runner preflight reasons used by `/api/v1/sandbox/runtimes`.

### API tests

1. Admin-only access is enforced on `/api/v1/sandbox/admin/macos-diagnostics`.
2. Response schema contains the expected top-level sections and detailed runtime entries.
3. `/api/v1/sandbox/runtimes` remains summarized and does not expose admin-only helper/template detail.

### Host-gated smoke tests

1. On Apple silicon macOS test hosts, verify the real host probe and any real version parsing.
2. Keep these tests gated so the main suite remains deterministic on non-macOS CI.

## 12. Acceptance Criteria

1. A new admin-only macOS diagnostics endpoint returns structured host/helper/template/runtime readiness data.
2. `/api/v1/sandbox/runtimes` remains summarized and does not become the operator diagnostics surface.
3. Readiness semantics clearly distinguish host/setup failures from policy restrictions.
4. The first diagnostics slice is side-effect free and safe to call repeatedly.
5. Tests cover probe behavior, admin authorization, and the summarized discovery contract.
