# Self-Hosting Onboarding Redesign Design (Profile-Based)

**Date:** 2026-02-28
**Status:** Approved
**Owner:** Documentation / Maintainer Team

## 1. Problem Statement

Current onboarding has high cognitive load for first-time self-hosters due to documentation sprawl, overlapping setup guides, and stale setup commands/endpoints in some pages. The main risks are:

- New users cannot quickly identify the canonical setup path.
- Multiple pages duplicate setup commands with drift over time.
- Stale setup references reduce trust in docs and increase support burden.

## 2. Goal and Non-Goals

### Goal

Create a profile-based onboarding system where first-time self-hosters can choose the right setup profile immediately, follow one canonical guide, and verify success with deterministic checks.

### Non-Goals

- Re-architecting runtime features or endpoint behavior.
- Comprehensive rewrite of non-onboarding product/design docs.
- Introducing monthly/ongoing process changes beyond CI enforcement added in this effort.

## 3. Audience and Primary Use Case

Primary audience: **new self-hosters**.

Primary use case: get a fresh environment running and verified with minimal ambiguity, regardless of profile.

## 4. Evaluated Approaches

### Approach A: Big-bang rewrite and delete

- Replace onboarding content in a single large cutover and remove old pages immediately.
- Pros: shortest path to clean final state.
- Cons: highest merge/review risk, difficult to isolate regressions.

### Approach B: Manifest-driven cutover (**Selected**)

- Define canonical onboarding map first, migrate content into that map, and delete/redirect conflicting docs under strict gates.
- Pros: aggressive cleanup with controlled execution, clear auditability.
- Cons: requires up-front manifest and checks.

### Approach C: New portal first, cleanup later

- Build a new onboarding portal while leaving old docs temporarily.
- Pros: lower immediate disruption.
- Cons: preserves drift/duplication longer, conflicts with aggressive cleanup target.

## 5. Approved Information Architecture

Onboarding is profile-based with one shared overlay.

### Canonical onboarding profiles

1. Local single-user
2. Docker single-user
3. Docker multi-user + Postgres
4. GPU/STT Add-on (overlay, shared by all relevant profiles)

### Structural rules

- `README.md` contains one "Start Here" chooser that routes to profile guides.
- `Docs/Getting_Started/README.md` is the canonical profile index.
- Each profile guide uses a common layout:
  - Prerequisites
  - Install
  - Run
  - Verify
  - Troubleshoot
- Setup commands are only allowed in canonical onboarding pages.
- Non-onboarding pages must link to profile guides instead of redefining setup steps.
- `Docs/Published` must mirror this onboarding hierarchy.

## 6. Aggressive Migration and Deletion Policy

All four onboarding components are delivered in phase 1.

### Migration rules

- Migrate valid setup content from legacy pages into canonical profile guides.
- Remove or hard-redirect superseded onboarding pages in the same migration wave.
- Convert partially useful pages into reference-only pages with explicit "setup moved" links.
- Move historical-only onboarding material into archival/product-history areas and remove it from onboarding navigation.

### Inventory and traceability

Maintain a migration inventory document that records, for each impacted page:

- original path
- action (`migrated`, `redirected`, `deleted`, `archived`)
- replacement path (if applicable)

## 7. Quality Gates (Strict)

Merge gate is strict and blocks merge on any failure.

1. **Zero broken links** across onboarding source and published pages.
2. **Command validity checks** for all canonical onboarding flows:
   - local single-user
   - docker single-user
   - docker multi-user + postgres
   - gpu/stt overlay command checks (with environment-aware constraints)
3. **Drift prevention**: fail CI if setup commands appear outside canonical onboarding pages (except explicitly allowlisted snippets).
4. **Published parity**: fail if onboarding source map and published onboarding map diverge.
5. **Legacy endpoint cleanup in onboarding**: no stale onboarding references to deprecated setup paths.

## 8. Deliverables

1. Canonical profile index and profile guides.
2. Shared GPU/STT overlay guide.
3. Migrated onboarding content from legacy pages.
4. Removed/redirected superseded onboarding pages.
5. Migration inventory report.
6. CI checks for links, command validity, drift prevention, and published parity.

## 9. Risks and Mitigations

### Risk: high churn in docs links during aggressive deletion

- Mitigation: enforce migration inventory and parity checks before merge.

### Risk: command checks become flaky across environments

- Mitigation: define deterministic smoke checks with explicit prerequisites and environment guards.

### Risk: contributors reintroduce setup duplication

- Mitigation: CI rule to block setup commands in non-canonical docs.

## 10. Success Criteria

- New self-hosters can select a profile and start correctly without cross-referencing other setup docs.
- Onboarding docs have no stale setup commands or broken links.
- Published docs and source docs present identical onboarding structure.
- Future setup drift is blocked automatically by CI.

