# Family Guardrails Wizard Design

Date: 2026-03-01  
Status: Approved for planning  
Owners: WebUI + Extension + API

## Summary

Design a full **Family Guardrails Wizard** for new and existing household admins who need to configure LLM safety for dependents with minimal complexity.

This wizard is template-first, supports multiple household configurations, and preserves the current consent model where supervision links become active after dependent acceptance.

## Goals

1. Make first-time setup straightforward for non-technical parents/caregivers.
2. Support household configurations in v1:
   - one guardian, multiple dependents
   - two guardians, shared dependents
   - institutional/caregiver setups
3. Keep consent-based activation semantics.
4. Support account provisioning for dependents inside the wizard.
5. Ship parity in WebUI and extension options surfaces.

## Non-Goals (v1)

1. Remove dependent acceptance requirement.
2. Replace all advanced moderation and guardian pages.
3. Add new out-of-band acceptance channels beyond in-app acceptance.

## Current Constraints

1. Guardian relationships are created in `pending` state and become enforceable at `active`.
2. Supervised policy creation currently requires an `active` relationship.
3. Guardian route availability is currently coupled to both guardian + self-monitoring capability flags.

These constraints require a pre-acceptance draft layer for wizard UX.

## Recommended Approach

Adopt a single **Household Graph Wizard** as the canonical setup flow.

Why:
1. Handles all supported household structures in one mental model.
2. Reduces context switching versus separate relationship/policy wizards.
3. Scales better as dependent count grows.

## Entry Points

1. WebUI: `Settings -> Family Guardrails Wizard` (new canonical entry).
2. Extension options: same full wizard route and behavior.
3. Existing pages remain available as advanced tools:
   - `Settings -> Guardian & Monitoring`
   - `Moderation Playground`

## Wizard Flow

1. **Household Basics**
   - household name
   - mode: `family` or `institutional`

2. **Add Guardians**
   - current user prefilled
   - optionally add second guardian or caregiver accounts

3. **Add Dependents (Create Accounts)**
   - create dependent accounts in wizard
   - minimal required fields only
   - add multiple dependents quickly

4. **Relationship Mapping**
   - guardian/dependent matrix
   - create pending supervision links
   - validate no orphan dependents and no invalid mappings

5. **Templates (Default) + Optional Customization**
   - per-dependent template selection
   - optional override panel for advanced edits

6. **Alert Preferences**
   - per-guardian alert routing defaults
   - clarify alert privacy options (`topic_only`, `snippet`, `full_message`)

7. **Invite + Acceptance Tracker**
   - status per dependent link (`pending`, `accepted`, etc.)
   - resend invite action
   - clear “queued until acceptance” messaging

8. **Review + Activate**
   - dependency-aware summary
   - mixed-result activation (`active` + `pending`) supported

## Critical Design Refinements (Mandatory)

### 1) Pre-Acceptance Draft + Materialization

Add a wizard draft layer:
1. Save planned guardrails before dependent acceptance.
2. Queue plans against pending links.
3. Auto-materialize queued plans once link transitions to `active`.
4. Make materialization idempotent.

### 2) Conflict Policy for Shared Dependents

For two-guardian households, enforce deterministic conflict resolution:
1. default: **strictest-wins** for effective action
2. audit trail records source policy/template and merge result
3. UI explains why effective behavior was chosen

### 3) First-Class Acceptance Operations

Acceptance is not hidden in row actions. Provide dedicated operations:
1. acceptance tracker table
2. resend invite controls
3. per-dependent blockers and next actions
4. household health summary (`pending count`, `active count`)

### 4) Capability Gating Adjustment

Do not block wizard availability on self-monitoring capability.
1. gate guardian setup wizard primarily on guardian endpoints
2. degrade self-monitoring sections independently if unavailable

### 5) WebUI + Extension Parity Tests

Add explicit parity checks:
1. wizard route present in both inventories
2. equivalent step progression and validation behavior
3. core scenarios e2e in both surfaces

### 6) Documentation Realignment

Publish wizard-first family setup guide and link from existing family docs.

## Data/State Model

Add wizard-oriented entities:
1. `HouseholdDraft`
2. `HouseholdMemberDraft`
3. `RelationshipDraft`
4. `GuardrailPlanDraft`
5. `ActivationRun`

State progression:
1. `draft`
2. `invites_pending`
3. `partially_active`
4. `active`
5. `needs_attention`

## API Orchestration (Conceptual)

1. Draft CRUD and resume-by-step.
2. Account provisioning for guardians/dependents.
3. Batch relationship mapping.
4. Plan save and queue for pending links.
5. Acceptance status queries.
6. Materialize-on-accept and manual replay endpoint.
7. Activation summary endpoint with per-dependent results.

## UX Patterns

1. Template-first default; manual controls behind expandable advanced sections.
2. 1-2 dependents: card-centric detail view.
3. Larger households: compact table view + bulk actions.
4. Institutional mode uses role/wording variants, not separate architecture.

## Success Metrics

1. Time to completed household setup.
2. Step completion rate through review/activation.
3. Pending-to-accepted conversion at 24h and 7d.
4. Template override frequency (template fit signal).
5. Error/retry rate per step.

## Test Strategy

1. Unit
   - wizard state transitions
   - template mapping
   - conflict merge logic
   - materialization idempotency

2. Integration
   - draft save/resume
   - pending link + queued plans
   - activation on acceptance

3. End-to-End (WebUI + extension options)
   - one guardian + two dependents
   - two guardians + shared dependent
   - institutional mode
   - partial acceptance mixed-state household

4. Regression
   - existing guardian/moderation advanced pages remain functional

## Rollout Plan

1. Feature-flagged alpha.
2. Beta with selected households.
3. Set wizard as canonical setup entry after beta metrics pass.
4. Keep legacy advanced pages for ongoing administration.

## Risks and Mitigations

1. **Risk:** partial activation confusion  
   **Mitigation:** explicit tracker + status semantics + reminders.

2. **Risk:** policy conflicts in shared-dependent homes  
   **Mitigation:** strictest-wins + explainability + audit records.

3. **Risk:** route parity drift between WebUI and extension  
   **Mitigation:** shared route assertions in CI.

4. **Risk:** backend sequencing race on acceptance/materialization  
   **Mitigation:** idempotent materialization + activation run journal.

## Open Implementation Questions (for planning phase)

1. Exact schema boundary between draft tables and existing guardian tables.
2. Where to host reminder/resend orchestration logic.
3. Whether conflict policy should be globally configurable in v1 or fixed.

## Decision Log

1. Consent-based model retained.
2. Primary setup starts in settings area, not moderation playground.
3. Full wizard required, not lightweight overlay.
4. Launch supports household models: one guardian/many dependents, two guardians/shared dependents, institutional.
5. In-app acceptance is the v1 acceptance mechanism.
6. Wizard ships in both WebUI and extension options.
7. Template-first with optional manual customization.
8. Account creation is included in wizard v1.
