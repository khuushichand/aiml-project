# Implementation Plan: Watchlists H2 - Match Between System and Real World

## Scope

Route/components: `WatchlistsPlaygroundPage`, `JobFormModal`, `CronDisplay`, `SettingsTab`  
Finding IDs: `H2.1` through `H2.6`

## Finding Coverage

- Internal vocabulary leakage in navigation and forms: `H2.1`, `H2.2`
- Technical scheduling and retention language burden: `H2.3`, `H2.6`
- Unexplained product/domain jargon: `H2.4`, `H2.5`

## Stage 1: Terminology and Label Pass
**Goal**: Replace implementation-facing labels with user-goal language.
**Success Criteria**:
- Tab labels and major action labels use user-centric wording (behind feature flag if migration risk is high).
- "Scope" and similar jargon in forms are replaced with plain-language labels and helper text.
- "Claim Clusters" and "MECE" terms include short explanations adjacent to controls.
**Tests**:
- i18n key snapshot tests for renamed labels.
- Component tests validating helper text presence for renamed concepts.
- Smoke tests confirming route-to-tab mapping still works after rename.
**Status**: Complete

## Stage 2: Human-Friendly Scheduling and Retention Inputs
**Goal**: Reduce technical parsing burden in job setup.
**Success Criteria**:
- Schedule UI defaults to natural presets and calendar/time controls; raw cron is advanced mode.
- TTL/retention is entered as duration units (`hours`, `days`, `weeks`) with safe conversion.
- Cron tooltip copy explains run cadence in plain language.
**Tests**:
- Unit tests for duration-to-seconds conversion and round-trip edit behavior.
- Component tests for schedule preset selection and advanced-mode guardrails.
- Integration tests for submitted payload parity with prior API contract.
**Status**: Complete

## Stage 3: First-Run Workflow Framing
**Goal**: Align page structure with user mental model for first successful briefing.
**Success Criteria**:
- First-run callout maps pipeline in one line ("Add Feed -> Set Schedule -> Review Results").
- Quick setup path from empty state can create source + job in a guided sequence.
- Completion state confirms when first run will execute and where results appear.
**Tests**:
- E2E first-run workflow test from empty state to first run creation.
- Component tests for onboarding state persistence/dismiss behavior.
- UX acceptance checklist verifying no unexplained jargon in first-run path.
**Status**: Complete

## Dependencies

- Label changes should be coordinated with H4 consistency patterns.
- Quick setup flow should reuse efficiency controls in H7 to avoid duplicate UX paths.
