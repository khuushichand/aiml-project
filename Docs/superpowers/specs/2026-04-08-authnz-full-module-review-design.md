# AuthNZ Full Module Review Design

Date: 2026-04-08
Topic: Full AuthNZ module deep review with remediation roadmap
Status: Approved design

## Objective

Review the AuthNZ surface in `tldw_server` for concrete bugs, security issues,
correctness problems, documentation drift, test gaps, and maintainability risks
with a deep, evidence-first audit.

The review should produce a ranked findings report and a prioritized remediation
roadmap. Unlike narrower prior AuthNZ reviews, this run explicitly includes the
core AuthNZ module, its immediate API integration points, and the tests and docs
that define or describe current behavior.

This review is allowed to include small proof-of-fix patches, but only for
confirmed critical issues where the remediation is localized and can be verified
without forcing a risky redesign during the audit.

## Scope

This review is centered on:

- `tldw_Server_API/app/core/AuthNZ`
- `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`
- `tldw_Server_API/app/api/v1/endpoints/auth.py`
- representative admin or control-surface endpoints that materially depend on
  AuthNZ claim-first enforcement
- AuthNZ-focused tests and adjacent tests that validate AuthNZ runtime behavior
- documentation that claims current AuthNZ behavior

This includes:

- authentication entry points and credential resolution
- authorization and claim-first dependency enforcement
- JWT issuance, validation, scoping, rotation, and revocation assumptions
- session lifecycle and blacklist behavior
- password, reset, email verification, MFA, API key, and virtual key flows
- rate limit, quota, lockout, and budget guardrails where they are part of the
  AuthNZ runtime contract
- settings precedence, mode and profile handling, startup and initialization
  behavior, and backend-specific persistence paths
- migration and schema safety across SQLite and PostgreSQL
- test coverage quality and documentation accuracy for the reviewed behavior

This review excludes:

- a full platform-wide endpoint audit outside AuthNZ-driven behavior
- broad product UX critique
- speculative rewrites that are not supported by concrete evidence
- large remediation refactors during the review itself

## Approaches Considered

### Recommended: Layered risk audit

Map trust boundaries first, then inspect the highest-risk AuthNZ internals and
their integration points, and finally compare implementation behavior against
tests and docs before writing findings.

Why this is preferred:

- it matches the user’s request for a deep audit plus roadmap
- it surfaces security and authz failures before lower-value cleanup
- it reduces the chance of missing issues hidden between core services and API
  dependencies
- it supports selective proof-of-fix patches without turning the review into a
  rewrite

### Alternative: Surface-first audit

Inspect architecture, the largest files, and representative endpoints, then
spot-check tests and docs.

Trade-offs:

- faster
- useful for a quick health scan
- weaker for edge-case runtime failures and persistence or migration hazards

### Alternative: Endpoint-first behavior audit

Start from `/api/v1/auth*`, `auth_deps.py`, and the current tests, then trace
back into core AuthNZ services.

Trade-offs:

- strong for externally visible regressions
- strong for auth and authz contract mismatches
- weaker for dormant but dangerous internals such as migrations, settings
  precedence, and backend divergence

## Chosen Method

Use the recommended layered risk audit with five ordered passes:

1. `Boundary map`
   Identify authentication entry points, authorization gates, trust boundaries,
   secret and key handling, and mode or profile switches.
2. `Runtime correctness`
   Inspect credential resolution, session lifecycle, JWT or API-key behavior,
   RBAC and claim enforcement, and stateful security controls.
3. `Persistence and configuration safety`
   Review settings precedence, startup and initialization behavior, DB
   abstractions, migrations, and SQLite or PostgreSQL divergence.
4. `Evidence cross-check`
   Compare suspicious or high-risk behavior against tests, recent commits, and
   current docs to distinguish confirmed defects from assumptions, stale docs,
   or already-covered invariants.
5. `Findings and remediation synthesis`
   Produce a ranked review report and roadmap, and apply only narrowly scoped
   proof-of-fix patches for confirmed critical issues that satisfy the patch
   gate below.

## Evidence Model

The review will rely on:

- direct source inspection of the scoped AuthNZ code and immediate integration
  points
- direct inspection of AuthNZ-focused tests across:
  - `tldw_Server_API/tests/AuthNZ`
  - `tldw_Server_API/tests/AuthNZ_SQLite`
  - `tldw_Server_API/tests/AuthNZ_Postgres`
  - `tldw_Server_API/tests/AuthNZ_Unit`
  - `tldw_Server_API/tests/AuthNZ_Federation`
- targeted caller inspection when an AuthNZ behavior is only meaningful in its
  API dependency or endpoint context
- targeted documentation inspection where docs claim current runtime behavior
- recent git history when it helps explain regression-prone areas or newly
  changed contracts

The review is evidence-first, not style-first. A concern becomes a reported
finding only when there is concrete support from code, tests, docs drift that
creates real risk, or targeted verification.

Runtime verification may be used selectively when it materially strengthens or
weakens a specific claim. It should answer narrow questions such as:

- whether a suspicious branch is actually exercised
- whether a contract claimed by docs or tests no longer matches code
- whether a critical invariant fails under current fixtures
- whether SQLite and PostgreSQL behavior diverge on a reviewed path

If verification cannot be run, the limitation should be stated explicitly and
the issue should remain a probable risk unless source evidence is already
conclusive.

## Review Focus Areas

The review order inside the scoped surface should bias toward:

- credential resolution order and ambiguity between single-user key auth,
  multi-user JWT auth, API keys, and virtual keys
- claim-first authorization and the risk of mode-based bypasses
- token creation, validation, revocation, refresh rotation, and blacklist usage
- session lifecycle, encrypted token storage, key management, and revocation
  consistency
- password, reset, verification, MFA, and lockout behavior
- API key and virtual key issuance, validation, scoping, quotas, and budgets
- settings precedence, fail-open or fail-closed behavior, and deployment-mode
  coordination
- backend-specific persistence, migration safety, and schema harmonization
- docs drift and test gaps on high-risk auth and authz contracts
- maintainability problems in very large files where blurred boundaries are
  likely to create future defects

Initial hotspot files should include at least:

- `tldw_Server_API/app/core/AuthNZ/User_DB_Handling.py`
- `tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py`
- `tldw_Server_API/app/core/AuthNZ/jwt_service.py`
- `tldw_Server_API/app/core/AuthNZ/session_manager.py`
- `tldw_Server_API/app/core/AuthNZ/api_key_manager.py`
- `tldw_Server_API/app/core/AuthNZ/permissions.py`
- `tldw_Server_API/app/core/AuthNZ/settings.py`
- `tldw_Server_API/app/core/AuthNZ/database.py`
- `tldw_Server_API/app/core/AuthNZ/migrations.py`
- `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`
- `tldw_Server_API/app/api/v1/endpoints/auth.py`

Representative expansion beyond the hotspot set should be driven by one or more
of these signals:

- high fan-out
- recent churn or repeated regressions
- security sensitivity
- backend divergence
- unusually large or multi-responsibility implementations

## Findings Model

The final report should present findings first, ordered by severity.

Each observation should be classified as one of:

### Confirmed finding

A concrete bug, vulnerability, contract mismatch, persistence hazard, or design
problem supported directly by code, tests, docs drift with operational risk, or
targeted verification.

### Probable risk

Something that appears unsafe, brittle, or likely wrong but depends on
assumptions that are not fully proven within the reviewed evidence.

### Improvement

A maintainability, hardening, or architectural simplification opportunity that
would reduce future risk but is not itself strong evidence of a current defect.

Each reported item should include:

- severity
- confidence
- concise description of the failure mode or risk
- why it matters
- concrete file references

## Severity Model

Severity should be weighted primarily by:

- security and privilege-escalation risk
- authentication or authorization correctness risk
- data integrity or session/token safety risk
- blast radius across modes, backends, or high-fan-out callers
- probability of recurring regressions caused by maintainability debt

Documentation drift and test gaps are in scope, but they must not outrank a
real runtime or security defect unless they create direct operational risk.

## Deliverable Contract

The review will produce three outputs:

### 1. Findings report

The final response should be in code-review style, ordered by severity, with
runtime and security defects first, then correctness issues, then
maintainability, docs drift, and test gaps.

### 2. Remediation roadmap

The roadmap should group work into:

- immediate fixes
- near-term hardening
- structural refactors worth scheduling

The roadmap should be concrete and minimal. It should recommend the smallest
defensible change that addresses the real issue rather than broad rewrites.

### 3. Proof-of-fix patches for confirmed critical issues only

Patches are allowed only when all of these are true:

- the issue is confirmed, not speculative
- severity is critical or otherwise urgent enough to justify interrupting the
  review flow
- the fix is localized and low-risk
- the change can be verified with targeted tests or other concrete checks

If a safe fix requires a broader redesign, the review should stop at the
finding plus roadmap item and not force a risky patch during the audit.

## Patch Gate

A proof-of-fix patch is permitted only if it satisfies this decision rule:

1. The bug is real and supported by direct evidence.
2. The touched area can be changed without broad coordination or endpoint-wide
   redesign.
3. The likely fix does not depend on unresolved product choices.
4. Verification can be run against the changed behavior.

If any of these are false, the issue stays in the report and roadmap only.

## Testing And Verification Strategy

Testing effort during the review should remain targeted, not exhaustive.

Verification should prefer the smallest useful command set that can answer a
specific question. When code changes are made, the review must verify them with
focused tests or equivalent concrete checks before claiming success.

Because touched code may include security-sensitive paths, completion for any
proof-of-fix patch should also include Bandit on the touched scope using the
project virtual environment.

## Execution Boundaries

- Stay focused on AuthNZ and its immediate integration surface.
- Do not silently expand into a full application review.
- Do not present speculation as a confirmed bug.
- Do not let large-file maintainability commentary crowd out higher-signal auth
  and authz failures.
- Do not turn the deep audit into a large remediation project during the same
  pass.

## Success Criteria

The review is successful when:

- the full approved AuthNZ surface is covered with risk-weighted depth
- findings are evidence-based and ordered by severity
- code and security defects are clearly separated from softer risks and
  maintainability issues
- docs drift and test gaps are treated as first-class findings when they create
  meaningful operational or regression risk
- the final report is immediately usable for triage
- any proof-of-fix patches are narrow, justified, and verified
- unresolved blind spots are made explicit instead of being mistaken for clean
  health

## Expected Outcome

This design yields a deep, boundary-aware AuthNZ audit that is broad enough to
cover core services, API integration points, tests, and documentation contracts
without losing prioritization. The result should be a high-signal findings
report, a practical remediation roadmap, and only those small critical patches
that can be made safely and verified during the review.
