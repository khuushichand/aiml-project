# Deep Research Quality And Trust Plan

**Date:** 2026-03-07

## Goal

Harden deep research outputs so reports are more trustworthy, more auditable, and regression-tested for evidence quality rather than just successful completion.

## Why This Workstream Matters

The module already produces:

- outline, claims, report, and bundle artifacts
- source registry and evidence notes
- provider-backed collection and synthesis

What it still lacks is strong trust signaling. Users need to know:

- whether a claim is truly supported
- when sources disagree
- which sources are weak or low-trust
- how much of the evidence was actually preserved

This workstream should make trust visible in the artifacts, UI, and regression suite.

## Architecture Direction

Keep the current phase structure, but strengthen the synthesis and packaging layers with explicit verification artifacts.

Recommended additions:

- stricter claim-to-citation checks in `synthesizer.py`
- contradiction and unsupported-claim analysis from existing evidence artifacts
- source trust metadata derived from source type, provenance, and snapshot availability
- a verification/evaluation layer that can run against canned research fixtures

## Scope

This workstream covers:

- stronger citation verification
- contradiction surfacing
- unsupported-claim flags
- source trust labels
- a more explicit snapshot policy
- evaluation fixtures and regression thresholds

This workstream does not cover:

- domain-specific truth scoring for every research field
- full fact-checking against external knowledge graphs
- autonomous legal or medical trust classifications

## Stage 1: Claim And Citation Contract Hardening

### Outcome

Claims become first-class verified outputs rather than loose synthesis byproducts.

### Deliverables

- stricter validation that every major claim references existing source IDs
- stronger checks that cited source IDs actually support the claim class they are attached to
- claim severity or confidence labels driven by support coverage

### Success Criteria

- synthesis cannot silently emit unsupported major claims
- low-support claims are flagged instead of being presented as ordinary findings

## Stage 2: Contradictions And Unsupported Claims

### Outcome

The module can explicitly tell users where the evidence disagrees or where the report overreaches.

### Deliverables

- contradiction extraction from evidence notes and source summaries
- unsupported-claim detection after synthesis
- verification artifacts such as:
  - `verification_summary.json`
  - `contradictions.json`
  - `unsupported_claims.json`

### Success Criteria

- the final bundle can surface contradictions separately from consensus findings
- unsupported claims are visible and auditable rather than hidden in prose

## Stage 3: Source Trust And Snapshot Policy

### Outcome

The module records why a source should be trusted and how durable that evidence is.

### Deliverables

- source trust metadata in the source registry or a derived trust artifact
- trust labels such as primary source, secondary source, metadata-only, local corpus, or allowlisted provider
- an explicit snapshot policy recorded per source or per run

### Success Criteria

- users can distinguish strong primary evidence from weaker or transient web evidence
- the bundle records whether a claim depends on non-snapshotted or low-trust sources

## Stage 4: UI And Bundle Surfacing

### Outcome

Trust signals become visible in the run console and exported bundle.

### Deliverables

- claim-level support summaries in the bundle
- contradiction and warning sections in the final package
- trust and snapshot indicators in artifact or bundle views

### Success Criteria

- a user does not need to inspect raw JSON to understand where the report is strong or weak
- exported bundles preserve the same trust signals visible in the console

## Stage 5: Evaluation Fixtures And Regression Gates

### Outcome

Deep research quality can be measured and protected from regressions.

### Deliverables

- canned fixture runs with expected claims, citations, and contradiction behavior
- evaluation helpers that score:
  - claim coverage
  - citation correctness
  - unsupported-claim rate
  - contradiction capture
- threshold-based regression checks for future research changes

### Success Criteria

- the module is judged on evidence quality, not just successful completion
- regressions in citation correctness or claim support fail tests

## Risks

### False Precision

If trust labels look too authoritative without clear rules, users may over-trust weak heuristics.

Mitigation:

- keep labels interpretable and tied to explicit provenance rules

### Over-Blocking Synthesis

If verification becomes too strict too early, useful runs may fail instead of surfacing bounded warnings.

Mitigation:

- distinguish between blocking errors and nonblocking trust warnings

### Fixture Drift

If evaluation fixtures are too brittle, they will become maintenance noise.

Mitigation:

- test stable research invariants, not exact prose

## Exit Condition

This workstream is complete when deep research outputs expose support strength, contradictions, source trust, and snapshot durability in both the machine-readable artifacts and the user-facing bundle, and those properties are guarded by repeatable regression tests.
